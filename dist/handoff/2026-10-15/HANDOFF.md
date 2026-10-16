Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only. The user's asks, with where
each stands, are in ASKS.md beside it: that list is what "done" means; report against it.

# Handoff, 2026-10-16 ~02:30 UTC

## Code

| What | Where |
|---|---|
| Released | **v0.9.15** = `main` = `origin/main` = `b9b35dd` (GitHub and all 6 proxies checked) |
| `improve/quality` | **`d6cdbba`** + handoff commits, local, pushed only up to `b9b35dd`. Full tests at d6cdbba: 731 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.15` |

Merged since v0.9.15 (all tested by a tester agent, read and re-tested by the master on the combined code):
- `482c80e` 嘉宾 list: green 我 row, blue 组合 tag, no 批量导入 for 嘉宾 (asks 10, 11, 13).
- `63e5184` lobby priority 组合 > 嘉宾 > 黑名单 > 我 (`guests.lobby_scene`); 我's music once per lobby by name overlap (`ThemeMusic.mine`); a 黑名单 seat never counts as 嘉宾; the 场景 skips 黑名单 seats (ask 14). On-game shots (`ui_shots` game_黑名单和嘉宾, game_我的场景) checked by the master after `22f012b` fixed their scale.
- `d5b18b6` 嘉宾场景 two-pane editor (`ui_guest_scenes.GuestScenesDialog`); `ScenePicker`/`ThemeField` gone; names whole in a 3-column grid; names preview under 随机; stale-only ticks show as 随机 (asks 12, 13).
- `d6cdbba` songs: 默认 + up to 3 songs per 场景, one chosen (`storage` `scene_sounds[key]` = volume, songs, chosen, plus a rollback copy; `"scene_songs": true` marker; `_unlisted_songs` brings back songs v0.9.15 dropped); radio circle fixed for Windows 11; under 静音 every ▶ off, saying 已静音 (ask 5).
- `92200d9`, `1ebc062` (other sessions): CLAUDE.md screenshot and model rules.

## Running

Four packages, three of them in `ui.py` in disjoint regions (tabs / 记录 / 设置) — merge one at a time, rebasing each. The desktop: only A's agents use it now; #21, #22–24 and #25–26 build and test offscreen, and get ONE screenshot pass each (by a tester, or the master) after A's tester is done, never two at once. The user wants to see #22–24 and #25–26 as pictures before they merge.

- **#21 `feature/record-buttons`** (implementer agent, base 13e9588, no desktop): 记录 seats get ♥ and 🚫 buttons on hover; one click adds with 撤销; the page stays put.
- **#22–24 `feature/guest-dialogs`** (workflow wf_65cdc217-2a7, base 8a4b065, no desktop): 添加/编辑嘉宾, 添加/编辑组合 and 我 dialogs each pick their own 场景 (放场景 box + one scene per row + preview at the bottom of the left column); GuestScenesDialog removed.
- **#25–26 `feature/settings-catalog`** (workflow wf_5df86789-8ea, base 7d71dcf, no desktop): 设置 with a catalog (常规/外观/帮助/关于) and rows of name+description left, control right; 开机启动 and 关闭窗口时 on separate rows. After it merges, update CLAUDE.md's 设置 rule ("fits 900x760 without scrolling, so it gets no new rows").
- **A / P5 `feature/scene-manager-dialog`** (workflow wf_6ca450e8-078, base `d6cdbba`): implementer (one ui_shots pass at the end) → tester (one full pass) → one fix round if it fails. Asks 3 and 4. When it reports: rebase onto `improve/quality`, read the diff, run the full tests and ruff, look at the dialog shot at 150 %, merge. A new session restarts it from `~/.claude/projects/C--Users-Zhibin-Ren-Desktop-Black-List-App/<session>/workflows/scripts/p5-scene-manager-dialog-*.js` or briefs a fresh implementer from that script's SPEC.

## On the user's PC

- 2026-10-16 01:07 UTC: the user asked "don't ship, just build it locally, I'll see". `build/install_local.py --verify` installed `improve/quality` 0798416 (asks 5, 10–14 in, 3–4 not yet) into `%LOCALAPPDATA%\Programs\BlackListDetect` and restarted it; 12 names verified, log clean. Their data folder was backed up first to `dist/backup_appdata_20261016` (git-ignored). Reinstall the same way once A merges. Still nothing published past v0.9.15.

## Waiting on the user

- **Green 场景** (for the 吴邪 friend): 7 concept stills sent; the user picks one (dist/concepts_green/all_concepts.png). Then one concept frame of the pick, then the build. The user wants pictures, not text, and no name until they choose.
- **Release v0.9.16**: only on their word, after A merges, with the final release check (dark theme and 100/200 % shots happen there, per CLAUDE.md "Cost"). `memory/release-process`; notes at most 3 lines, 场景 not 特效.

## Next steps, in order

1. Merge A when it reports (above). Then update CLAUDE.md "Rules": 选择场景 is gone; name the tallest dialog now (嘉宾场景 or 场景管理, from `tests/test_dialog_fit.py`).
2. Tell the user the state against ASKS.md, and ask for the release word and the green 场景 pick.
3. On the release word: final release check (full tests, `tools/ui_shots.py` light + dark at 100/150/200, `build/check_functions.py`), bump to v0.9.16, notes, `make_release`, sign, push, publish, `check --each`.

## Small cleanups (not blocking)

- `PictureResultDialog` (`ui_dialogs.py`) is dead in the app since 用截图检查 went; only tests and `build/render_gallery.py` open it.
- The 检查 panel keeps its taller height if 直播模式 is turned off from code while it is open; no player path reaches it.
- 选择片段: the whole-song play is the song's own loudness × 音量 (not levelled like the saved clip); 截取 has no ✂ icon.
- Songs: a quick ✕ on a second row within a double-click interval is ignored (on purpose: it stops a double-click deleting two); orphan song files only in hand-edited or rollback edge cases.
- Lobby: a 我 check that reads every seat unclear makes the next lobby within 60 s silent; a live re-check that turns a 嘉宾 lobby into a 我 lobby plays the old scene's tune (older behaviour).

## Branches not merged

- **`feature/bamboo-frame`** (`agent-a0b18785ef4023894`, `cde23e9`): 竹风 v2, rejected 2026-10-15 (memory `bamboo-v2-feedback`). Superseded by the concept stills above.
- **Parked, not to ship:** `feature/wind-notebook`, `feature/sheep-scene-v2`, `feature/breeze-silk`, `feature/sheep-scene`, `feature/breeze-scene`. `.claude/worktrees/test-frame-box` is not this session's.

## Gotchas

- Every agent brief carries the user's four lines (Opus effort high max; stop ~50 turns with the commit; ~30-line report; the screenshot rule): agent worktrees start from origin/main, whose CLAUDE.md is older (memory `brief-lines`).
- Other sessions commit to `improve/quality` while a master works: rebase a branch right before its fast-forward.
- PowerShell: `git commit -m` twice for subject + attribution; `-F -` with a here-string does not work. Use `git -C <path>` or Push-Location, never a bare `cd` into a worktree.
