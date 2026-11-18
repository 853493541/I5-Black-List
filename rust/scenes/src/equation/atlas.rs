//! Every picture the scene works out once (the equations' letters and glow, the heart's light, the
//! drifting symbols) packed into one texture, row by row, a 2 pixel gutter between them.

use super::light::Image;

/// Where a picture sits in the atlas, in its pixels.
#[derive(Clone, Copy, Debug, Default)]
pub struct Tile {
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
}

pub struct Atlas {
    pub width: usize,
    pub height: usize,
    pub rgba: Vec<u8>,
    x: usize,
    y: usize,
    row: usize,
}

const GUTTER: usize = 2;

impl Atlas {
    pub fn new(width: usize) -> Self {
        Self { width, height: 0, rgba: Vec::new(), x: 0, y: 0, row: 0 }
    }

    pub fn add(&mut self, img: &Image) -> Tile {
        let (w, h) = (img.w.min(self.width - GUTTER), img.h);
        if self.x + w + GUTTER > self.width {
            self.y += self.row + GUTTER;
            self.x = 0;
            self.row = 0;
        }
        let (x, y) = (self.x, self.y);
        self.height = self.height.max(y + h + GUTTER);
        self.rgba.resize(self.width * self.height * 4, 0);
        for row in 0..h {
            let from = &img.rgba[row * img.w * 4..row * img.w * 4 + w * 4];
            let at = ((y + row) * self.width + x) * 4;
            self.rgba[at..at + w * 4].copy_from_slice(from);
        }
        self.x += w + GUTTER;
        self.row = self.row.max(h);
        Tile { x: x as f64, y: y as f64, w: w as f64, h: h as f64 }
    }

    /// A coverage mask (0..1), kept in every channel.
    pub fn add_mask(&mut self, cover: &[f32], w: usize, h: usize) -> Tile {
        let rgba = cover.iter().flat_map(|&c| [(c * 255.0 + 0.5) as u8; 4]).collect();
        self.add(&Image { w, h, rgba })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packs_side_by_side_then_wraps() {
        let mut atlas = Atlas::new(16);
        let img = Image { w: 6, h: 3, rgba: vec![9; 6 * 3 * 4] };
        let a = atlas.add(&img);
        let b = atlas.add(&img);
        let c = atlas.add(&img);
        assert_eq!((a.x, b.x, c.x, c.y), (0.0, 8.0, 0.0, 5.0));
        assert_eq!(atlas.rgba[((5 * 16) * 4) as usize], 9);
    }
}
