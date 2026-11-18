//! Draws 冰蓝极光 with wgpu, offscreen (copied from crate::gpu and grown to this scene's passes): the
//! wash once, then per frame the aurora at half size (aurora.wgsl), the light inside the heart at a
//! quarter size, and the frame over the lobby (ice.wgsl), laid over or added shape by shape.

use wgpu::util::DeviceExt;

use super::prim::{Frame, Prim, ADD};
use super::{Ice, IceFrame};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    layout: wgpu::BindGroupLayout,
    over: wgpu::RenderPipeline,
    add: wgpu::RenderPipeline,
    aurora_pipe: wgpu::RenderPipeline,
    sampler: wgpu::Sampler,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    wash: wgpu::Texture,
    aurora: wgpu::Texture,
    glass: wgpu::TextureView,
    blank: wgpu::TextureView,
    width: u32,
    height: u32,
    /// The adapter's name and kind, e.g. "llvmpipe (LLVM ...), Cpu".
    pub adapter: String,
}

fn texture(device: &wgpu::Device, w: u32, h: u32, usage: wgpu::TextureUsages) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: None,
        size: wgpu::Extent3d { width: w.max(1), height: h.max(1), depth_or_array_layers: 1 },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format: FORMAT,
        usage,
        view_formats: &[],
    })
}

fn entry(binding: u32, ty: wgpu::BindingType) -> wgpu::BindGroupLayoutEntry {
    wgpu::BindGroupLayoutEntry { binding, visibility: wgpu::ShaderStages::VERTEX_FRAGMENT, ty, count: None }
}

fn pipeline(device: &wgpu::Device, layout: Option<&wgpu::PipelineLayout>, shader: &wgpu::ShaderModule, blend: Option<wgpu::BlendState>) -> wgpu::RenderPipeline {
    device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
        label: None,
        layout,
        vertex: wgpu::VertexState { module: shader, entry_point: Some("vs"), compilation_options: Default::default(), buffers: &[] },
        fragment: Some(wgpu::FragmentState {
            module: shader,
            entry_point: Some("fs"),
            compilation_options: Default::default(),
            targets: &[Some(wgpu::ColorTargetState { format: FORMAT, blend, write_mask: wgpu::ColorWrites::ALL })],
        }),
        primitive: wgpu::PrimitiveState::default(),
        depth_stencil: None,
        multisample: wgpu::MultisampleState::default(),
        multiview: None,
        cache: None,
    })
}

impl Renderer {
    /// A renderer for `scene` (its width a multiple of 64) over `lobby`, RGBA bytes of its size.
    pub fn new(scene: &Ice, lobby: &[u8]) -> Result<Self, String> {
        let (width, height) = (scene.width as u32, scene.height as u32);
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).map_err(|e| e.to_string())?;
        let storage = wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Storage { read_only: true }, has_dynamic_offset: false, min_binding_size: None };
        let tex = wgpu::BindingType::Texture { sample_type: wgpu::TextureSampleType::Float { filterable: true }, view_dimension: wgpu::TextureViewDimension::D2, multisampled: false };
        let uniform = wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Uniform, has_dynamic_offset: false, min_binding_size: None };
        let mut entries = vec![entry(0, storage), entry(1, storage)];
        entries.extend((2..7).map(|b| entry(b, tex)));
        entries.extend([entry(7, uniform), entry(8, wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering))]);
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor { label: None, entries: &entries });
        let pipe_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor { label: None, bind_group_layouts: &[&layout], push_constant_ranges: &[] });
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("ice.wgsl").into()) });
        let over = pipeline(&device, Some(&pipe_layout), &shader, Some(wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING));
        let sum = wgpu::BlendComponent { src_factor: wgpu::BlendFactor::One, dst_factor: wgpu::BlendFactor::One, operation: wgpu::BlendOperation::Add };
        let add = pipeline(&device, Some(&pipe_layout), &shader, Some(wgpu::BlendState { color: sum, alpha: sum }));
        let aurora_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("aurora.wgsl").into()) });
        let aurora_pipe = pipeline(&device, None, &aurora_shader, None);
        let linear = wgpu::FilterMode::Linear;
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor { mag_filter: linear, min_filter: linear, ..Default::default() });
        let usage = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST;
        let drawn = wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING;
        let upload = |w: u32, h: u32, bytes: &[u8]| {
            let t = texture(&device, w, h, usage);
            let layout = wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w * 4), rows_per_image: None };
            queue.write_texture(t.as_image_copy(), bytes, layout, t.size());
            t.create_view(&Default::default())
        };
        let lobby = upload(width, height, lobby);
        let (side, pixels) = super::glass::glass(scene.glass_px);
        let glass = upload(side as u32, side as u32, &pixels);
        let blank = upload(1, 1, &[0; 4]);
        let a = scene.paint(0.0).aurora.size;
        let aurora = texture(&device, a[0], a[1], drawn);
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let wash = texture(&device, width, height, drawn);
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        let r = Self { device, queue, layout, over, add, aurora_pipe, sampler, target, lobby, wash, aurora, glass, blank, width, height, adapter };
        r.shapes(&scene.wash(), &r.wash, [width, height], None);
        Ok(r)
    }

    /// Draws `frame`'s shapes onto `onto` (cleared first), `size` its pixels; `within` the light
    /// inside the heart, when the frame lays it on.
    fn shapes(&self, frame: &Frame, onto: &wgpu::Texture, size: [u32; 2], within: Option<&wgpu::TextureView>) {
        let init = |bytes: &[u8], usage| self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage });
        let one = [Prim::default()];
        let prims = init(bytemuck::cast_slice(if frame.prims.is_empty() { &one } else { &frame.prims }), wgpu::BufferUsages::STORAGE);
        let none = [[0.0f32; 2]];
        let points = init(bytemuck::cast_slice(if frame.points.is_empty() { &none } else { &frame.points }), wgpu::BufferUsages::STORAGE);
        let dims = init(bytemuck::cast_slice(&[size[0] as f32, size[1] as f32, 0.0, 0.0]), wgpu::BufferUsages::UNIFORM);
        let full = std::ptr::eq(onto, &self.target);
        let (wash, aurora) = (self.wash.create_view(&Default::default()), self.aurora.create_view(&Default::default()));
        let views = [&self.lobby, if full { &wash } else { &self.blank }, if full { &aurora } else { &self.blank }, &self.glass, within.unwrap_or(&self.blank)];
        let mut entries = vec![
            wgpu::BindGroupEntry { binding: 0, resource: prims.as_entire_binding() },
            wgpu::BindGroupEntry { binding: 1, resource: points.as_entire_binding() },
        ];
        entries.extend(views.iter().enumerate().map(|(i, v)| wgpu::BindGroupEntry { binding: i as u32 + 2, resource: wgpu::BindingResource::TextureView(v) }));
        entries.push(wgpu::BindGroupEntry { binding: 7, resource: dims.as_entire_binding() });
        entries.push(wgpu::BindGroupEntry { binding: 8, resource: wgpu::BindingResource::Sampler(&self.sampler) });
        let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor { label: None, layout: &self.layout, entries: &entries });
        let view = onto.create_view(&Default::default());
        let mut encoder = self.device.create_command_encoder(&Default::default());
        {
            let mut pass = begin(&mut encoder, &view);
            pass.set_bind_group(0, &group, &[]);
            let mut start = 0;
            while start < frame.prims.len() {
                let added = frame.prims[start].kind[3] & ADD != 0;
                let end = (start..frame.prims.len()).find(|&i| (frame.prims[i].kind[3] & ADD != 0) != added).unwrap_or(frame.prims.len());
                pass.set_pipeline(if added { &self.add } else { &self.over });
                pass.draw(0..6, start as u32..end as u32);
                start = end;
            }
        }
        self.queue.submit([encoder.finish()]);
    }

    fn aurora(&self, data: &[f32]) {
        let buffer = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(data), usage: wgpu::BufferUsages::STORAGE });
        let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.aurora_pipe.get_bind_group_layout(0),
            entries: &[wgpu::BindGroupEntry { binding: 0, resource: buffer.as_entire_binding() }],
        });
        let view = self.aurora.create_view(&Default::default());
        let mut encoder = self.device.create_command_encoder(&Default::default());
        {
            let mut pass = begin(&mut encoder, &view);
            pass.set_pipeline(&self.aurora_pipe);
            pass.set_bind_group(0, &group, &[]);
            pass.draw(0..3, 0..1);
        }
        self.queue.submit([encoder.finish()]);
    }

    /// Draws one frame and waits until the chip is done.
    pub fn render(&self, frame: &IceFrame) {
        if frame.aurora.drawn() {
            self.aurora(&frame.aurora.data);
        }
        let within = frame.within.as_ref().map(|(shapes, size)| {
            let t = texture(&self.device, size[0], size[1], wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING);
            self.shapes(shapes, &t, *size, None);
            t.create_view(&Default::default())
        });
        self.shapes(&frame.main, &self.target, [self.width, self.height], within.as_ref());
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
        let layout = wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(row), rows_per_image: None };
        encoder.copy_texture_to_buffer(self.target.as_image_copy(), wgpu::TexelCopyBufferInfo { buffer: &buffer, layout }, self.target.size());
        self.queue.submit([encoder.finish()]);
        buffer.slice(..).map_async(wgpu::MapMode::Read, |_| {});
        let _ = self.device.poll(wgpu::PollType::Wait);
        let bytes = buffer.slice(..).get_mapped_range().to_vec();
        bytes
    }
}

fn begin<'a>(encoder: &'a mut wgpu::CommandEncoder, view: &'a wgpu::TextureView) -> wgpu::RenderPass<'a> {
    encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
        label: None,
        color_attachments: &[Some(wgpu::RenderPassColorAttachment {
            view,
            resolve_target: None,
            ops: wgpu::Operations { load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT), store: wgpu::StoreOp::Store },
        })],
        ..Default::default()
    })
}
