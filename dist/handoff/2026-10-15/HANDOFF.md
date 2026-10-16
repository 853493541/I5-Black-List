Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only. The user's asks, with where
each stands, are in ASKS.md beside it: that list is what "done" means; report against it.

# Handoff, 2026-10-16 ~02:20 UTC (19:20 PT)

## Code

| What | Where |
|---|---|
| Released | **v0.9.15** = `main` = `origin/main` = `b9b35dd` (GitHub and all 6 proxies checked) |
| `improve/quality` | **`902d56f`** + this handoff's commit, local, pushed only up to `b9b35dd`. Full tests on the last merge: 757 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.15` (not bumped) |
| On the user's PC | `902d56f` installed with `build/install_local.py --verify` (12 names verified, app restarted, log clean). Their data folder was backed up before the first local install to `dist/backup_appdata_20261016` (git-ignored). |

All 27 asks in ASKS.md are merged. Since v0.9.15, in merge order: 嘉宾 list (我 row, blue 组合, no 批量导入), lobby priority, 嘉宾场景 editor (later replaced), songs per 场景, 场景管理 as a dialog (+ master's fix: spare room at its foot, old notes cleared on reopen), 直播模式 back in the 检查 panel (+ master's fix: the panel shrinks back), 记录 ♥/🚫 buttons (+ master's fix: a real pointer lights the seat, proved with a real cursor), 嘉宾/组合/我 dialogs that pick their own 场景 (放场景 + one scene per row + preview), 设置 as a catalog (常规/外观/帮助/关于, name + gray line left, control right). CLAUDE.md's 设置 and dialog-height rules updated (902d56f).

## Running

Nothing. No agents, no workflows. Leftover worktree: only `feature/bamboo-frame` (parked) and the parked scene branches below.

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
