//! The fallback: each frame drawn offscreen, read back from the GPU, and handed to
//! UpdateLayeredWindow as a premultiplied, top-down BGRA DIB. The same DIB copies the screen (`capture`).

use std::ffi::c_void;

use scenes::prim::Frame;
use windows::Win32::Foundation::{COLORREF, HWND, POINT, SIZE};
use windows::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, GetDC, ReleaseDC, SelectObject,
    AC_SRC_ALPHA, AC_SRC_OVER, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, BLENDFUNCTION, CAPTUREBLT, DIB_RGB_COLORS,
    HBITMAP, HDC, HGDIOBJ, SRCCOPY,
};
use windows::Win32::UI::WindowsAndMessaging::{UpdateLayeredWindow, ULW_ALPHA};

use crate::geom::ScreenRect;
use crate::paint::{Gpu, Offscreen, Painter};

/// GDI's byte order, premultiplied, as UpdateLayeredWindow wants it.
pub const FORMAT: wgpu::TextureFormat = wgpu::TextureFormat::Bgra8Unorm;

/// A top-down 32-bit DIB selected into a memory DC.
pub struct Dib {
    pub dc: HDC,
    bitmap: HBITMAP,
    old: HGDIOBJ,
    bits: *mut c_void,
    len: usize,
}

impl Dib {
    pub fn new(w: i32, h: i32) -> Result<Self, String> {
        let (w, h) = (w.max(1), h.max(1));
        let info = BITMAPINFO {
            bmiHeader: BITMAPINFOHEADER {
                biSize: size_of::<BITMAPINFOHEADER>() as u32,
                biWidth: w,
                // Negative: top-down rows, as the GPU reads them.
                biHeight: -h,
                biPlanes: 1,
                biBitCount: 32,
                biCompression: BI_RGB.0,
                ..Default::default()
            },
            ..Default::default()
        };
        let dc = unsafe { CreateCompatibleDC(None) };
        if dc.is_invalid() {
            return Err("CreateCompatibleDC failed".into());
        }
        let mut bits = std::ptr::null_mut();
        let bitmap = match unsafe { CreateDIBSection(Some(dc), &info, DIB_RGB_COLORS, &mut bits, None, 0) } {
            Ok(b) if !bits.is_null() => b,
            other => {
                let _ = unsafe { DeleteDC(dc) };
                return Err(format!("CreateDIBSection: {:?}", other.err()));
            }
        };
        let old = unsafe { SelectObject(dc, bitmap.into()) };
        Ok(Self { dc, bitmap, old, bits, len: (w * h * 4) as usize })
    }

    pub fn bytes(&mut self) -> &mut [u8] {
        // SAFETY: bits is the DIB section's own memory, w * h * 4 bytes, alive as long as the bitmap.
        unsafe { std::slice::from_raw_parts_mut(self.bits.cast::<u8>(), self.len) }
    }
}

impl Drop for Dib {
    fn drop(&mut self) {
        unsafe {
            SelectObject(self.dc, self.old);
            let _ = DeleteObject(self.bitmap.into());
            let _ = DeleteDC(self.dc);
        }
    }
}

/// The DIB's pixels on the layered window, its own alpha over what is under it.
pub fn update(hwnd: HWND, area: ScreenRect, dc: HDC) -> Result<(), String> {
    let blend = BLENDFUNCTION { BlendOp: AC_SRC_OVER as u8, BlendFlags: 0, SourceConstantAlpha: 255, AlphaFormat: AC_SRC_ALPHA as u8 };
    let (pos, size, origin) = (POINT { x: area[0], y: area[1] }, SIZE { cx: area[2], cy: area[3] }, POINT::default());
    unsafe {
        UpdateLayeredWindow(hwnd, None, Some(&pos), Some(&size), Some(dc), Some(&origin), COLORREF(0), Some(&blend), ULW_ALPHA)
    }
    .map_err(|e| e.to_string())
}

/// The desktop as it shows now over `area` (layered and composed windows included), BGRA top-down.
pub fn capture(area: ScreenRect) -> Result<Vec<u8>, String> {
    let mut dib = Dib::new(area[2], area[3])?;
    let screen = unsafe { GetDC(None) };
    if screen.is_invalid() {
        return Err("GetDC(screen) failed".into());
    }
    let copied = unsafe { BitBlt(dib.dc, 0, 0, area[2], area[3], Some(screen), area[0], area[1], SRCCOPY | CAPTUREBLT) };
    unsafe { ReleaseDC(None, screen) };
    copied.map_err(|e| format!("BitBlt: {e}"))?;
    Ok(dib.bytes().to_vec())
}

pub struct Layered {
    off: Offscreen,
    dib: Dib,
    last: Vec<u8>,
}

impl Layered {
    pub fn new(gpu: &Gpu, _hwnd: HWND, area: ScreenRect) -> Result<Self, String> {
        let (w, h) = (area[2].max(1), area[3].max(1));
        Ok(Self { off: Offscreen::new(gpu, w as u32, h as u32, FORMAT), dib: Dib::new(w, h)?, last: Vec::new() })
    }

    pub fn present(&mut self, gpu: &Gpu, painter: &Painter, frame: &Frame, hwnd: HWND, area: ScreenRect) -> Result<(), String> {
        painter.render(gpu, frame, &self.off.view);
        self.last = self.off.read(gpu);
        let bytes = self.dib.bytes();
        if self.last.len() != bytes.len() {
            return Err(format!("read {} bytes, want {}", self.last.len(), bytes.len()));
        }
        bytes.copy_from_slice(&self.last);
        update(hwnd, area, self.dib.dc)
    }

    pub fn last(&self) -> &[u8] {
        &self.last
    }
}
