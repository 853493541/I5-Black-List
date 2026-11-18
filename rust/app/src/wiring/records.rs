//! The flow's `Records` on the real lists (data::store::Store): 记录, the 嘉宾 in a lobby, and the scene that greets it.

use super::flow::{Greeting, Records};
use super::stubs::CheckResult;
use data::import::guests::{lobby_scene, Choice};
use data::import::model as pick;
use data::store::scans::Seat;
use data::store::Store;
use std::cell::RefCell;
use std::rc::Rc;

/// The store, shared with the window that edits it.
pub struct StoreRecords(pub Rc<RefCell<Store>>);

fn scenes(from: &data::store::sounds::Scenes) -> pick::Scenes {
    pick::Scenes { keys: from.keys.clone(), random: from.random }
}

/// The scene a choice plays. A choice of several is resolved by the scene player's own draw; until then the first.
pub fn scene_of(choice: &Choice) -> String {
    match choice {
        Choice::One(key) => key.clone(),
        // stub: stage (love_scenes.choose draws one of these at random)
        Choice::Many(keys) => keys.first().cloned().unwrap_or_default(),
    }
}

impl Records for StoreRecords {
    fn add_scan(&mut self, result: &CheckResult, elapsed: Option<f64>) {
        let seats: Vec<Seat> = result
            .names
            .iter()
            .map(|slot| Seat {
                seat: lobby::seat_number(slot.index) as i64,
                name: if slot.unclear { String::new() } else { slot.visible.clone() },
                unclear: slot.unclear,
            })
            .collect();
        self.0.borrow_mut().add_scan(&seats, elapsed);
    }

    fn likes_in(&self, result: &CheckResult) -> Vec<String> {
        let store = self.0.borrow();
        let likes: Vec<lobby::Entry> = store
            .likes
            .iter()
            .map(|like| lobby::Entry { name: like.name.clone(), nickname: like.nickname.clone(), ..lobby::Entry::default() })
            .collect();
        let warned: Vec<usize> = result.hits.iter().map(|hit| hit.index).collect();
        let mut found: Vec<String> = Vec::new();
        for slot in result.names.iter().filter(|slot| !warned.contains(&slot.index)) {
            let label = lobby::NameLabel {
                raw: slot.raw.clone(),
                visible: slot.visible.clone(),
                truncated: slot.truncated,
                unclear: slot.unclear,
            };
            for hit in lobby::match_label(&label, &likes) {
                let name = &likes[hit.index].name;
                if !found.contains(name) {
                    found.push(name.clone());
                }
            }
        }
        found
    }

    fn greeting(&self, likes: &[String], blacklisted: bool) -> Greeting {
        let store = self.0.borrow();
        let all: Vec<pick::Entry> = store
            .likes
            .iter()
            .map(|like| pick::Entry {
                name: like.name.clone(),
                nickname: like.nickname.clone(),
                scenes: scenes(&like.scenes),
                ..pick::Entry::default()
            })
            .collect();
        let present: Vec<pick::Entry> = all.iter().filter(|like| likes.contains(&like.name)).cloned().collect();
        let combos: Vec<pick::Combo> =
            store.combos.iter().map(|combo| pick::Combo { names: combo.names.clone(), scenes: scenes(&combo.scenes) }).collect();
        let (who, choice) = lobby_scene(&all, &combos, &present, &scenes(&store.me), blacklisted);
        if who.is_empty() {
            return Greeting::default();
        }
        Greeting { who, scene: scene_of(&choice) }
    }
}
