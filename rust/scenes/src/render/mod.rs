//! What every scene's renderer shares, folded here from the per-scene copies (see each scene's gpu.rs).
//!
//! - `Chip`: the device a renderer draws on: its own (`open`, the tools and checks) or the stage's (the app, so
//!   frames go to the window by a copy on the chip, `deliver`).
//! - `read`: reading a drawn texture back as packed RGBA rows, at any width (rows padded for the copy).

/// The texture's bytes, 4 per pixel, rows packed, waiting for the chip. Works at any width: the copy's
/// rows are padded to wgpu's 256-byte alignment and the padding dropped.
pub fn read(device: &wgpu::Device, queue: &wgpu::Queue, texture: &wgpu::Texture) -> Vec<u8> {
    let size = texture.size();
    let row = size.width * 4;
    let padded = row.div_ceil(wgpu::COPY_BYTES_PER_ROW_ALIGNMENT) * wgpu::COPY_BYTES_PER_ROW_ALIGNMENT;
    let buffer = device.create_buffer(&wgpu::BufferDescriptor {
        label: None,
        size: u64::from(padded * size.height),
        usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
        mapped_at_creation: false,
    });
    let mut encoder = device.create_command_encoder(&Default::default());
    let layout = wgpu::TexelCopyBufferLayout { offset: 0, bytes_per_row: Some(padded), rows_per_image: None };
    encoder.copy_texture_to_buffer(texture.as_image_copy(), wgpu::TexelCopyBufferInfo { buffer: &buffer, layout }, size);
    queue.submit([encoder.finish()]);
    buffer.slice(..).map_async(wgpu::MapMode::Read, |_| {});
    let _ = device.poll(wgpu::PollType::Wait);
    let mapped = buffer.slice(..).get_mapped_range();
    if padded == row {
        return mapped.to_vec();
    }
    mapped.chunks(padded as usize).flat_map(|line| &line[..row as usize]).copied().collect()
}

/// A device, its queue and what the adapter is.
#[derive(Clone)]
pub struct Chip {
    pub device: wgpu::Device,
    pub queue: wgpu::Queue,
    pub info: wgpu::AdapterInfo,
}

/// A device of its own on the system's adapter, with the adapter's own limits (neon's atlas needs them).
pub fn open() -> Result<Chip, String> {
    let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor { backends: wgpu::Backends::all(), ..Default::default() });
    let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default())).map_err(|e| e.to_string())?;
    let desc = wgpu::DeviceDescriptor { required_limits: adapter.limits(), ..Default::default() };
    let (device, queue) = pollster::block_on(adapter.request_device(&desc)).map_err(|e| e.to_string())?;
    Ok(Chip { device, queue, info: adapter.get_info() })
}

/// Where a drawn frame goes: back to the CPU as RGBA bytes, or copied on the chip into a texture of the
/// same device, size and format (the stage's still picture).
pub enum Out<'a> {
    Read(&'a mut Vec<u8>),
    Copy(&'a wgpu::Texture),
}

/// Hands the frame drawn in `target` to `out`.
pub fn deliver(device: &wgpu::Device, queue: &wgpu::Queue, target: &wgpu::Texture, out: Out) {
    match out {
        Out::Read(bytes) => *bytes = read(device, queue, target),
        Out::Copy(onto) => {
            let mut encoder = device.create_command_encoder(&Default::default());
            encoder.copy_texture_to_texture(target.as_image_copy(), onto.as_image_copy(), target.size());
            queue.submit([encoder.finish()]);
        }
    }
}
