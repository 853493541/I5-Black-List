Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only.

# Handoff, 2026-10-15 (evening)

## Code

| What | Where |
|---|---|
| Released | **v0.9.14** = `main` = `origin/main` = `df8957d` |
| `improve/quality` | **`d8f2efc`** (+ this handoff's commit), local, **not pushed**. Full tests: 687 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.14` |

On `improve/quality` since v0.9.14, in order:
- `fb2902d` 演说家遇袭's notice no longer boosted.
- `1f07b9c` Only `run_app` makes sound (`ui_music.allow_sound`).
- `10d831b` CLAUDE.md "Cost" rules.
- `c41c3e8`, `1d1458f`, `f33b2ee`, `e62a1f7` 设置 loses the 声音 slider and the 嘉宾 › 场景 switch (one-time folds on load).
- `d6f5301` the previous handoff.
- **check-header merged** (`7fed366`, `44e9aac`, `2300b26`, `6e23c86`, `1042fb0`): 记录 loses 用截图检查; the 检查 panel loses 提醒 (every check tells about both lists); 直播模式 loses 测试框; 直播模式 is a `StreamSwitch` in the header beside the 检查 pill (`ui_header.py`), the pill in theme colours; the panel holds 显示, 方式 and a 直播 row (测试效果) only while 直播模式 is on. `1042fb0` fixed `build/check_functions.py` (step 2 reads the lobby through `check_image`) and `build/render_gallery.py` (secondary focus on 导出日志). Tested by one tester (PASS WITH NOTES, all notes handled or listed under "Small cleanups").
- `39cf849` (another session, while this master worked) CLAUDE.md: every agent runs on Opus at effort high, the model named on every `Agent` call (`model: "opus"`), never Fable or max.
- **P3 clip-picker merged** (`d639aad`): 选择片段 plays the whole song as it opens (unless 静音), a playhead to click/drag (seeks; the selection is no longer dragged by its middle, as §0 C says), 截取 takes the 5 s just heard, ◀ ▶ nudge with auto-repeat, 试听 pauses the song, 确定 plays nothing; `_keep` no longer auto-plays after an upload. `sound_import.save_rest` writes the song from t (350 ms for a 10-minute song from 0, measured); `ThemeMusic.play_file`. Looked at: `dlg_选择片段` at 150% matches the plan's mockup.

- **P1a guest-scenes-data merged** (`d8f2efc`): `Scenes(keys, random)` with `off` as a property, `ANY_SCENE = Scenes(random=True)`; likes.json read by the §2 E table and written with `"random"` (`no_scene` kept so v0.9.14 reads it back); `Store.me` (likes.json `"me"`, missing = 不放; `reset` clears it, `clear_likes` leaves it; `set_me`); `_fold_old_settings` makes 不放 = `Scenes()`; `guests.lobby_choice` with 随机/不放 (`_asked`); `scenes_said` says 随机 (was 全部随机); `ScenePicker` and `ThemeField` adapted until P1b-ii replaces them. `import_likes` untouched (P1b-i removes it). Note: `ui_likes.py:331` still measures the 场景 column by "全部随机" — P1b-i changes it to 随机.

## Running

- **P1b-i `feature/guest-list`** (implementer on Opus, desktop granted), base `d8f2efc`: see "Next steps" 2. When it reports: rebase, read the diff, run the tests, look at its 嘉宾 page shots, merge; then update CLAUDE.md's "red tags everywhere" rule.

## Branches not merged

- **`feature/bamboo-frame`**, worktree `.claude/worktrees/agent-a0b18785ef4023894`, head `cde23e9`. The new green 场景 「竹风」, key `bamboo`, at the concept checkpoint (v2): a jade band on the edges only, bamboo, the 蛇眉铜鱼 ring, a heart, and 3 chibi pandas; not in SCENES or LOOKS; no sound or poster; frames in its `dist/bamboo_v2/`. **Waiting on the user's approval of v2.** Then the full build: polish (panda arms, the climbing panda's size, how each panda leaves); its sound in `build/theme_tunes.py`, its poster, SCENES/LOOKS entries; review, merge. A gift for a friend who mains 小说家-吴邪 (green + wind).
- **Parked, not to ship.** Leave unless the user asks: `feature/wind-notebook` (`agent-aca4fb31e9a3990eb`), `feature/sheep-scene-v2` (`agent-af314d75e03110601`), `feature/breeze-silk` (`agent-a755becc1e757f49c`), `feature/sheep-scene` and `feature/breeze-scene` (uncommitted drafts). `.claude/worktrees/test-frame-box` is not this session's.

## Next steps, in order

1. **Merge P1b-i** when it reports (above).
2. **P1b-i `feature/guest-list`** (running): the green 我 row on top of the 嘉宾 list (shows `store.player_name` or a muted 「点右上角填写游戏名」; no drag, no edit dialog, no delete, not in the tab count or 复制名单; shows when the search is empty or matches; its 场景 cell says `scenes_said(store.me)`); the 组合 pill in a fixed blue (`ui_widgets._draw_pill` gains `ink`; THEME `blue`/`blue_wash` in both palettes); 批量导入 gone from the 嘉宾 page (toolbar button, empty-state button, `import_many`, `Store.import_likes`, `BatchAddDialog`'s likes branch; 黑名单's stays); `ui.py` `_save_player_name` refreshes `likes_page`. Tests + `tools/ui_shots.py` (嘉宾 page with 我). The master then updates CLAUDE.md's "red tags everywhere" rule (the 组合 pill is blue on purpose).
3. **P1b-ii `feature/guest-scene-editor`** (desktop yes), after P1b-i: new `ui_guest_scenes.py` `GuestScenesDialog` (嘉宾场景, two panes per §2 E: people on the left with 我 on top, a 随机 box + "都不勾：不放" and a 3-column scene grid on the right with the silent preview; edits kept until 确定, 取消 drops them; ~630 px with 14 scenes, the preview shrinks first if a test with 16 fake scenes goes over 672). Opens from a row's 场景 cell, the 我 row, or the row menu 选择场景, with that person selected. The 场景 row leaves 添加嘉宾/编辑嘉宾/添加组合/编辑组合 (a new one starts on 随机). Delete `ScenePicker` and `ThemeField`. `SceneList` gets columns. Tests, `test_dialog_fit` (16 fake scenes), `ui_shots` (dlg_嘉宾场景).
4. **P2 `feature/lobby-priority`** (desktop yes) and **P4 `feature/scene-songs`** (no desktop), side by side after P1b-ii: see `dist/plan_v0915/PLAN.md` §3 (P2: `guests.lobby_scene`, `ui.py` `_show_panel`/`_dress_love`/`_love_for`/`_play_love`; P4: songs per 场景 in `storage.py`, `sound_import` names `<key>-<n>`, `ui_music.song()/drop`, `ui_effects` SoundChoices). P4's "B auto-play bug" is already fixed by P3.
5. **P5 `feature/scene-manager-dialog`** (desktop yes), last: 场景管理 leaves the tabs (Ctrl+1–4 renumbered) and opens from a button right of the 嘉宾 search box.
6. **竹风:** show v2 if the user hasn't answered, then the full build.
7. **Release v0.9.15** only when the user says so (`memory/release-process`). Update notes: at most 3 lines, say 场景 not 特效.

The plan: `dist/plan_v0915/PLAN.md` (git-ignored; only in the main checkout). §0 decisions are binding; its line numbers are from `fb2902d`.

## Small cleanups (not blocking)

- `PictureResultDialog` (`ui_dialogs.py`) is dead in the app since 用截图检查 went; only tests and `build/render_gallery.py` open it. Remove with its tests, or leave.
- The 检查 panel keeps its taller height if 直播模式 is turned off from code while it is open (`_sync_stream_controls` → `_place` → `adjustSize` does not shrink it); no player path reaches it.
- 选择片段: the whole-song play is the song's own loudness × 音量 (not levelled like the saved clip), so it and 试听 may differ in loudness; 截取 has no ✂ icon. Tell the user; change only if asked.

## Gotchas

- A Bash `cd` into an agent worktree moved the desktop session's working folder once. Use `git -C <path>`, `Push-Location`/`Pop-Location`, or `(cd … && …)` subshells.
- `git commit -F -` with a PowerShell here-string does not work here: write the message to a file and `-F <file>`.
- Workflows can be resumed only in the session that started them.
