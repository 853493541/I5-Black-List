//! Draws 毛茸茸's frames on the graphics chip with wgpu, offscreen (the spike's gpu.rs with layers
//! and an atlas): one instanced draw of every shape and picture over the lobby, read back as RGBA
//! bytes. Without a GPU driver it runs on Mesa's software Vulkan, lavapipe.

use wgpu::util::DeviceExt;

use super::Fluffy;
use crate::prim::{Frame, Prim};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    page: wgpu::Texture,
    doodles: wgpu::Texture,
    atlas: wgpu::Texture,
    shown: std::cell::Cell<[[f64; 2]; 2]>,
    size: wgpu::Buffer,
    width: u32,
    /// The adapter's name and kind, e.g. "llvmpipe (LLVM ...), Cpu".
    pub adapter: String,
}

fn texture(device: &wgpu::Device, w: u32, h: u32, usage: wgpu::TextureUsages) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: None,
        size: wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: FORMAT,
        usage,
        view_formats: &[],
    })
}

fn upload(queue: &wgpu::Queue, onto: &wgpu::Texture, bytes: &[u8], width: u32) {
    let layout = wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(width * 4), rows_per_image: None };
    queue.write_texture(onto.as_image_copy(), bytes, layout, onto.size());
}

impl Renderer {
    /// A renderer for the scene's frames over `lobby`, RGBA bytes of its size (width a multiple of 64).
    pub fn new(scene: &Fluffy, lobby: &[u8]) -> Result<Self, String> {
        Self::on(&crate::render::open()?, scene, lobby)
    }

    /// The same on a given device (the stage's, in the app).
    pub fn on(chip: &crate::render::Chip, scene: &Fluffy, lobby: &[u8]) -> Result<Self, String> {
        let (width, height) = (scene.width.ceil() as u32, scene.height.ceil() as u32);
        let (device, queue, info) = (chip.device.clone(), chip.queue.clone(), chip.info.clone());
        let shader =
            device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("fluffy.wgsl").into()) });
        let blend = wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING;
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: None,
            layout: None,
            vertex: wgpu::VertexState { module: &shader, entry_point: Some("vs"), compilation_options: Default::default(), buffers: &[] },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState { format: FORMAT, blend: Some(blend), write_mask: wgpu::ColorWrites::ALL })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        let usage = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST;
        let lobby_tex = texture(&device, width, height, usage);
        upload(&queue, &lobby_tex, lobby, width);
        let atlas = texture(&device, scene.atlas.canvas.w as u32, scene.atlas.canvas.h as u32, usage);
        upload(&queue, &atlas, bytemuck::cast_slice(&scene.atlas.canvas.px), scene.atlas.canvas.w as u32);
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let (page, doodles) = (texture(&device, width, height, usage), texture(&device, width, height, usage));
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: None,
            contents: bytemuck::cast_slice(&dims),
            usage: wgpu::BufferUsages::UNIFORM,
        });
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self {
            device,
            queue,
            pipeline,
            target,
            lobby: lobby_tex.create_view(&Default::default()),
            page,
            doodles,
            atlas,
            shown: std::cell::Cell::new([[-1.0; 2]; 2]),
            size,
            width,
            adapter,
        })
    }

    fn draw(&self, frame: &Frame, onto: &wgpu::Texture) {
        let view = |t: &wgpu::Texture| t.create_view(&Default::default());
        let (page, doodles, atlas) = (view(&self.page), view(&self.doodles), view(&self.atlas));
        let storage = |bytes: &[u8]| {
            self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage: wgpu::BufferUsages::STORAGE })
        };
        let one = [Prim::default()];
        let prims = storage(bytemuck::cast_slice(if frame.prims.is_empty() { &one } else { &frame.prims }));
        let none = [[0.0f32; 2]];
        let points = storage(bytemuck::cast_slice(if frame.points.is_empty() { &none } else { &frame.points }));
        let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipeline.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: prims.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: points.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: wgpu::BindingResource::TextureView(&self.lobby) },
                wgpu::BindGroupEntry { binding: 3, resource: wgpu::BindingResource::TextureView(&page) },
                wgpu::BindGroupEntry { binding: 4, resource: self.size.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 5, resource: wgpu::BindingResource::TextureView(&doodles) },
                wgpu::BindGroupEntry { binding: 6, resource: wgpu::BindingResource::TextureView(&atlas) },
            ],
        });
        let view = onto.create_view(&Default::default());
        let mut encoder = self.device.create_command_encoder(&Default::default());
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT), store: wgpu::StoreOp::Store },
                })],
                ..Default::default()
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &group, &[]);
            pass.draw(0..6, 0..frame.prims.len() as u32);
        }
        self.queue.submit([encoder.finish()]);
    }

    /// Draws the scene at t seconds and waits until the chip is done; the page and doodle layers
    /// are worked out again only when they changed.
    pub fn render(&self, scene: &Fluffy, t: f64) {
        let shot = scene.paint(t);
        let [page, doodles] = self.shown.get();
        if shot.page != page {
            upload(&self.queue, &self.page, bytemuck::cast_slice(&scene.page(shot.page).px), self.width);
        }
        if shot.doodles != doodles {
            upload(&self.queue, &self.doodles, bytemuck::cast_slice(&scene.doodles(shot.doodles).px), self.width);
        }
        self.shown.set([shot.page, shot.doodles]);
        self.draw(&shot.frame, &self.target);
        let _ = self.device.poll(wgpu::PollType::Wait);
    }

    /// The last frame as RGBA bytes.
    /// The device, its queue and the texture the last frame was drawn into (for `render::deliver`).
    pub fn drawn(&self) -> (&wgpu::Device, &wgpu::Queue, &wgpu::Texture) {
        (&self.device, &self.queue, &self.target)
    }

    pub fn read(&self) -> Vec<u8> {
        crate::render::read(&self.device, &self.queue, &self.target)
    }
}
