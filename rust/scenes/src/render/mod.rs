//! What every scene's renderer shares, folded here from the per-scene copies (see each scene's gpu.rs).
//!
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
