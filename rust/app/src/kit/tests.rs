//! The kit against the Python app: theme tokens equal golden_theme.json (tools/rust_golden_theme.py), and the
//! gallery renders. Every Slint check is in one test: Slint keeps its platform per thread.

use slint::ComponentHandle;

use super::{render, roles};
use crate::{KitGallery, Theme, Tokens};

fn hex(color: slint::Color) -> String {
    format!("#{:02x}{:02x}{:02x}", color.red(), color.green(), color.blue())
}

#[test]
fn theme_matches_python_and_gallery_renders() {
    let golden: serde_json::Value = serde_json::from_str(include_str!("golden_theme.json")).unwrap();
    let window = render::window();
    let ui = KitGallery::new().unwrap();
    let theme = ui.global::<Theme>();

    let palettes = golden["palettes"].as_object().unwrap();
    assert_eq!(palettes.len(), 10);
    for (key, colors) in palettes {
        let (accent, mode) = key.split_once('/').unwrap();
        let palette = theme.invoke_palette(accent.into(), mode == "dark");
        let rust = roles::roles(&palette);
        assert_eq!(rust.len(), colors.as_object().unwrap().len(), "{key}: a role is missing");
        for (role, color) in rust {
            assert_eq!(hex(color), colors[role].as_str().unwrap(), "{key} {role}");
        }
    }
    // An unknown accent is 蓝色, as use_theme does; the switch follows accent and dark.
    assert_eq!(hex(theme.invoke_palette("灰色".into(), true).bg), "#15171b");
    theme.set_accent("绿色".into());
    theme.set_dark(true);
    assert_eq!(hex(theme.get_p().accent), golden["palettes"]["绿色/dark"]["accent"].as_str().unwrap());

    let tokens = ui.global::<Tokens>();
    let px = |name: &str| golden["type_px"][name].as_f64().unwrap() as f32;
    let space = |name: &str| golden["spacing"][name].as_f64().unwrap() as f32;
    let type_scale = [tokens.get_body(), tokens.get_small(), tokens.get_section(), tokens.get_title()];
    assert_eq!(type_scale, [px("body"), px("small"), px("section"), px("title")]);
    assert_eq!([tokens.get_dialog_title(), tokens.get_overlay()], [px("dialog_title"), px("overlay")]);
    let spacing = [tokens.get_pad(), tokens.get_gap(), tokens.get_dialog_pad(), tokens.get_control_h()];
    assert_eq!(spacing, [space("pad"), space("gap"), space("dialog_pad"), space("control_h")]);
    let rows = [tokens.get_row_h(), tokens.get_radius(), tokens.get_card_radius()];
    assert_eq!(rows, [space("row_h"), space("radius"), space("card_radius")]);

    let (width, height) = (1400 * 3 / 2, 900 * 3 / 2);
    for accent in ["蓝色", "红色"] {
        ui.set_accent(accent.into());
        let pixels = render::draw(&window, &ui, width, height, 1.5).unwrap();
        let distinct: std::collections::HashSet<_> = pixels.iter().map(|p| (p.r, p.g, p.b)).collect();
        assert!(distinct.len() > 50, "{accent}: the gallery drew almost nothing");
        if let Ok(dir) = std::env::var("KIT_SHOTS") {
            let path = std::path::Path::new(&dir).join(format!("gallery-{accent}.png"));
            render::save(&path, &pixels, width, height).unwrap();
        }
    }
}
