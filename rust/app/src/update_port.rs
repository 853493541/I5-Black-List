//! 发现新版本 / 正在更新 (ui_update.UpdateDialog): the dialog for the release the runner found, its buttons, and the
//! download's progress on its bar, carried out through the runner.

use crate::notices::update::{Effect, UpdateDialog};
use crate::notices::view::fill_update;
use crate::UpdateDialogWindow;
use app::wiring::runner::Runner;
use app::wiring::updates::Install;
use slint::ComponentHandle;
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Press {
    Close,
    Skip,
    Act,
}

#[derive(Default)]
pub struct UpdatePort {
    open: Option<(UpdateDialog, UpdateDialogWindow)>,
    presses: Rc<RefCell<Vec<Press>>>,
}

impl UpdatePort {
    /// 有更新: the dialog for the release offered, the download started at once.
    pub fn open(&mut self, runner: &mut Runner) {
        let Some(release) = runner.offer.clone() else { return };
        if self.open.is_some() {
            return;
        }
        let Ok(window) = UpdateDialogWindow::new() else { return };
        for (press, hook) in [(Press::Close, 0), (Press::Skip, 1), (Press::Act, 2)] {
            let presses = self.presses.clone();
            let push = move || presses.borrow_mut().push(press);
            match hook {
                0 => window.on_close_clicked(push),
                1 => window.on_skip(push),
                _ => window.on_act(push),
            }
        }
        let from_source = app::wiring::startup::install_root().is_none();
        let mut dialog = UpdateDialog::new(&release, app::wiring::startup::VERSION, from_source);
        let first = dialog.start(None);
        let _ = window.show();
        self.open = Some((dialog, window));
        self.carry(runner, first);
        self.fill();
    }

    /// The window's timer: its buttons, then what the download said.
    pub fn pump(&mut self, runner: &mut Runner) {
        let presses: Vec<Press> = std::mem::take(&mut *self.presses.borrow_mut());
        let events = std::mem::take(&mut runner.install_events);
        let Some((dialog, _)) = self.open.as_mut() else { return };
        let mut effects = Vec::new();
        for press in presses {
            effects.push(match press {
                Press::Close => dialog.reject(),
                Press::Skip => dialog.skip(),
                Press::Act => dialog.act(None),
            });
        }
        for event in &events {
            match event {
                Install::Progress(got, total) => dialog.progress((*got).max(0) as u64, (*total).max(0) as u64),
                Install::Staged => effects.push(dialog.done()),
                Install::Failed(error) => dialog.failed(error.message()),
            }
        }
        let changed = !effects.is_empty() || !events.is_empty();
        for effect in effects {
            self.carry(runner, effect);
        }
        if changed {
            self.fill();
        }
    }

    fn fill(&self) {
        if let Some((dialog, window)) = &self.open {
            fill_update(window, dialog, false);
        }
    }

    fn carry(&mut self, runner: &mut Runner, effect: Effect) {
        match effect {
            Effect::StartDownload => {
                if !runner.start_install() {
                    if let Some((dialog, _)) = self.open.as_mut() {
                        dialog.failed("下载失败，看看网络再试");
                    }
                }
            }
            Effect::RestartAfter(ms) => crate::ui_wiring::restart_after(runner, ms),
            Effect::OpenUrl(url) => crate::ui_wiring::open_url(&url),
            Effect::Close => {
                if let Some((_, window)) = self.open.take() {
                    let _ = window.hide();
                }
            }
            Effect::Nudge | Effect::None => {}
        }
    }
}
