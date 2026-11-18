//! The cyber scene's renderer: the lobby, an atlas of the pictures made once, the night's wash and
//! the panels' layers as textures; each run of shapes drawn in one instanced call with its blend.

use wgpu::util::DeviceExt;

use super::canvas::{Blend, Canvas, Prim, Src};
use super::light::Pic;

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;
/// The textures that can be drawn into: the screen, the wash and the two layers.
const TARGETS: usize = 5;

/// The pictures packed into one texture, a texel of each picture's edge repeated round it.
pub struct Atlas {
    pub w: usize,
    pub h: usize,
    pub px: Vec<u8>,
    x: usize,
    y: usize,
    row: usize,
}

impl Atlas {
    pub fn new(w: usize, h: usize) -> Self {
        Self { w, h, px: vec![0; w * h * 4], x: 0, y: 0, row: 0 }
    }

    /// Where pic now sits, in texels.
    pub fn add(&mut self, pic: &Pic) -> Src {
        let (pw, ph) = (pic.w + 2, pic.h + 2);
        if self.x + pw > self.w {
            self.x = 0;
            self.y += self.row;
            self.row = 0;
        }
        assert!(self.y + ph <= self.h, "atlas full");
        for y in 0..ph {
            for x in 0..pw {
                let (sx, sy) = (x.saturating_sub(1).min(pic.w - 1), y.saturating_sub(1).min(pic.h - 1));
                let from = (sy * pic.w + sx) * 4;
                let to = ((self.y + y) * self.w + self.x + x) * 4;
                self.px[to..to + 4].copy_from_slice(&pic.px[from..from + 4]);
            }
        }
        let at = [(self.x + 1) as f64, (self.y + 1) as f64, pic.w as f64, pic.h as f64];
        self.x += pw;
        self.row = self.row.max(ph);
        at
    }
}

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipelines: [wgpu::RenderPipeline; 4],
    /// lobby, atlas, wash, layer A, layer B
    textures: Vec<wgpu::Texture>,
    target: wgpu::Texture,
    blank: wgpu::TextureView,
    sampler: wgpu::Sampler,
    size: wgpu::Buffer,
    width: u32,
    height: u32,
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

fn blend_state(b: Blend) -> wgpu::BlendState {
    use wgpu::{BlendComponent as C, BlendFactor as F, BlendOperation as O};
    let c = |s, d| C { src_factor: s, dst_factor: d, operation: O::Add };
    match b {
        Blend::Over => wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING,
        Blend::Plus => wgpu::BlendState { color: c(F::One, F::One), alpha: c(F::One, F::One) },
        Blend::Atop => wgpu::BlendState { color: c(F::DstAlpha, F::OneMinusSrcAlpha), alpha: c(F::Zero, F::One) },
        Blend::Out => wgpu::BlendState { color: c(F::Zero, F::OneMinusSrcAlpha), alpha: c(F::Zero, F::OneMinusSrcAlpha) },
    }
}

impl Renderer {
    pub fn new(width: u32, height: u32, lobby: &[u8], atlas: &Atlas) -> Result<Self, String> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).map_err(|e| e.to_string())?;
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("cyber.wgsl").into()) });
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: None,
            entries: &(0..9u32)
                .map(|binding| wgpu::BindGroupLayoutEntry {
                    binding,
                    visibility: wgpu::ShaderStages::VERTEX_FRAGMENT,
                    ty: match binding {
                        0 | 1 => wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Storage { read_only: true }, has_dynamic_offset: false, min_binding_size: None },
                        2 => wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Uniform, has_dynamic_offset: false, min_binding_size: None },
                        3 => wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                        _ => wgpu::BindingType::Texture { sample_type: wgpu::TextureSampleType::Float { filterable: true }, view_dimension: wgpu::TextureViewDimension::D2, multisampled: false },
                    },
                    count: None,
                })
                .collect::<Vec<_>>(),
        });
        let pipe_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor { label: None, bind_group_layouts: &[&layout], push_constant_ranges: &[] });
        let pipelines = [Blend::Over, Blend::Plus, Blend::Atop, Blend::Out].map(|b| {
            device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
                label: None,
                layout: Some(&pipe_layout),
                vertex: wgpu::VertexState { module: &shader, entry_point: Some("vs"), compilation_options: Default::default(), buffers: &[] },
                fragment: Some(wgpu::FragmentState {
                    module: &shader,
                    entry_point: Some("fs"),
                    compilation_options: Default::default(),
                    targets: &[Some(wgpu::ColorTargetState { format: FORMAT, blend: Some(blend_state(b)), write_mask: wgpu::ColorWrites::ALL })],
                }),
                primitive: wgpu::PrimitiveState::default(),
                depth_stencil: None,
                multisample: wgpu::MultisampleState::default(),
                multiview: None,
                cache: None,
            })
        });
        let read = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST;
        let drawn = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::RENDER_ATTACHMENT;
        let upload = |tex: &wgpu::Texture, bytes: &[u8], w: u32| {
            queue.write_texture(tex.as_image_copy(), bytes, wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w * 4), rows_per_image: None }, tex.size());
        };
        let lobby_tex = texture(&device, width, height, read);
        upload(&lobby_tex, lobby, width);
        let atlas_tex = texture(&device, atlas.w as u32, atlas.h as u32, read);
        upload(&atlas_tex, &atlas.px, atlas.w as u32);
        let mut textures = vec![lobby_tex, atlas_tex];
        textures.extend((0..3).map(|_| texture(&device, width, height, drawn)));
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let blank = texture(&device, 1, 1, read).create_view(&Default::default());
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor { mag_filter: wgpu::FilterMode::Linear, min_filter: wgpu::FilterMode::Linear, ..Default::default() });
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self { device, queue, pipelines, textures, target, blank, sampler, size, width, height, adapter })
    }

    /// Draws canvas: the screen is left in the target to read; the wash and layers stay as drawn.
    pub fn render(&self, canvas: &Canvas) {
        let storage = |bytes: &[u8]| self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytes, usage: wgpu::BufferUsages::STORAGE });
        let one = [Prim::default()];
        let prims = storage(bytemuck::cast_slice(if canvas.prims.is_empty() { &one } else { &canvas.prims }));
        let none = [[0.0f32; 2]];
        let points = storage(bytemuck::cast_slice(if canvas.points.is_empty() { &none } else { &canvas.points }));
        let views: Vec<wgpu::TextureView> = self.textures.iter().map(|t| t.create_view(&Default::default())).collect();
        // One bind group per target: the texture drawn into is not read in its own pass.
        let groups: Vec<wgpu::BindGroup> = (0..TARGETS)
            .map(|target| {
                let mut entries = vec![
                    wgpu::BindGroupEntry { binding: 0, resource: prims.as_entire_binding() },
                    wgpu::BindGroupEntry { binding: 1, resource: points.as_entire_binding() },
                    wgpu::BindGroupEntry { binding: 2, resource: self.size.as_entire_binding() },
                    wgpu::BindGroupEntry { binding: 3, resource: wgpu::BindingResource::Sampler(&self.sampler) },
                ];
                for (i, view) in views.iter().enumerate() {
                    let own = target > 0 && i == target;
                    entries.push(wgpu::BindGroupEntry { binding: 4 + i as u32, resource: wgpu::BindingResource::TextureView(if own { &self.blank } else { view }) });
                }
                self.device.create_bind_group(&wgpu::BindGroupDescriptor { label: None, layout: &self.pipelines[0].get_bind_group_layout(0), entries: &entries })
            })
            .collect();
        let screen = self.target.create_view(&Default::default());
        let mut encoder = self.device.create_command_encoder(&Default::default());
        let mut i = 0;
        while i < canvas.runs.len() {
            let target = canvas.runs[i].target as usize;
            let mut j = i + 1;
            while j < canvas.runs.len() && canvas.runs[j].target as usize == target && !canvas.runs[j].clear {
                j += 1;
            }
            let view = if target == 0 { &screen } else { &views[target] };
            let load = if canvas.runs[i].clear { wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT) } else { wgpu::LoadOp::Load };
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment { view, resolve_target: None, ops: wgpu::Operations { load, store: wgpu::StoreOp::Store } })],
                ..Default::default()
            });
            pass.set_bind_group(0, &groups[target], &[]);
            for run in &canvas.runs[i..j] {
                pass.set_pipeline(&self.pipelines[run.blend as usize]);
                pass.draw(0..6, run.start..run.end);
            }
            drop(pass);
            i = j;
        }
        self.queue.submit([encoder.finish()]);
        let _ = self.device.poll(wgpu::PollType::Wait);
    }

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
