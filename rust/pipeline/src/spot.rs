//! Where the last lobby was (pipeline.LobbySpot), so the next check skips the search when the title looks as it did.

use lobby::{countdown_in, ready_in, Anchor, OcrLine, Rect};
use opencv::core::Mat;
use opencv::prelude::*;

use crate::engine::Engine;
use crate::image::{line_cut, pixels};
use crate::pixel::{mean_diff, thumb, Pixels};
use crate::Result;

/// The title as a small gray picture; the mean difference per pixel (0 to 255) under which it is still there.
pub const SPOT_THUMB: (usize, usize) = (96, 24);
pub const SPOT_STILL: f64 = 12.0;

/// The search's own anchor, the frame size, the title as a thumbnail, and where the countdown and 准备就绪 were.
#[derive(Debug, Clone, PartialEq)]
pub struct LobbySpot {
    pub size: (i32, i32),
    pub anchor: Anchor,
    pub thumb: Vec<f32>,
    pub lines: (Option<Rect>, Option<Rect>),
}

pub(crate) fn frame_thumb(rgb: &Mat, bbox: &Rect) -> Result<Vec<f32>> {
    let data = pixels(rgb)?;
    let px = Pixels { data: &data, width: rgb.cols() as usize, height: rgb.rows() as usize };
    Ok(thumb(&px, bbox, SPOT_THUMB))
}

/// _remember: the spot of a lobby found by searching, None without a title.
pub fn remember(frame: &Mat, anchor: &Anchor, lines: &[OcrLine]) -> Result<Option<LobbySpot>> {
    let Some(title) = anchor.title_box else { return Ok(None) };
    let ready = lines.iter().find(|line| ready_in(&line.text).is_some()).map(|line| line.bbox);
    Ok(Some(LobbySpot {
        size: (frame.rows(), frame.cols()),
        anchor: anchor.clone(),
        thumb: frame_thumb(frame, &title)?,
        lines: (anchor.countdown_box, ready),
    }))
}

fn missing() -> Anchor {
    Anchor { reason: crate::check::NO_LOBBY.to_string(), ..Anchor::default() }
}

/// _at_spot: the lobby where it was last time, when its title looks as it did; only the countdown and 准备就绪 are
/// read again.
pub fn at_spot(engine: &mut Engine, rgb: &Mat, spot: &LobbySpot) -> Result<Anchor> {
    let Some(title) = spot.anchor.title_box else { return Ok(missing()) };
    if mean_diff(&frame_thumb(rgb, &title)?, &spot.thumb) > SPOT_STILL {
        return Ok(missing());
    }
    let boxes: Vec<Rect> = [spot.lines.0, spot.lines.1].into_iter().flatten().collect();
    let cuts = boxes.iter().map(|b| line_cut(rgb, b)).collect::<Result<Vec<_>>>()?;
    let read = if cuts.is_empty() { Vec::new() } else { engine.read_crops(&cuts)? };
    // dict(zip(boxes, texts)): the last text read for a box wins.
    let text_of = |wanted: &Rect| -> String {
        boxes.iter().zip(&read).filter(|(b, _)| *b == wanted).map(|(_, r)| r.0.clone()).next_back().unwrap_or_default()
    };
    let mut anchor = spot.anchor.clone();
    anchor.countdown_seconds = spot.lines.0.and_then(|b| countdown_in(&text_of(&b)));
    anchor.ready_count = spot.lines.1.and_then(|b| ready_in(&text_of(&b)));
    Ok(anchor)
}
