//! The small real parts behind the flow's ports: the sound (ui_music), the tray icon (ui.py's tray) and 直播姬's
//! state for 直播模式 (livehime.status).

use super::stubs::{LiveHime, Player, TrayAction};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Arc, Mutex, PoisonError};

/// Each 场景's sound as 场景管理 set it (Store.scene_sound): the chosen song, or None for the scene's own, and 音量.
pub type SharedSounds = Arc<Mutex<HashMap<String, (Option<PathBuf>, i32)>>>;

/// Copies every scene's sound from the store (the sound thread cannot borrow it).
pub fn share_sounds(store: &data::store::Store, shared: &SharedSounds) {
    let sounds = stage::pick::keys()
        .map(|key| {
            let (song, volume) = store.scene_sound(key);
            (key.to_string(), (song, volume as i32))
        })
        .collect();
    *shared.lock().unwrap_or_else(PoisonError::into_inner) = sounds;
}

/// What the music asks for a scene: the shared copy's answer, else the scene's own tune at 100 %.
pub fn sounds_of(shared: SharedSounds) -> sound::music::SoundsOf {
    Box::new(move |key: &str| {
        shared.lock().unwrap_or_else(PoisonError::into_inner).get(key).cloned().unwrap_or((None, 100))
    })
}

/// The sound crate's player: silent until `sound::allow_sound`, which only the real app's run calls.
pub struct Sound(pub sound::Player);

impl Sound {
    /// The speakers of this PC, the tunes from `assets`.
    pub fn system(assets: PathBuf, sounds: SharedSounds) -> Sound {
        Sound(sound::Player::system(assets, Some(sounds_of(sounds))))
    }
}

impl Player for Sound {
    fn play_tune(&mut self, scene_key: &str) {
        self.0.play_tune(scene_key);
    }
    fn play_alert(&mut self) {
        self.0.play_alert(sound::Alert::Blacklist);
    }
    fn set_muted(&mut self, muted: bool) {
        self.0.set_muted(muted);
    }
}

/// The tray's words in the app's: a click on the icon or 显示主窗口 brings the window back, 退出 quits.
pub fn tray_action(action: win::tray::TrayAction) -> TrayAction {
    match action {
        win::tray::TrayAction::ShowMainWindow => TrayAction::Show,
        win::tray::TrayAction::Quit => TrayAction::Quit,
    }
}

/// 直播姬's state as the header shows it (livehime.Status), in the flow's words; None: not known yet.
pub fn live_hime(status: Option<win::livehime::Status>) -> LiveHime {
    use win::livehime::Status;
    match status {
        None => LiveHime::Unknown,
        Some(Status::Ok) => LiveHime::Ok,
        Some(Status::Closed) => LiveHime::NotRunning,
        Some(Status::Missing | Status::Hidden) => LiveHime::NoWindow,
        Some(Status::Behind) => LiveHime::Covered,
    }
}

#[cfg(windows)]
pub use self::windows::{LiveHimeDesktop, SystemTray};

#[cfg(windows)]
mod windows {
    use super::super::stubs::{LiveHime, LiveHimeWatch, Tray, TrayAction};
    use std::sync::mpsc::{channel, Sender};

    /// The tray icon and its menu (win::tray), its clicks forwarded to the runner's channel.
    pub struct SystemTray(win::tray::Tray);

    impl SystemTray {
        pub fn spawn(actions: Sender<TrayAction>) -> Result<SystemTray, win::tray::TrayError> {
            let (sender, clicks) = channel();
            let tray = win::tray::Tray::spawn(sender)?;
            let _ = std::thread::Builder::new().name("TrayActions".into()).spawn(move || {
                for click in clicks {
                    if actions.send(super::tray_action(click)).is_err() {
                        break;
                    }
                }
            });
            Ok(SystemTray(tray))
        }
    }

    impl Tray for SystemTray {
        fn visible(&self) -> bool {
            self.0.is_shown()
        }
    }

    /// 直播姬 on this PC: its window by title, its scene from its own log.
    pub struct LiveHimeDesktop {
        pub title: String,
        pub point: Option<(i32, i32)>,
        watch: win::livehime::SceneWatch,
    }

    impl LiveHimeDesktop {
        pub fn new(title: &str) -> LiveHimeDesktop {
            LiveHimeDesktop { title: title.into(), point: None, watch: win::livehime::SceneWatch::new(None) }
        }
    }

    impl LiveHimeWatch for LiveHimeDesktop {
        fn state(&mut self) -> LiveHime {
            super::live_hime(win::livehime::desktop::header_status(&self.title, &mut self.watch, self.point))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_scene_without_a_shared_sound_plays_its_own_tune_at_full_volume() {
        let shared = SharedSounds::default();
        shared.lock().unwrap().insert("stars".into(), (Some(PathBuf::from("songs/a.wav")), 40));
        let of = sounds_of(shared);
        assert_eq!(of("stars"), (Some(PathBuf::from("songs/a.wav")), 40));
        assert_eq!(of("ice"), (None, 100));
    }

    #[test]
    fn the_tray_and_live_hime_words_map_onto_the_flows() {
        assert_eq!(tray_action(win::tray::TrayAction::ShowMainWindow), TrayAction::Show);
        assert_eq!(tray_action(win::tray::TrayAction::Quit), TrayAction::Quit);
        assert_eq!(live_hime(None), LiveHime::Unknown);
        assert_eq!(live_hime(Some(win::livehime::Status::Behind)), LiveHime::Covered);
        assert_eq!(live_hime(Some(win::livehime::Status::Hidden)), LiveHime::NoWindow);
    }

    #[test]
    fn the_player_stays_silent_in_tests() {
        // allow_sound is the real app's alone: nothing a test does may open the speakers.
        assert!(!sound::sound_allowed());
        let mut player = Sound::system(PathBuf::from("assets"), SharedSounds::default());
        player.play_tune("stars");
        player.set_muted(true);
        assert!(!sound::sound_allowed());
    }
}
