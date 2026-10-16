Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only. The user's asks, with where
each stands, are in ASKS.md beside it: that list is what "done" means; report against it.

# Handoff, 2026-10-16 ~05:15 UTC

## Code

| What | Where |
|---|---|
| Released | **v0.9.15** = `main` = `origin/main` = `b9b35dd` (GitHub and all 6 proxies checked) |
| `improve/quality` | **`d08725d`** + this handoff's commit, local, pushed only up to `b9b35dd`. Full tests on the last merge: 755 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.15` (not bumped) |
| On the user's PC | `d6bb214` installed with `build/install_local.py --verify` (12 names verified, app restarted). Their data folder was backed up before the first local install to `dist/backup_appdata_20261016` (git-ignored). |

Asks 1–34 in ASKS.md are merged and installed. This batch (2026-10-16 04:50–05:15 UTC), in merge order: #29–31 嘉宾 buttons and dialog layout (`b45a0e9`), #32 场景管理 hotkey on the left, 配乐, ▶ 播放 (`a7caa8c`), #33 设置 dropdowns, 主题 in 常规, wording (`7372a87`), #34 检查 panel: 基础模式, no 测试效果, no title, 直播模式 关闭 | 开启 (`a82f91f`; the master resolved conflicts in ui.py `play_quick_scene` and tests/test_effect_hotkey.py) + the master's `d6bb214` (直播姬's state: what is wrong whole on the row, with room for the longest; how to fix it on hover). CLAUDE.md updated for all of it (`d08725d`).

## Running

- **#36–37 `fix/scene-manager-speed`** (implementer, base `cd7e12c`, the desktop is granted to it): measure the 场景管理 open lag (the player: about 1 s); if over ~150 ms, open on a still and play on a click in the list (▶ 播放 with 配乐), and cut other costs on the open path; the same for 添加/编辑嘉宾 if they lag. 选择片段: no 共…/边听边按 line, no 选中…秒, the song time at the right end of the 暂停/截取 row, 截取 → 截取刚听到的 5 秒. Files: ui_effects, ui_love_pick, ui_sound_trim (maybe ui_guests/ui_likes), tests. Its shots: scratchpad\shots-speed. When it reports: read the diff, rebase, full tests, merge, reinstall, send the user the screens.
- **#38 music research** (workflow `wf_83277528-06f`, 5 researcher agents): 温迪's official music, the songs of the friend's two GMVs, the repo's 配乐 rules (build/theme_tunes.py: the app's own or public-domain tunes, so a stream can carry them), a verifier, a summary. When it returns: write dist/research/venti_music/REPORT.md, give the user the candidates with the 5 s hook, the stream catch and the options (recording clip / motif re-played by the build script / original / the player uploads it in 场景管理). Download audio only with the user's OK.

## Built, waiting

- **#35 `feature/lyre-scene`** (worktree `agent-abc12a1339922ab73`, commit `84386f2`, base `40c7a23`): `love_scenes/lyre.py`, not in SCENES/LOOKS, with its tests; `dist/concepts_genshin_wind/anim/lyre.webp` + stills sent. The user ACCEPTED the animation. Before it ships: (1) its first frames bake ~1.3–1.4 s each (band, current, lyre), which LoveBorder's running clock would turn into a skipped entrance: bake ahead (a thread, or before play starts); wait for #36's findings on first-frame bakes, the same problem; (2) its 配乐 (#38); (3) a poster; (4) SCENES + `ui_overlay.LOOKS` entries; (5) the name the user picks (the concept was called 竖琴清风; no name until they choose).
- The lyre's history: concepts A/B/C (`dist/concepts_genshin_wind/`, workflow wf_a7491357-0f6), A2 takes, the real 斐林 found by image search (`lyre_reference_real.png`, `LYRE_REFERENCE.md`), A3 close copy approved as splash art (`A3_true_lyre/concept.png`), animated as #35.
- **Release v0.9.16:** the release check of 2026-10-16 ~02:00 (READY WITH NOTES, check_functions 22/22) predates #29–34, so it must run again (full tests, ui_shots light + dark at 100/150/200, check_functions). The notes draft (场景管理移到嘉宾页，可传3首歌 / 编辑嘉宾和组合时直接选场景 / 设置页改版，记录可一键加入名单) needs the user's OK and an update for #29–37. Publishing only on their word.

## Waiting on the user

- **Their look in the app** at the installed build. To confirm with them: the shortened 设置 button texts 导出 / 查看 / 清空; the 声音 row's gray line 每个场景的音量在场景管理里调.
- **Green 场景**: 7 concept stills sent (dist/concepts_green/all_concepts.png: 1 草原风车, 2 竹风铃, 3 风筝, 4 水墨竹, 5 山雾萤火, 6 青铜门, 7 柳与燕). They pick one; then one concept frame of it, then the build. Pictures, not text; no name until they choose.
- **Release v0.9.16**: only on their word. The final release check first: full tests, `tools/ui_shots.py` light + dark at 100/150/200 (dark and 100/200 only here, per CLAUDE.md "Cost"), `build/check_functions.py`; then bump, notes (3 lines, 场景 not 特效), `make_release`, sign, push, publish, `check --each` (memory `release-process`).

## Small cleanups (not blocking; testers' low/cosmetic notes)

- 嘉宾 dialogs: with more than 10 scenes, arrow keys don't scroll the list to the focused scene; the scene list's scroll area is an empty Tab stop; a removed 嘉宾's strike-out is faint at 100%; stale comments (tests/test_likes.py:458, tests/test_scene_multi.py:1/325, ui_effects.py:3, model.Entry's docstring).
- 设置: a very long 检查更新 note could push the buttons off (no current note is that long); Ctrl+click deselects the catalog row; the right scroll area is an empty Tab stop.
- 场景管理: uploading songs with the dialog open at the window's minimum size lets the dim layer hang below the window until reopened; docstrings in ui_love_pick.py still say "the 场景管理 page".
- `PictureResultDialog` is dead in the app. 选择片段: the whole-song play is not levelled like the saved clip; 截取 has no ✂ icon.

## Branches not merged

- `feature/bamboo-frame` (`agent-a0b18785ef4023894`, `cde23e9`): 竹风 v2, rejected (memory `bamboo-v2-feedback`), superseded by the concept stills.
- Parked, not to ship: `feature/wind-notebook`, `feature/sheep-scene-v2`, `feature/breeze-silk`, `feature/sheep-scene`, `feature/breeze-scene`. `.claude/worktrees/test-frame-box` is not this session's.

## Gotchas

- Every agent brief carries the user's four lines (memory `brief-lines`). An `implementer` always gets a fresh worktree of its own: a fix on an existing branch is a new implementer told to work from that branch's commit, or the master does it.
- Testers must check UI with a real pointer on the desktop when the change is about hover/click: the #21 unit tests passed while a real mouse never lit the seat.
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a byte-order mark: edit source files with Python (`write_text`/`write_bytes`) or the Edit tool, never Set-Content.
- Other sessions commit to `improve/quality` while a master works (rules in CLAUDE.md, agents/): rebase right before each fast-forward.
