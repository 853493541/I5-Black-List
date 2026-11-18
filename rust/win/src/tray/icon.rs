//! The tray icon picture: blacklist_detect/assets/app.ico, built into the program, and the size picked from it.

/// app.ico, the file Python's `_icon()` loads.
pub const APP_ICO: &[u8] = include_bytes!("../../../../blacklist_detect/assets/app.ico");

/// One picture in an .ico file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct IcoEntry {
    /// Width and height in pixels (a 0 in the file means 256).
    pub size: u32,
    pub bits: u16,
    pub offset: usize,
    pub len: usize,
}

/// The pictures in an .ico file, or None when it is not one (or an entry runs past the end).
pub fn entries(ico: &[u8]) -> Option<Vec<IcoEntry>> {
    let u16_at = |at: usize| ico.get(at..at + 2).map(|b| u16::from_le_bytes([b[0], b[1]]));
    let u32_at = |at: usize| ico.get(at..at + 4).map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]));
    if u16_at(0)? != 0 || u16_at(2)? != 1 {
        return None;
    }
    let count = usize::from(u16_at(4)?);
    let mut out = Vec::with_capacity(count);
    for i in 0..count {
        let at = 6 + 16 * i;
        let width = u32::from(*ico.get(at)?);
        let entry = IcoEntry {
            size: if width == 0 { 256 } else { width },
            bits: u16_at(at + 6)?,
            len: usize::try_from(u32_at(at + 8)?).ok()?,
            offset: usize::try_from(u32_at(at + 12)?).ok()?,
        };
        if entry.offset.checked_add(entry.len)? > ico.len() {
            return None;
        }
        out.push(entry);
    }
    Some(out)
}

/// The picture for a `size` px icon: the smallest at least that big, else the biggest. Windows scales it.
pub fn pick(ico: &[u8], size: u32) -> Option<&[u8]> {
    let all = entries(ico)?;
    let best = all
        .iter()
        .filter(|e| e.size >= size)
        .min_by_key(|e| (e.size, std::cmp::Reverse(e.bits)))
        .or_else(|| all.iter().max_by_key(|e| (e.size, e.bits)))?;
    ico.get(best.offset..best.offset + best.len)
}
