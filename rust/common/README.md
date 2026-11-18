# common

Wave 1 had nine workers at once, so some rules and records were written more than once. This crate keeps one copy.
Every old path still works: the crate that had a copy now re-exports it (`pub use common::X;`). New code imports from
`common` directly.

Parity: `tools/rust_golden_common.py` writes `tests/golden.json` from the Python app (640 name strings: 40 picked
edge cases and 600 seeded random ones; app_dir, child_env, ocr_threads, the constants). `tests/golden.rs` checks all
of it. Before the switch, all three old copies of the name rules matched the same 640 cases, so the switch changes
nothing.

## What moved, and where each copy was

| In common | Python | Copies it replaced (each now a re-export) |
|---|---|---|
| `text::{normalize_text, split_ellipsis, strip_noise, fold, clean_stored_name, MIN_PREFIX_CHARS}` | match.py | `lobby::matching`, `data::import::text` (regex version), `data::store::text` (`normalize` is `normalize_text`) |
| `text::{nfkc, is_space, is_letter_or_number, casefold, drop_space}` | `str` rules | `lobby::text`; `is_space` also in `data::import::text`, `data::store::py` |
| `model::{Entry, Scenes, Combo, OcrLine, Rect}` | model.py | `lobby::model`, `data::import::model` (`Entry::named` from lobby, `Entry::new` from data: both kept) |
| `names::{LAUNCHERS, PROCESSES, launcher_in}` | names.py | `data::import::names`, `data::update::stage`, `win::autostart`, `win::instance` |
| `limits::{TAGS, MAX_TAG, MAX_NAME, MAX_NOTE, SHARE_MARK, OLD_SHARE_MARKS, SCENE_KEYS}` | storage.py, love_scenes.KEYS | `data::import::tags`, `data::store::text`, `data::store::share` |
| `paths::{app_dir, app_dir_for, custom_sound_dir}` | paths.py | `data::store::files` |
| `paths::{child_env, child_env_from}` | paths.child_env | new (not ported before); give it to `Command::env_clear().envs(..)` |
| `paths::{ocr_threads_for, ocr_threads}` | paths.ocr_threads | `ocr::det::ocr_threads(cores)` (re-exported under its old name), `ocr::rec::ocr_threads()` |

## Same name, not the same thing (left as they are)

- `data::store::sounds::Scenes`: its `Default` is 不放 (`random: false`), which `Store.me` relies on, and it carries
  the store's own methods (`cleaned`, `saved`, `save_into`, ...). Merging it means a trait or a call-site change.
  `data::store::{Entry, Like, Combo}` are the stored forms (no nickname on an `Entry`; a `Like` is a 嘉宾).
- `data::store::text::{order_tags, tags_and_reason}` and `data::import::tags::{...}`: same Python functions, but
  different signatures, and the store's `tags_and_reason` splits lines with Rust's `lines()` where the import side
  uses Python's `splitlines` (they differ on `\x0b`, `\x0c`, `\x1c`-`\x1e`, `\x85`, ` `, ` `). Merging
  them is a behaviour change, so it is for the data owner. `clean_tag` and `merge_reason` are also in both, same
  behaviour.
- `data::store::py::float_repr` and `data::update::py::float_repr`: different code (the update one is simpler; they
  differ for very small or large numbers). `strip` is in `data::store::py`, `data::update::py`, `data::import::text`.
- `data::store::text::parse_hotkey` (strings, Python `strip`) and `win::hotkey::parse_hotkey` (a `Modifier` enum,
  Rust `trim`): one rule, two types.
- `scenes::stars::Rect` is x, y, width, height; `common::Rect` is left, top, right, bottom.
- `scenes::prim::Frame` (a draw list) and `win::frame::Frame` (captured pixels).
- `lobby::Scan` (a saved check as last_seen reads it: when, the seats) and `data::store::scans::Scan` (the stored form,
  with `elapsed` kept as saved): a merge needs `lobby` to depend on serde_json or the store to drop `elapsed`.
