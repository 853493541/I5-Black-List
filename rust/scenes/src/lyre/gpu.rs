//! Lays 竖琴清风's frames on with wgpu, offscreen: its pictures uploaded once as textures, then for each
//! frame one quad per thing laid on (lyre.wgsl), over the lobby, read back as RGBA bytes.

use wgpu::util::DeviceExt;

use super::art::Art;
use super::img::rgb;
use super::paint::{Frame, Item};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

#[repr(C)]
#[derive(Clone, Copy, Default, bytemuck::Pod, bytemuck::Zeroable)]
struct Quad {
    m: [f32; 4],
    n: [f32; 4],
    color: [f32; 4],
    kind: [f32; 4],
}

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    clips: wgpu::Texture,
    pics: Vec<wgpu::BindGroup>,
    sizes: Vec<[f32; 2]>,
    size: wgpu::Buffer,
    width: u32,
    height: u32,
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

impl Renderer {
    /// A renderer for frames of width x height over `lobby` (RGBA bytes), with the scene's pictures.
    pub fn new(width: u32, height: u32, lobby: &[u8], art: &Art) -> Result<Self, String> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).map_err(|e| e.to_string())?;
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("lyre.wgsl").into()) });
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
        let usage = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST;
        let upload = |w: u32, h: u32, bytes: &[u8]| {
            let tex = texture(&device, w, h, usage);
            queue.write_texture(tex.as_image_copy(), bytes, wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(w.max(1) * 4), rows_per_image: None }, tex.size());
            tex
        };
        let lobby_tex = upload(width, height, lobby);
        let layout = pipeline.get_bind_group_layout(1);
        let pics = art
            .store
            .iter()
            .map(|p| {
                let bytes: Vec<u8> = if p.px.is_empty() { vec![0; 4] } else { p.px.iter().flatten().copied().collect() };
                let view = upload(p.w.max(1) as u32, p.h.max(1) as u32, &bytes).create_view(&Default::default());
                device.create_bind_group(&wgpu::BindGroupDescriptor { label: None, layout: &layout, entries: &[wgpu::BindGroupEntry { binding: 0, resource: wgpu::BindingResource::TextureView(&view) }] })
            })
            .collect();
        let sizes = art.store.iter().map(|p| [p.w as f32, p.h as f32]).collect();
        let target = texture(&device, width, height, wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC);
        let clips = texture(&device, width, height, usage);
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self { device, queue, pipeline, target, lobby: lobby_tex.create_view(&Default::default()), clips, pics, sizes, size, width, height, adapter })
    }

    /// Draws one frame and waits until the chip is done.
    pub fn render(&self, frame: &Frame) {
        if frame.clips.iter().any(Option::is_some) {
            let n = (self.width * self.height) as usize;
            let mut bytes = vec![0u8; n * 4];
            for (ch, clip) in frame.clips.iter().enumerate() {
                if let Some(c) = clip {
                    for i in 0..n.min(c.v.len()) {
                        bytes[i * 4 + ch] = (c.v[i] * 255.0 + 0.5) as u8;
                    }
                }
            }
            self.queue.write_texture(self.clips.as_image_copy(), &bytes, wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(self.width * 4), rows_per_image: None }, self.clips.size());
        }
        let mut quads = vec![Quad { kind: [2.0, 0.0, 0.0, 0.0], ..Default::default() }];
        let mut pics = vec![0usize];
        for item in &frame.items {
            match *item {
                Item::Pic { id, m, alpha, clip } => {
                    let [w, h] = self.sizes[id];
                    quads.push(Quad {
                        m: [m[0] as f32, m[1] as f32, m[2] as f32, m[3] as f32],
                        n: [m[4] as f32, m[5] as f32, w, h],
                        color: [0.0, 0.0, 0.0, alpha.min(1.0) as f32],
                        kind: [0.0, clip as f32, 0.0, 0.0],
                    });
                    pics.push(id);
                }
                Item::Dot { x, y, r, color, alpha } => {
                    let c = rgb(color);
                    quads.push(Quad { n: [x as f32, y as f32, r as f32, 0.0], color: [c[0], c[1], c[2], alpha as f32], kind: [1.0, 0.0, 0.0, 0.0], ..Default::default() });
                    pics.push(0);
                }
            }
        }
        let buffer = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&quads), usage: wgpu::BufferUsages::STORAGE });
        let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.pipeline.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: self.size.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: buffer.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: wgpu::BindingResource::TextureView(&self.lobby) },
                wgpu::BindGroupEntry { binding: 3, resource: wgpu::BindingResource::TextureView(&self.clips.create_view(&Default::default())) },
            ],
        });
        let view = self.target.create_view(&Default::default());
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
            for (i, id) in pics.iter().enumerate() {
                pass.set_bind_group(1, &self.pics[*id], &[]);
                pass.draw(0..6, i as u32..i as u32 + 1);
            }
        }
        self.queue.submit([encoder.finish()]);
        let _ = self.device.poll(wgpu::PollType::Wait);
    }

    /// The last frame as RGBA bytes.
    pub fn read(&self) -> Vec<u8> {
        crate::render::read(&self.device, &self.queue, &self.target)
    }
}
