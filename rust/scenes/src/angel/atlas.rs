//! The baked pictures packed into one texture, in shelves, with the gold's draw times beside them.

use super::px::Pic;

/// Where a picture is in the atlas: x, y, w, h in pixels.
pub type Region = [f32; 4];

pub struct Atlas {
    pub w: usize,
    pub h: usize,
    pub px: Vec<u8>,
    pub times: Vec<f32>,
    shelf: (usize, usize, usize),
}

impl Atlas {
    pub fn new(w: usize) -> Self {
        Self { w, h: 0, px: Vec::new(), times: Vec::new(), shelf: (0, 0, 0) }
    }

    /// Puts a picture in, with its draw times (one a pixel) if it has them.
    pub fn put(&mut self, pic: &Pic, times: Option<&[f32]>) -> Region {
        let (mut x, mut y, mut tall) = self.shelf;
        if x + pic.w > self.w {
            (x, y, tall) = (0, y + tall, 0);
        }
        tall = tall.max(pic.h);
        if y + tall > self.h {
            self.h = y + tall;
            self.px.resize(self.w * self.h * 4, 0);
            self.times.resize(self.w * self.h, f32::MAX);
        }
        for row in 0..pic.h {
            let at = ((y + row) * self.w + x) * 4;
            self.px[at..at + pic.w * 4].copy_from_slice(&pic.px[row * pic.w * 4..(row + 1) * pic.w * 4]);
            if let Some(t) = times {
                let at = (y + row) * self.w + x;
                self.times[at..at + pic.w].copy_from_slice(&t[row * pic.w..(row + 1) * pic.w]);
            }
        }
        self.shelf = (x + pic.w, y, tall);
        [x as f32, y as f32, pic.w as f32, pic.h as f32]
    }
}
