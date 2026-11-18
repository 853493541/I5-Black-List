//! 金色传说's renderer: crate::gpu with two more textures, the atlas of baked pictures (premultiplied
//! RGBA) and, beside it, when each gold pixel is drawn (one float a pixel), for the image shapes.

use wgpu::util::DeviceExt;

use super::atlas::Atlas;
use crate::prim::{Frame, Prim};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    galaxy: wgpu::Texture,
    blank: wgpu::TextureView,
    size: wgpu::Buffer,
    atlas: wgpu::TextureView,
    times: wgpu::TextureView,
    /// The adapter's name and kind, e.g. "llvmpipe (LLVM ...), Cpu".
    pub adapter: String,
}

fn texture(device: &wgpu::Device, w: u32, h: u32, usage: wgpu::TextureUsages) -> wgpu::Texture {
    texture_as(device, w, h, usage, FORMAT)
}

fn texture_as(device: &wgpu::Device, w: u32, h: u32, usage: wgpu::TextureUsages, format: wgpu::TextureFormat) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: None,
        size: wgpu::Extent3d { width: w, height: h, depth_or_array_layers: 1 },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format,
        usage,
        view_formats: &[],
    })
}

impl Renderer {
    /// A renderer for frames of width x height (width a multiple of 64) over `lobby`, RGBA bytes of that size.
    pub fn new(width: u32, height: u32, lobby: &[u8], art: &Atlas) -> Result<Self, String> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).map_err(|e| e.to_string())?;
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("angel.wgsl").into()) });
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
        queue.write_texture(
            lobby_tex.as_image_copy(),
            lobby,
            wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(width * 4), rows_per_image: None },
            lobby_tex.size(),
        );
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let galaxy = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING);
        let blank = texture(&device, 1, 1, usage).create_view(&Default::default());
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let (aw, ah) = (art.w as u32, art.h as u32);
        let atlas = texture(&device, aw, ah, usage);
        queue.write_texture(atlas.as_image_copy(), &art.px, wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(aw * 4), rows_per_image: None }, atlas.size());
        let times = texture_as(&device, aw, ah, usage, wgpu::TextureFormat::R32Float);
        queue.write_texture(times.as_image_copy(), bytemuck::cast_slice(&art.times), wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(aw * 4), rows_per_image: None }, times.size());
        let (atlas, times) = (atlas.create_view(&Default::default()), times.create_view(&Default::default()));
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self { device, queue, pipeline, target, lobby: lobby_tex.create_view(&Default::default()), galaxy, blank, size, atlas, times, adapter })
    }

    fn draw(&self, frame: &Frame, onto: &wgpu::Texture, galaxy: &wgpu::TextureView) {
        let storage = |bytes: &[u8]| self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage: wgpu::BufferUsages::STORAGE });
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
                wgpu::BindGroupEntry { binding: 3, resource: wgpu::BindingResource::TextureView(galaxy) },
                wgpu::BindGroupEntry { binding: 4, resource: self.size.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 5, resource: wgpu::BindingResource::TextureView(&self.atlas) },
                wgpu::BindGroupEntry { binding: 6, resource: wgpu::BindingResource::TextureView(&self.times) },
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

    /// Draws the scene's still layer (the warm wash) once, as the Python Wash does.
    pub fn set_galaxy(&self, frame: &Frame) {
        self.draw(frame, &self.galaxy, &self.blank);
    }

    /// Draws one frame and waits until the chip is done.
    pub fn render(&self, frame: &Frame) {
        let view = self.galaxy.create_view(&Default::default());
        self.draw(frame, &self.target, &view);
        let _ = self.device.poll(wgpu::PollType::Wait);
    }

    /// The last frame as RGBA bytes.
    pub fn read(&self) -> Vec<u8> {
        crate::render::read(&self.device, &self.queue, &self.target)
    }
}
