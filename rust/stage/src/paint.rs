//! Draws a scene's frames with the scenes crate's shader onto any texture: an offscreen one (tests,
//! the layered-window fallback) or a swap chain's (the DirectComposition window). Unlike
//! scenes::gpu::Renderer it shares the device with a surface, takes the surface's format, and over
//! the game leaves the lobby picture out (the game shows through), drawing on transparent.

use scenes::prim::{Frame, Prim, PICTURE};
use wgpu::util::DeviceExt;

/// Which adapter to ask for.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Adapter {
    /// The system's choice (high performance first).
    Default,
    /// The software one: WARP on Windows (DX12), llvmpipe / lavapipe elsewhere.
    Software,
}

/// An instance, adapter, device and queue. On Windows only DX12 (DirectComposition needs it).
pub struct Gpu {
    pub instance: wgpu::Instance,
    pub adapter: wgpu::Adapter,
    pub device: wgpu::Device,
    pub queue: wgpu::Queue,
}

impl Gpu {
    pub fn new(which: Adapter) -> Result<Self, String> {
        let backends = if cfg!(windows) {
            wgpu::Backends::DX12
        } else {
            wgpu::Backends::all()
        };
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends,
            ..Default::default()
        });
        let options = wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            force_fallback_adapter: which == Adapter::Software,
            compatible_surface: None,
        };
        let adapter =
            pollster::block_on(instance.request_adapter(&options)).map_err(|e| e.to_string())?;
        let (device, queue) =
            pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default()))
                .map_err(|e| e.to_string())?;
        Ok(Self {
            instance,
            adapter,
            device,
            queue,
        })
    }

    /// The adapter's name, kind and backend, e.g. "Microsoft Basic Render Driver (Cpu, Dx12)".
    pub fn name(&self) -> String {
        let info = self.adapter.get_info();
        format!("{} ({:?}, {:?})", info.name, info.device_type, info.backend)
    }
}

fn texture(
    device: &wgpu::Device,
    w: u32,
    h: u32,
    format: wgpu::TextureFormat,
    usage: wgpu::TextureUsages,
) -> wgpu::Texture {
    device.create_texture(&wgpu::TextureDescriptor {
        label: None,
        size: wgpu::Extent3d {
            width: w.max(1),
            height: h.max(1),
            depth_or_array_layers: 1,
        },
        mip_level_count: 1,
        sample_count: 1,
        dimension: wgpu::TextureDimension::D2,
        format,
        usage,
        view_formats: &[],
    })
}

/// The scene shader set up for one size and target format.
pub struct Painter {
    pipeline: wgpu::RenderPipeline,
    still_pipeline: wgpu::RenderPipeline,
    lobby: wgpu::TextureView,
    still: wgpu::Texture,
    blank: wgpu::TextureView,
    size: wgpu::Buffer,
    /// A lobby under the scene (previews): layer-0 pictures are kept.
    with_lobby: bool,
}

const STILL: wgpu::TextureFormat = wgpu::TextureFormat::Rgba8Unorm;

fn pipeline(
    device: &wgpu::Device,
    shader: &wgpu::ShaderModule,
    format: wgpu::TextureFormat,
) -> wgpu::RenderPipeline {
    device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
        label: None,
        layout: None,
        vertex: wgpu::VertexState {
            module: shader,
            entry_point: Some("vs"),
            compilation_options: Default::default(),
            buffers: &[],
        },
        fragment: Some(wgpu::FragmentState {
            module: shader,
            entry_point: Some("fs"),
            compilation_options: Default::default(),
            targets: &[Some(wgpu::ColorTargetState {
                format,
                blend: Some(wgpu::BlendState::PREMULTIPLIED_ALPHA_BLENDING),
                write_mask: wgpu::ColorWrites::ALL,
            })],
        }),
        primitive: wgpu::PrimitiveState::default(),
        depth_stencil: None,
        multisample: wgpu::MultisampleState::default(),
        multiview: None,
        cache: None,
    })
}

impl Painter {
    /// A painter for width x height frames in `format`; lobby: RGBA bytes of that size under the scene
    /// (a preview), or None over the game.
    pub fn new(
        gpu: &Gpu,
        width: u32,
        height: u32,
        format: wgpu::TextureFormat,
        lobby: Option<&[u8]>,
    ) -> Self {
        let device = &gpu.device;
        let source = wgpu::ShaderSource::Wgsl(include_str!("../../scenes/src/scene.wgsl").into());
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: None,
            source,
        });
        let usage = wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST;
        let lobby_tex = texture(device, width, height, STILL, usage);
        if let Some(bytes) = lobby {
            let layout = wgpu::TexelCopyBufferLayout {
                offset: 0,
                bytes_per_row: Some(width * 4),
                rows_per_image: None,
            };
            gpu.queue
                .write_texture(lobby_tex.as_image_copy(), bytes, layout, lobby_tex.size());
        }
        let still = texture(
            device,
            width,
            height,
            STILL,
            wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
        );
        let blank = texture(device, 1, 1, STILL, usage).create_view(&Default::default());
        let dims = [width as f32, height as f32, 0.0, 0.0];
        let size = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: None,
            contents: bytemuck::cast_slice(&dims),
            usage: wgpu::BufferUsages::UNIFORM,
        });
        Self {
            pipeline: pipeline(device, &shader, format),
            still_pipeline: pipeline(device, &shader, STILL),
            lobby: lobby_tex.create_view(&Default::default()),
            still,
            blank,
            size,
            with_lobby: lobby.is_some(),
        }
    }

    fn draw(
        &self,
        gpu: &Gpu,
        frame: &Frame,
        pipeline: &wgpu::RenderPipeline,
        onto: &wgpu::TextureView,
        still: &wgpu::TextureView,
    ) {
        let device = &gpu.device;
        let lobby_picture = |p: &Prim| p.kind[0] == PICTURE && p.s0[0] == 0.0;
        let prims: Vec<Prim> = frame
            .prims
            .iter()
            .copied()
            .filter(|p| self.with_lobby || !lobby_picture(p))
            .collect();
        let storage = |bytes: &[u8]| {
            device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: None,
                contents: bytes,
                usage: wgpu::BufferUsages::STORAGE,
            })
        };
        let one = [Prim::default()];
        let prim_buf = storage(bytemuck::cast_slice(if prims.is_empty() {
            &one
        } else {
            &prims
        }));
        let none = [[0.0f32; 2]];
        let points = storage(bytemuck::cast_slice(if frame.points.is_empty() {
            &none
        } else {
            &frame.points
        }));
        let group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &pipeline.get_bind_group_layout(0),
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: prim_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: points.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::TextureView(&self.lobby),
                },
                wgpu::BindGroupEntry {
                    binding: 3,
                    resource: wgpu::BindingResource::TextureView(still),
                },
                wgpu::BindGroupEntry {
                    binding: 4,
                    resource: self.size.as_entire_binding(),
                },
            ],
        });
        let mut encoder = device.create_command_encoder(&Default::default());
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: None,
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: onto,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::TRANSPARENT),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                ..Default::default()
            });
            pass.set_pipeline(pipeline);
            pass.set_bind_group(0, &group, &[]);
            pass.draw(0..6, 0..prims.len() as u32);
        }
        gpu.queue.submit([encoder.finish()]);
    }

    /// Draws the scene's still picture (layer 1) once.
    pub fn set_still(&self, gpu: &Gpu, frame: &Frame) {
        let view = self.still.create_view(&Default::default());
        self.draw(gpu, frame, &self.still_pipeline, &view, &self.blank);
    }

    /// Draws one frame onto `onto` (a view of a texture in this painter's format and size).
    pub fn render(&self, gpu: &Gpu, frame: &Frame, onto: &wgpu::TextureView) {
        let view = self.still.create_view(&Default::default());
        self.draw(gpu, frame, &self.pipeline, onto, &view);
    }
}

/// An offscreen target: frames drawn into it and read back as premultiplied bytes in its format.
pub struct Offscreen {
    pub texture: wgpu::Texture,
    pub view: wgpu::TextureView,
    width: u32,
    height: u32,
}

impl Offscreen {
    pub fn new(gpu: &Gpu, width: u32, height: u32, format: wgpu::TextureFormat) -> Self {
        let texture = texture(
            &gpu.device,
            width,
            height,
            format,
            wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
        );
        let view = texture.create_view(&Default::default());
        Self {
            texture,
            view,
            width,
            height,
        }
    }

    /// The last frame's bytes, 4 per pixel, rows packed, waiting for the chip.
    pub fn read(&self, gpu: &Gpu) -> Vec<u8> {
        let row = self.width * 4;
        let padded =
            row.div_ceil(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT) * wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
        let buffer = gpu.device.create_buffer(&wgpu::BufferDescriptor {
            label: None,
            size: u64::from(padded * self.height),
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut encoder = gpu.device.create_command_encoder(&Default::default());
        let layout = wgpu::TexelCopyBufferLayout {
            offset: 0,
            bytes_per_row: Some(padded),
            rows_per_image: None,
        };
        encoder.copy_texture_to_buffer(
            self.texture.as_image_copy(),
            wgpu::TexelCopyBufferInfo {
                buffer: &buffer,
                layout,
            },
            self.texture.size(),
        );
        gpu.queue.submit([encoder.finish()]);
        buffer.slice(..).map_async(wgpu::MapMode::Read, |_| {});
        let _ = gpu.device.poll(wgpu::PollType::Wait);
        let mapped = buffer.slice(..).get_mapped_range();
        mapped
            .chunks(padded as usize)
            .flat_map(|line| &line[..row as usize])
            .copied()
            .collect()
    }
}

/// Waits until the chip has drawn everything submitted.
pub fn finish(gpu: &Gpu) {
    let _ = gpu.device.poll(wgpu::PollType::Wait);
}
