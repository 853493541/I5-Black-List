//! Draws 演说家遇袭's frames with wgpu, offscreen: the scene's pictures uploaded once as textures,
//! the veil (fog and flash) drawn at half size into a texture of its own, then everything over the
//! lobby in one pass, one draw per run of shapes or per picture; read back as RGBA bytes.

use wgpu::util::DeviceExt;

use super::frame::{Frame, Prim};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    target: wgpu::Texture,
    textures: Vec<wgpu::Texture>,
    width: u32,
    height: u32,
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

impl Renderer {
    /// A renderer for frames of width x height (width a multiple of 64).
    pub fn new(width: u32, height: u32) -> Result<Self, String> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).map_err(|e| e.to_string())?;
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("claw.wgsl").into()) });
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
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let mut gpu = Self { device, queue, pipeline, target, textures: Vec::new(), width, height, adapter: format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend) };
        // Texture 0: a blank texel, read by draws that read none.
        gpu.add(1, 1, &[0; 4]);
        Ok(gpu)
    }

    /// Uploads a picture (premultiplied RGBA bytes); its number for Frame::image.
    pub fn add(&mut self, w: usize, h: usize, bytes: &[u8]) -> usize {
        let usage = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST;
        let tex = texture(&self.device, w as u32, h as u32, usage);
        self.queue.write_texture(tex.as_image_copy(), bytes, wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w as u32 * 4), rows_per_image: None }, tex.size());
        self.textures.push(tex);
        self.textures.len() - 1
    }

    /// A texture a frame can be drawn into (the veil) and then read as a picture.
    pub fn add_target(&mut self, w: usize, h: usize) -> usize {
        let usage = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::RENDER_ATTACHMENT;
        self.textures.push(texture(&self.device, w as u32, h as u32, usage));
        self.textures.len() - 1
    }

    fn pass(&self, encoder: &mut wgpu::CommandEncoder, frame: &Frame, onto: &wgpu::Texture) {
        let storage = |bytes: &[u8]| self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage: wgpu::BufferUsages::STORAGE });
        let one = [Prim::default()];
        let prims = storage(bytemuck::cast_slice(if frame.prims.is_empty() { &one } else { &frame.prims }));
        let none = [[0.0f32; 2]];
        let points = storage(bytemuck::cast_slice(if frame.points.is_empty() { &none } else { &frame.points }));
        let dims = [onto.width() as f32, onto.height() as f32, 0.0, 0.0];
        let size = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let layout = self.pipeline.get_bind_group_layout(0);
        let groups: Vec<wgpu::BindGroup> = frame
            .draws
            .iter()
            .map(|d| {
                let pic = self.textures[d.texture.unwrap_or(0)].create_view(&Default::default());
                let keep = self.textures[d.mask.unwrap_or(0)].create_view(&Default::default());
                self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                    label: None,
                    layout: &layout,
                    entries: &[
                        wgpu::BindGroupEntry { binding: 0, resource: prims.as_entire_binding() },
                        wgpu::BindGroupEntry { binding: 1, resource: points.as_entire_binding() },
                        wgpu::BindGroupEntry { binding: 2, resource: wgpu::BindingResource::TextureView(&pic) },
                        wgpu::BindGroupEntry { binding: 3, resource: wgpu::BindingResource::TextureView(&keep) },
                        wgpu::BindGroupEntry { binding: 4, resource: size.as_entire_binding() },
                    ],
                })
            })
            .collect();
        let view = onto.create_view(&Default::default());
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
        for (d, group) in frame.draws.iter().zip(&groups) {
            pass.set_bind_group(0, group, &[]);
            pass.draw(0..6, d.start..d.end);
        }
    }

    /// Draws `veil` into texture `veil_to` (when given), then `frame` onto the screen, and waits.
    pub fn render(&self, veil: Option<(&Frame, usize)>, frame: &Frame) {
        let mut encoder = self.device.create_command_encoder(&Default::default());
        if let Some((v, to)) = veil {
            self.pass(&mut encoder, v, &self.textures[to]);
        }
        self.pass(&mut encoder, frame, &self.target);
        self.queue.submit([encoder.finish()]);
        let _ = self.device.poll(wgpu::PollType::Wait);
    }

    /// The last frame as RGBA bytes.
    pub fn read(&self) -> Vec<u8> {
        let row = self.width * 4;
        let buffer = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: None,
            size: u64::from(row * self.height),
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut encoder = self.device.create_command_encoder(&Default::default());
        encoder.copy_texture_to_buffer(
            self.target.as_image_copy(),
            wgpu::TexelCopyBufferInfo { buffer: &buffer, layout: wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(row), rows_per_image: None } },
            self.target.size(),
        );
        self.queue.submit([encoder.finish()]);
        buffer.slice(..).map_async(wgpu::MapMode::Read, |_| {});
        let _ = self.device.poll(wgpu::PollType::Wait);
        let bytes = buffer.slice(..).get_mapped_range().to_vec();
        bytes
    }
}
