//! Draws a scene's frames on the graphics chip with wgpu, offscreen. Copied from crate::gpu and grown
//! for 玫瑰花边 and 经典: two layers the scene draws once and lays on later (Python's cached
//! pictures), and an atlas of pictures the scene works out on the CPU (Python's numpy light).

use wgpu::util::DeviceExt;

use crate::lace::prim::{Frame, Prim};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    layers: [wgpu::Texture; 2],
    atlas: wgpu::TextureView,
    blank: wgpu::TextureView,
    size: wgpu::Buffer,
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

fn upload(device: &wgpu::Device, queue: &wgpu::Queue, w: u32, h: u32, bytes: &[u8]) -> wgpu::TextureView {
    let tex = texture(device, w, h, wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST);
    queue.write_texture(tex.as_image_copy(), bytes, wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w * 4), rows_per_image: None }, tex.size());
    tex.create_view(&Default::default())
}

impl Renderer {
    /// A renderer for frames of width x height (width a multiple of 64) over `lobby`, RGBA bytes of that size.
    pub fn new(width: u32, height: u32, lobby: &[u8]) -> Result<Self, String> {
        Self::on(&crate::render::open()?, width, height, lobby)
    }

    /// The same on a given device (the stage's, in the app).
    pub fn on(chip: &crate::render::Chip, width: u32, height: u32, lobby: &[u8]) -> Result<Self, String> {
        let (device, queue, info) = (chip.device.clone(), chip.queue.clone(), chip.info.clone());
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("scene.wgsl").into()) });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: None,
            layout: None,
            vertex: wgpu::VertexState { module: &shader, entry_point: Some("vs"), compilation_options: Default::default(), buffers: &[] },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState { format: FORMAT, blend: Some(wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING), write_mask: wgpu::ColorWrites::ALL })],
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        let lobby = upload(&device, &queue, width, height, lobby);
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let layer = || texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING);
        let layers = [layer(), layer()];
        let blank = upload(&device, &queue, 1, 1, &[0; 4]);
        let atlas = upload(&device, &queue, 1, 1, &[0; 4]);
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self { device, queue, pipeline, target, lobby, layers, atlas, blank, size, adapter })
    }

    /// The scene's CPU-made pictures, one RGBA (premultiplied) atlas of w x h.
    pub fn set_atlas(&mut self, w: u32, h: u32, bytes: &[u8]) {
        self.atlas = upload(&self.device, &self.queue, w, h, bytes);
    }

    fn draw(&self, frame: &Frame, onto: &wgpu::Texture, with_layers: bool) {
        let storage = |bytes: &[u8]| self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage: wgpu::BufferUsages::STORAGE });
        let one = [Prim::default()];
        let prims = storage(bytemuck::cast_slice(if frame.prims.is_empty() { &one } else { &frame.prims }));
        let none = [[0.0f32; 2]];
        let points = storage(bytemuck::cast_slice(if frame.points.is_empty() { &none } else { &frame.points }));
        let views: Vec<wgpu::TextureView> = self.layers.iter().map(|l| l.create_view(&Default::default())).collect();
        let (a, b) = if with_layers { (&views[0], &views[1]) } else { (&self.blank, &self.blank) };
        fn view(v: &wgpu::TextureView) -> wgpu::BindingResource<'_> {
            wgpu::BindingResource::TextureView(v)
        }
        let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipeline.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: prims.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: points.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: view(&self.lobby) },
                wgpu::BindGroupEntry { binding: 3, resource: view(a) },
                wgpu::BindGroupEntry { binding: 4, resource: view(b) },
                wgpu::BindGroupEntry { binding: 5, resource: view(&self.atlas) },
                wgpu::BindGroupEntry { binding: 6, resource: self.size.as_entire_binding() },
            ],
        });
        let target = onto.create_view(&Default::default());
        let mut encoder = self.device.create_command_encoder(&Default::default());
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &target,
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

    /// Draws a still layer (0 or 1) once, onto transparency, as Python paints its cached pictures.
    pub fn set_layer(&self, which: usize, frame: &Frame) {
        self.draw(frame, &self.layers[which], false);
    }

    /// Draws one frame and waits until the chip is done.
    pub fn render(&self, frame: &Frame) {
        self.draw(frame, &self.target, true);
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
