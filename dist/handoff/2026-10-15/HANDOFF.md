Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only.

# Handoff, 2026-10-15 (night)

## Code

| What | Where |
|---|---|
| Released | **v0.9.15** = `main` = `origin/main` = `b9b35dd` (published 2026-10-15 evening PT; `release.py check --each`: GitHub and all 6 proxies OK, signature and zip checked) |
| `improve/quality` | `482c80e` + this handoff's commit, local (pushed up to `b9b35dd`). Full tests at 482c80e: 689 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.15` |

v0.9.15 holds, on top of v0.9.14:
- `fb2902d`, `1f07b9c`, `10d831b`, `c41c3e8`…`e62a1f7`: 演说家遇袭 loudness, background silence, Cost rules, 设置 loses the 声音 slider and the 嘉宾 › 场景 switch (one-time folds on load).
- **check-header** (`7fed366`…`1042fb0`): 记录 loses 用截图检查; the 检查 panel loses 提醒 (every check tells about both lists); 直播模式 loses 测试框; 直播模式 is a `StreamSwitch` in the header beside the 检查 pill (`ui_header.py`); the panel holds 显示, 方式 and a 直播 row (测试效果) only while 直播模式 is on. One tester, PASS WITH NOTES; notes handled or under "Small cleanups".
- `39cf849` (another session): CLAUDE.md — every agent on Opus at effort high, `model: "opus"` named on every `Agent` call, never Fable or max.
- **P3 clip-picker** (`d639aad`): 选择片段 plays the whole song on open (unless 静音), playhead click/drag seeks (the selection is no longer dragged by its middle, per plan §0 C), 截取 takes the 5 s just heard, ◀ ▶ nudge with auto-repeat, 试听 pauses the song, 确定 plays nothing; `_keep` no longer auto-plays after an upload. `sound_import.save_rest` (350 ms for a 10-minute song from 0, measured), `ThemeMusic.play_file`. Not told to the user yet: the whole-song play is the song's own loudness × 音量 (not levelled like the saved clip); 截取 has no ✂ icon.
- **P1a guest-scenes-data** (`d8f2efc`): `Scenes(keys, random)` with `off` as a property, `ANY_SCENE = Scenes(random=True)`; likes.json read by plan §2 E's table and written with `"random"` (`no_scene` kept so v0.9.14 reads it back); `Store.me` (likes.json `"me"`, missing = 不放; `reset` clears it, `clear_likes` leaves it; `set_me`); `_fold_old_settings` makes 不放 = `Scenes()`; `guests.lobby_choice` with 随机/不放 (`_asked`); `scenes_said` says 随机 (was 全部随机); `ScenePicker`/`ThemeField` adapted until P1b-ii replaces them. `ui_likes.py:331` still measures the 场景 column by "全部随机" (P1b-i fixes).
- `dfff44d`, `b9b35dd`: handoff; the release (version bump, `build/notes/v0.9.15.txt`).

- **P1b-i guest-list merged** (`482c80e`, after the release): the green 我 row on top of the 嘉宾 list (`ME_ROLE`; `store.player_name` or muted 「点右上角填写游戏名」; the 我 tag is green ink on a `surface` chip; no drag/edit/delete/menu; not in the count, 复制名单 or 清空; search shows it when empty or matching; 场景 cell = `scenes_said(store.me)`; `LikesPage.edit_me()` is a stub for P1b-ii; no 我 row while the list is empty); the 组合 pill in blue (`_draw_pill(..., ink)`; THEME `blue`/`blue_wash` in both palettes, contrast-tested); 批量导入 gone from the 嘉宾 page (`Store.import_likes` and `BatchAddDialog`'s `likes` are gone; 黑名单's stays); `ui.py` refreshes `likes_page` after the name is saved; `tools/ui_shots.py` fixed (it used `Scenes(off=True)`) and seeds `store.set_me(Scenes(("lace",)))`.

## Running

- Nothing, unless the next master started P1b-ii (see "Next steps").

## Branches not merged

- **`feature/bamboo-frame`**, worktree `.claude/worktrees/agent-a0b18785ef4023894`, head `cde23e9`: 竹风 v2. **Rejected by the user on 2026-10-15 and set aside** (memory `bamboo-v2-feedback`): pandas "horrifying" at frame scale, the 蛇眉铜鱼 ring too detailed, 窗棂 corners wrong for green, the badge "disgusting". Only when the user asks again: a judged panel of panda styles composited at real size over the sample lobby (`tools/love_frames.py` renders a scene; the toolkit is `_fur`/`_face` in `bamboo.py` and `_cat` in `fluffy.py`), simple two-tone fish or none, natural corners, a simple badge.
- **Parked, not to ship.** `feature/wind-notebook` (`agent-aca4fb31e9a3990eb`), `feature/sheep-scene-v2` (`agent-af314d75e03110601`), `feature/breeze-silk` (`agent-a755becc1e757f49c`), `feature/sheep-scene` and `feature/breeze-scene` (uncommitted drafts). `.claude/worktrees/test-frame-box` is not this session's.

## Next steps, in order

1. **P1b-ii `feature/guest-scene-editor`** (desktop yes), from `improve/quality`: new `ui_guest_scenes.py` `GuestScenesDialog` (嘉宾场景, two panes per plan §2 E: people on the left with 我 on top, a 随机 box + "都不勾：不放" and a 3-column scene grid on the right with the silent preview; edits kept until 确定, 取消 drops them; ~630 px with 14 scenes, the preview shrinks first if a test with 16 fake scenes goes over 672). Opens from a row's 场景 cell, the 我 row, or the row menu 选择场景, with that person selected. The 场景 row leaves 添加嘉宾/编辑嘉宾/添加组合/编辑组合 (a new one starts on 随机). Delete `ScenePicker` and `ThemeField`. `SceneList` gets columns. Tests, `test_dialog_fit` (16 fake scenes), `ui_shots` (dlg_嘉宾场景). A draft brief is in this session's scratchpad (`brief_p1b2.md`); the next master writes its own from this list.
3. **P2 `feature/lobby-priority`** (desktop yes) and **P4 `feature/scene-songs`** (no desktop), side by side after P1b-ii: plan §3 (P2: `guests.lobby_scene`, `ui.py` `_show_panel`/`_dress_love`/`_love_for`/`_play_love`; P4: songs per 场景 in `storage.py`, `sound_import` names `<key>-<n>`, `ui_music.song()/drop`, `ui_effects` SoundChoices). P4's "B auto-play bug" is already fixed by P3. Under ultracode, these two can be one workflow (two implementers, then one tester each).
4. **P5 `feature/scene-manager-dialog`** (desktop yes), last: 场景管理 leaves the tabs (Ctrl+1–4 renumbered) and opens from a button right of the 嘉宾 search box.
5. **Release v0.9.16** only when the user says so (`memory/release-process`). Update notes: at most 3 lines, say 场景 not 特效.

The plan: `dist/plan_v0915/PLAN.md` (git-ignored; only in the main checkout). §0 decisions are binding; its line numbers are from `fb2902d`.

## Small cleanups (not blocking)

- `PictureResultDialog` (`ui_dialogs.py`) is dead in the app since 用截图检查 went; only tests and `build/render_gallery.py` open it.
- The 检查 panel keeps its taller height if 直播模式 is turned off from code while it is open (`_sync_stream_controls` → `_place` → `adjustSize` does not shrink it); no player path reaches it.

## Gotchas

- Another session commits to `improve/quality` while a master works: rebase a branch right before its fast-forward, and check `git log` before every merge.
- A Bash `cd` into an agent worktree moved the desktop session's working folder once. Use `git -C <path>`, `Push-Location`/`Pop-Location`, or `(cd … && …)` subshells.
- `git commit -F -` with a PowerShell here-string does not work here: `-m` twice, or write the message to a file and `-F <file>`.
- Local `main` lagged `origin/main` (releases are pushed as `HEAD:main`): `git branch -f main <release>` after pushing.
- Workflows can be resumed only in the session that started them.
