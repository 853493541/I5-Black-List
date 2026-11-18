//! Draws 数学公式's frames on the graphics chip with wgpu, offscreen (the spike's gpu.rs, copied, with
//! the scene's atlas of pictures bound beside the lobby and the paper): one instanced draw of every
//! shape, read back as RGBA bytes. Without a GPU driver (here, in a container) it runs on lavapipe.

use wgpu::util::DeviceExt;

use super::atlas::Atlas;
use super::prim::{Frame, Prim};

const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

pub struct Renderer {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    target: wgpu::Texture,
    lobby: wgpu::TextureView,
    galaxy: wgpu::Texture,
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

impl Renderer {
    /// A renderer for frames of width x height (width a multiple of 64) over `lobby`, RGBA bytes of that size.
    pub fn new(width: u32, height: u32, lobby: &[u8], atlas: &Atlas) -> Result<Self, String> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
        let info = adapter.get_info();
        let (device, queue) = pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).map_err(|e| e.to_string())?;
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(include_str!("equation.wgsl").into()) });
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
        let (aw, ah) = (atlas.width as u32, (atlas.height as u32).max(1));
        let atlas_tex = texture(&device, aw, ah, usage);
        if atlas.height > 0 {
            queue.write_texture(
                atlas_tex.as_image_copy(),
                &atlas.rgba,
                wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(aw * 4), rows_per_image: None },
                atlas_tex.size(),
            );
        }
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: None, contents: bytemuck::cast_slice(&dims), usage: wgpu::BufferUsages::UNIFORM });
        let adapter = format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend);
        Ok(Self { device, queue, pipeline, target, lobby: lobby_tex.create_view(&Default::default()), galaxy, atlas: atlas_tex.create_view(&Default::default()), blank, size, adapter })
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

    /// Draws the scene's still layer (the paper) once, as the Python Wash does.
    pub fn set_paper(&self, frame: &Frame) {
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

#[cfg(test)]
mod tests {
    use super::super::atlas::Atlas;
    use super::super::prim::{solid, Frame};
    use super::Renderer;

    #[test]
    fn draws_a_dot_over_the_lobby() {
        let (w, h) = (64u32, 32u32);
        let lobby: Vec<u8> = (0..w * h).flat_map(|_| [0u8, 0, 255, 255]).collect();
        // No Vulkan, Metal or DX12 driver at all: nothing to test here.
        let Ok(gpu) = Renderer::new(w, h, &lobby, &Atlas::new(64)) else { return };
        let mut frame = Frame::new();
        frame.picture(0, [64.0, 32.0], [0.0; 4], 1.0);
        frame.circle(16.0, 16.0, 6.0, &solid("#ff0000", 0.5));
        gpu.set_paper(&Frame::new());
        gpu.render(&frame);
        let px = gpu.read();
        let at = |x: u32, y: u32| &px[((y * w + x) * 4) as usize..((y * w + x) * 4 + 4) as usize];
        assert_eq!(at(50, 16), [0, 0, 255, 255]);
        let mid = at(16, 16);
        assert!((127..=129).contains(&mid[0]) && (126..=129).contains(&mid[2]), "{mid:?}");
    }
}
