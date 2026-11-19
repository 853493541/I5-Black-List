use super::*;
use crate::list::ListAction;

/// Each tab shows its own page in the main window (pictures in $BLACKLIST_SHOTS/main), and an action that
/// asks first opens its question; a yes comes back as the area's action.
#[test]
fn the_main_window_shows_each_page_and_opens_the_questions() {
    crate::shots::init();
    let mut seeded = crate::list::render::seeded("normal");
    seeded.likes = crate::history::tests_seed_likes();
    let store = Rc::new(RefCell::new(seeded));
    let ui = MainUi::new(store.clone(), "1.2.0").unwrap();
    let dir = std::env::var_os("BLACKLIST_SHOTS").map(std::path::PathBuf::from).map(|d| d.join("main"));
    let mut pictures = Vec::new();
    for (page, name) in ["记录", "黑名单", "嘉宾", "设置"].iter().enumerate() {
        ui.window.set_page(page as i32);
        ui.refresh();
        let picture = crate::shots::draw(&ui.window, (900.0, 560.0), 1.5).unwrap();
        if let Some(dir) = &dir {
            crate::shots::save(&dir.join(format!("page_{name}.png")), &picture).unwrap();
        }
        pictures.push(picture);
    }
    for (i, a) in pictures.iter().enumerate() {
        for b in &pictures[i + 1..] {
            assert_ne!(a.rgb, b.rgb, "every page draws differently");
        }
    }
    ui.bus.send(UiEvent::List(ListAction::AskClear));
    assert!(ui.pump().is_empty());
    assert_eq!(ui.dialogs.borrow().len(), 1, "清空黑名单 asks first");
    assert_eq!(*ui.asking.borrow(), Some(Yes::ClearList));
    ui.bus.send(UiEvent::Shell(ShellAction::BeginHotkey));
    assert!(ui.pump().is_empty(), "the hotkey box handles it");
    assert!(ui.hotkey_waiting.get(), "the hotkey box waits for a key");
    let root = store.borrow().root.clone();
    let _ = std::fs::remove_dir_all(root);
}

fn ui_with_store() -> (MainUi, Shared) {
    crate::shots::init();
    let store = Rc::new(RefCell::new(crate::list::render::seeded("normal")));
    (MainUi::new(store.clone(), "1.2.0").unwrap(), store)
}

fn step(ui: &MainUi, event: UiEvent) -> Vec<UiEvent> {
    ui.bus.send(event);
    ui.pump()
}

/// 添加 opens with the picked tag, 保存 adds the name and closes; 编辑's 删除 removes it.
#[test]
fn add_and_edit_save_through_the_dialog() {
    use crate::dialogs::DialogAction as D;
    let (ui, store) = ui_with_store();
    let before = store.borrow().entries.len();
    assert!(step(&ui, UiEvent::List(ListAction::Add { tag: "炸房".into() })).is_empty());
    assert_eq!(ui.about(), Some(About::Name(None)));
    let save = D::SaveName { name: "新来的路人".into(), tags: vec!["炸房".into()], detail: "开局就退".into() };
    assert!(step(&ui, UiEvent::Dialog(save)).is_empty());
    assert_eq!(ui.about(), None, "保存 closes it");
    let added = store.borrow().entries.iter().position(|e| e.name == "新来的路人").expect("added");
    assert_eq!(store.borrow().entries.len(), before + 1);
    step(&ui, UiEvent::List(ListAction::Edit(added)));
    assert_eq!(ui.about(), Some(About::Name(Some(added))));
    step(&ui, UiEvent::Dialog(D::DeleteName));
    assert!(store.borrow().entries.iter().all(|e| e.name != "新来的路人"), "删除 removes it");
    let root = store.borrow().root.clone();
    let _ = std::fs::remove_dir_all(root);
}

/// 批量导入 with a shared 原因 goes on to 确认导入; its 导入 adds the people with the 标签 still on.
#[test]
fn batch_import_goes_through_the_tag_question() {
    use crate::dialogs::DialogAction as D;
    let (ui, store) = ui_with_store();
    step(&ui, UiEvent::List(ListAction::AddMany));
    assert!(matches!(ui.about(), Some(About::Batch(..))));
    let records: Vec<data::import::Record> =
        ["甲乙丙丁", "戊己庚辛"].iter().map(|n| (n.to_string(), Vec::new(), "开局就退".to_string(), -1)).collect();
    step(&ui, UiEvent::Dialog(D::ImportChecked(records.clone())));
    let Some(About::Suggest(_, found)) = ui.about() else { panic!("确认导入 opens: {:?}", ui.about()) };
    let on: Vec<String> = found.iter().map(|f| f.tag.clone()).collect();
    step(&ui, UiEvent::Dialog(D::ImportWithTags(crate::ui_dialogs::with_tags(&records, &found, &on))));
    assert_eq!(ui.about(), None);
    let store = store.borrow();
    let added = store.entries.iter().find(|e| e.name == "甲乙丙丁").expect("imported");
    assert!(!added.tags.is_empty(), "the suggested 标签 went on: {:?}", added.tags);
    let _ = std::fs::remove_dir_all(&store.root);
}

/// 添加嘉宾, 添加组合, 场景管理 and the guides open; their answers save and close, sounds go to the runner.
#[test]
fn guest_combo_and_scene_dialogs_answer_through_the_bus() {
    use crate::guestedit::{ComboAction as C, GuestAction as G, SceneAction as S, Scenes};
    use crate::guests::GuestAction;
    let (ui, store) = ui_with_store();
    step(&ui, UiEvent::Guests(GuestAction::AddGuest));
    assert_eq!(ui.about(), Some(About::Guest(None)));
    assert_eq!(step(&ui, UiEvent::GuestEdit(G::Replay)), vec![UiEvent::GuestEdit(G::Replay)], "sounds are the runner's");
    let save = G::Save { name: "心动小鹿".into(), nickname: "小鹿".into(), reason: String::new(), scenes: Scenes::of(&["lace"]) };
    step(&ui, UiEvent::GuestEdit(save));
    assert_eq!(store.borrow().likes.len(), 1);
    assert_eq!(store.borrow().likes[0].scenes.keys, vec!["lace".to_string()]);
    store.borrow_mut().add_like("心动星星", "", "", &Default::default()).unwrap();
    step(&ui, UiEvent::Guests(GuestAction::AddCombo));
    assert_eq!(ui.about(), Some(About::Combo(None)));
    step(&ui, UiEvent::Combo(C::Save { names: vec!["心动小鹿".into(), "心动星星".into()], scenes: Scenes::any() }));
    assert_eq!(store.borrow().combos.len(), 1);
    step(&ui, UiEvent::Guests(GuestAction::ManageScenes));
    assert_eq!(ui.about(), Some(About::Scenes));
    step(&ui, UiEvent::Scenes(S::Close));
    assert_eq!(ui.about(), None);
    step(&ui, UiEvent::Shell(ShellAction::ShowDisplayGuide));
    assert_eq!(ui.about(), Some(About::Info));
    step(&ui, UiEvent::Shell(ShellAction::ShowStreamGuide));
    assert_eq!(ui.about(), Some(About::Info), "one dialog at a time");
    step(&ui, UiEvent::Dialog(crate::dialogs::DialogAction::Closed));
    assert_eq!(ui.about(), None);
    assert_eq!(step(&ui, UiEvent::Shell(ShellAction::OpenUpdate)), vec![UiEvent::Shell(ShellAction::OpenUpdate)]);
    let root = store.borrow().root.clone();
    let _ = std::fs::remove_dir_all(root);
}
