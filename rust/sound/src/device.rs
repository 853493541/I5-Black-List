//! Windows' speakers through rodio. The stream lives on a thread of its own (rodio's stream cannot move between
//! threads); it is opened on the first sound heard, never at start, and never in tests (the Gate holds it back).

use std::sync::mpsc::{channel, Sender};

use crate::music::Output;
use crate::tunes::Clip;

#[derive(Default)]
pub struct Speakers {
    tx: Option<Sender<Option<Clip>>>,
}

impl Output for Speakers {
    fn play(&mut self, clip: Option<Clip>) {
        if self.tx.is_none() {
            let (tx, rx) = channel::<Option<Clip>>();
            let spawned = std::thread::Builder::new().name("sound".into()).spawn(move || {
                // No speakers: every sound is dropped, as winsound plays nothing there.
                let Ok((_stream, handle)) = rodio::OutputStream::try_default() else {
                    while rx.recv().is_ok() {}
                    return;
                };
                let mut current: Option<rodio::Sink> = None;
                while let Ok(next) = rx.recv() {
                    // A new sound stops the one playing, as winsound's SND_ASYNC does.
                    drop(current.take());
                    if let Some(clip) = next {
                        if let Ok(sink) = rodio::Sink::try_new(&handle) {
                            sink.append(rodio::buffer::SamplesBuffer::new(clip.channels, clip.rate, clip.samples));
                            current = Some(sink);
                        }
                    }
                }
            });
            if spawned.is_err() {
                return;
            }
            self.tx = Some(tx);
        }
        if let Some(tx) = &self.tx {
            let _ = tx.send(clip);
        }
    }
}
