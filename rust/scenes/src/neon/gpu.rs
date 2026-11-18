//! Draws 霓虹都市's frames with wgpu, offscreen: its pictures in one atlas texture, every shape and
//! picture one instanced quad, in runs drawn over (source-over) or added (Plus), read back as RGBA.

use wgpu::util::DeviceExt;

use super::frame::{Atlas, Frame, Prim, FADED};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    over: wgpu::RenderPipeline,
    plus: wgpu::RenderPipeline,
    /// The frame as it was before a FADED run.
    under: wgpu::Texture,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    atlas: wgpu::TextureView,
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
    /// A renderer for frames of width x height (width a multiple of 64) over `lobby` (RGBA bytes of
    /// that size), with the scene's pictures in `atlas` and the bare gap (x, y, w, h) a wash leaves.
    pub fn new(width: u32, height: u32, lobby: &[u8], atlas: &Atlas, gap: [f64; 4]) -> Result<Self, String> {
        Self::on(&crate::render::open()?, width, height, lobby, atlas, gap)
    }

    /// The same on a given device (the stage's, in the app).
    pub fn on(chip: &crate::render::Chip, width: u32, height: u32, lobby: &[u8], atlas: &Atlas, gap: [f64; 4]) -> Result<Self, String> {
        let (device, queue, info) = (chip.device.clone(), chip.queue.clone(), chip.info.clone());
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("neon.wgsl").into()) });
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: None,
            entries: &[
                entry(0, wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Storage { read_only: true }, has_dynamic_offset: false, min_binding_size: None }),
                entry(1, wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Storage { read_only: true }, has_dynamic_offset: false, min_binding_size: None }),
                entry(2, tex_binding()),
                entry(3, tex_binding()),
                entry(4, wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Uniform, has_dynamic_offset: false, min_binding_size: None }),
                entry(5, tex_binding()),
            ],
        });
        let pl = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor { label: None, bind_group_layouts: &[&layout], push_constant_ranges: &[] });
        let add = wgpu::BlendComponent { src_factor: wgpu::BlendFactor::One, dst_factor: wgpu::BlendFactor::One, operation: wgpu::BlendOperation::Add };
        let make = |blend: wgpu::BlendState| {
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: None,
                layout: Some(&pl),
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
            })
        };
        let over = make(wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING);
        let plus = make(wgpu::BlendState { color: add, alpha: add });
        let lobby = upload(&device, &queue, width, height, lobby);
        let atlas = upload(&device, &queue, atlas.w, atlas.h, &atlas.bytes);
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let under = texture(&device, width, height, wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST);
        let dims = [width as f32, height as f32, 0.0, 0.0, gap[0] as f32, gap[1] as f32, gap[2] as f32, gap[3] as f32];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self { device, queue, over, plus, under, target, lobby, atlas, size, adapter })
    }

    /// Draws one frame and waits until the chip is done.
    pub fn render(&self, frame: &Frame) {
        let storage = |bytes: &[u8]| self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage: wgpu::BufferUsages::STORAGE });
        let one = [Prim::default()];
        let prims = storage(bytemuck::cast_slice(if frame.prims.is_empty() { &one } else { &frame.prims }));
        let none = [[0.0f32; 2]];
        let points = storage(bytemuck::cast_slice(if frame.points.is_empty() { &none } else { &frame.points }));
        let under = self.under.create_view(&Default::default());
        let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.over.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: prims.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: points.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: wgpu::BindingResource::TextureView(&self.lobby) },
                wgpu::BindGroupEntry { binding: 3, resource: wgpu::BindingResource::TextureView(&self.atlas) },
                wgpu::BindGroupEntry { binding: 4, resource: self.size.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 5, resource: wgpu::BindingResource::TextureView(&under) },
            ],
        });
        let view = self.target.create_view(&Default::default());
        let mut encoder = self.device.create_command_encoder(&Default::default());
        // One pass per stretch of runs; a FADED run starts a new one, after the frame so far is copied for it to read.
        let mut i = 0;
        while i == 0 || i < frame.runs.len() {
            let mut j = i + 1;
            while j < frame.runs.len() && frame.runs[j].2 != FADED {
                j += 1;
            }
            if frame.runs.get(i).is_some_and(|r| r.2 == FADED) {
                encoder.copy_texture_to_texture(self.target.as_image_copy(), self.under.as_image_copy(), self.target.size());
            }
            let load = if i == 0 { wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT) } else { wgpu::LoadOp::Load };
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment { view: &view, resolve_target: None, ops: wgpu::Operations { load, store: wgpu::StoreOp::Store } })],
                ..Default::default()
            });
            pass.set_bind_group(0, &group, &[]);
            for &(first, end, how) in frame.runs.get(i..j.min(frame.runs.len())).unwrap_or(&[]) {
                pass.set_pipeline(if how == 0 { &self.over } else { &self.plus });
                pass.draw(0..6, first..end);
            }
            drop(pass);
            i = j;
        }
        self.queue.submit([encoder.finish()]);
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

fn entry(binding: u32, ty: wgpu::BindingType) -> wgpu::BindGroupLayoutEntry {
    wgpu::BindGroupLayoutEntry { binding, visibility: wgpu::ShaderStages::VERTEX_FRAGMENT, ty, count: None }
}

fn tex_binding() -> wgpu::BindingType {
    wgpu::BindingType::Texture { sample_type: wgpu::TextureSampleType::Float { filterable: false }, view_dimension: wgpu::TextureViewDimension::D2, multisampled: false }
}
