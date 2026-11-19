use super::*;

fn slot(index: usize, visible: &str, bbox: [i64; 4]) -> pipeline::NameSlot {
    pipeline::NameSlot {
        index,
        bbox,
        raw: visible.into(),
        visible: visible.into(),
        truncated: false,
        confidence: 0.9,
        unclear: false,
    }
}

fn lists() -> Lists {
    Lists {
        blacklist: vec![lobby::Entry { name: "示例坏人".into(), tags: vec!["挂机".into()], ..lobby::Entry::default() }],
        likes: vec![
            lobby::Entry { name: "心动小鹿".into(), nickname: "小鹿".into(), ..lobby::Entry::default() },
            lobby::Entry { name: "心动星星".into(), ..lobby::Entry::default() },
        ],
    }
}

fn found() -> pipeline::CheckResult {
    pipeline::CheckResult {
        header_found: true,
        names: vec![slot(0, "示例坏人", [10, 20, 110, 50]), slot(1, "心动小鹿", [10, 60, 110, 90]), slot(2, "心动星星", [10, 100, 110, 130])],
        hits: vec![pipeline::Hit {
            index: 0,
            read_text: "示例坏人".into(),
            entry: 0,
            entry_name: "示例坏人".into(),
            note: String::new(),
            truncated: false,
            line: "示例坏人".into(),
            tags: vec!["挂机".into()],
        }],
        likes: vec![(2, 1), (1, 0), (2, 1)],
        button_box: Some([200, 300, 400, 340]),
        game_box: Some([0.0, 0.0, 1920.0, 1080.0]),
        ..pipeline::CheckResult::default()
    }
}

#[test]
fn the_pipelines_answer_keeps_its_marks_and_moves_onto_the_desktop() {
    let result = convert(&found(), &lists(), (-1920, 0));
    assert!(result.header_found);
    assert_eq!(result.hits.len(), 1);
    assert_eq!(result.hits[0].name, "示例坏人");
    assert_eq!(result.button_box, Some(Rect { x: -1720, y: 300, w: 200, h: 40 }));
    assert_eq!(result.game_box, Some(Rect { x: -1920, y: 0, w: 1920, h: 1080 }));
    let kinds: Vec<_> = result.seats.iter().map(|seat| (seat.name.as_str(), seat.kind.clone())).collect();
    assert_eq!(
        kinds,
        vec![
            ("示例坏人", MarkKind::Blacklist { tags: vec!["挂机".into()] }),
            ("小鹿", MarkKind::Guest),
            ("心动星星", MarkKind::Guest),
        ]
    );
    assert_eq!(result.seats[0].rect, Rect { x: -1910, y: 20, w: 100, h: 30 });
}

#[test]
fn the_guests_come_from_the_pipeline_once_each_in_its_order() {
    // The flow does not match them again: what the pipeline matched is what greets the lobby.
    let result = convert(&found(), &lists(), (0, 0));
    assert_eq!(result.likes, vec!["心动星星".to_string(), "心动小鹿".to_string()]);
}

#[test]
fn no_models_is_said_plainly_and_paused_like_a_missing_model() {
    let mut checker = PipelineChecker::new(PathBuf::from("missing.dll"), None, 2, SharedLists::default());
    let frame = Frame { width: 2, height: 2, rgb: vec![0; 12] };
    let error = checker.check(&frame).unwrap_err();
    assert!(error.models && error.plain);
    assert_eq!(error.message, "识别功能没装好，重新解压一遍安装包");
    assert!(checker.glance(&frame).unwrap_err().models);
}

#[test]
fn onnx_runtime_is_ours_by_its_full_path_never_a_name_windows_would_search() {
    let dir = tempfile::tempdir().unwrap();
    let install = dir.path().join("blacklist_detect").join("onnxruntime.dll");
    let beside = dir.path().join("runtime").join("onnxruntime.dll");
    let ours = [Some(install.clone()), Some(beside.clone())];
    // Neither there: on Windows the path looked at (System32's older Windows ML copy must not load), elsewhere the name.
    assert_eq!(choose_library(&ours, "onnxruntime.dll", true), beside);
    assert_eq!(choose_library(&ours, "onnxruntime.dll", false), PathBuf::from("onnxruntime.dll"));
    std::fs::create_dir_all(beside.parent().unwrap()).unwrap();
    std::fs::write(&beside, b"x").unwrap();
    assert_eq!(choose_library(&ours, "onnxruntime.dll", true), beside);
    std::fs::create_dir_all(install.parent().unwrap()).unwrap();
    std::fs::write(&install, b"x").unwrap();
    assert_eq!(choose_library(&ours, "onnxruntime.dll", true), install, "the release's own comes first");
}
