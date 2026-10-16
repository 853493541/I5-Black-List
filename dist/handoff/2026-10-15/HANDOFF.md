Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only. The user's asks, with where
each stands, are in ASKS.md beside it: that list is what "done" means; report against it.

# Handoff, 2026-10-16 ~05:35 UTC (the session moved to another account; this master wound down here)

## Code

| What | Where |
|---|---|
| Released | **v0.9.15** = `main` = `origin/main` = `b9b35dd` (GitHub and all 6 proxies checked) |
| `improve/quality` | **`c0fc080`** + this handoff's commits, local, pushed only up to `b9b35dd`. Full tests on the last merge: 756 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.15` (not bumped) |
| On the user's PC | `c0fc080` installed with `build/install_local.py --verify` (12 names verified, app restarted). Their data folder was backed up before the first local install to `dist/backup_appdata_20261016` (git-ignored). |

Asks 1–34, 36 and 37 in ASKS.md are merged and installed. The last batch (2026-10-16 04:50–05:35 UTC), in merge order: #29–31 嘉宾 buttons and dialog layout (`b45a0e9`), #32 场景管理 hotkey on the left, 配乐, ▶ 播放 (`a7caa8c`), #33 设置 dropdowns, 主题 in 常规, wording (`7372a87`), #34 检查 panel: 基础模式, no 测试效果, no title, 直播模式 关闭 | 开启 (`a82f91f`; the master resolved conflicts in ui.py `play_quick_scene` and tests/test_effect_hotkey.py) + the master's `d6bb214` (直播姬's state: what is wrong whole on the row, how to fix it on hover), CLAUDE.md for all of it (`d08725d`), #37 选择片段 clean-up (`3aa5424`), #36 场景管理 and the 嘉宾 dialogs open on the scene's still and play on a click (`c0fc080`; open 183 ms–1 s → ~23 ms). The master looked at shots of every one (scratchpad\shots-master for #36–37).

## Running

- **#38 music research: DONE** (workflow `wf_83277528-06f`, 5 researcher agents, verified): `dist/research/venti_music/REPORT.md` (summary first, then the verification and the three reports). In short: 温迪's music is 《诗人的工作》 / Bard's Adventure (official https://www.youtube.com/watch?v=APFVfv9klmg, 1:47); the hook by YouTube most-replayed is 0:40–0:45 (second choice 1:04–1:09), not listened to yet; options (a) real 5 s cut as default (breaks the stream rule of build/theme_tunes.py; 演说家遇袭 is the only precedent, by the user's choice), (b) its melody re-played by the build script's harp on the strums 0.9/2.9/4.4 s, (c) an original lyre tune, (d) the player uploads it in 场景管理 and cuts 0:40–0:45; recommended (c)+(d). Sent to the user; waiting for their pick. Download audio only with their OK.
- No agent is running. No worktree of this session holds unmerged work except `feature/lyre-scene` below.

## Built, waiting

- **#35 `feature/lyre-scene`** (worktree `.claude/worktrees/agent-abc12a1339922ab73`, commit `84386f2`, base `40c7a23`): `love_scenes/lyre.py`, not in SCENES/LOOKS, with its tests; `dist/concepts_genshin_wind/anim/lyre.webp` + stills sent. The user ACCEPTED the animation. Before it ships, one package (rebase it on improve/quality first): (1) its first frames bake ~1.3–1.4 s each (band, current, lyre), which LoveBorder's running clock would turn into a skipped entrance: bake ahead (a thread, or before play starts); note #36 now makes a scene only on a click, so the 场景管理/嘉宾 previews already open on the poster; (2) its 配乐 (#38, after the user picks); (3) a poster (build/theme_posters.py, `assets/posters/lyre.jpg`); (4) SCENES + `ui_overlay.LOOKS` entries; (5) the name the user picks (asked: 竖琴清风 or 风之诗; no name until they choose).
- The lyre's history: concepts A/B/C (`dist/concepts_genshin_wind/`, workflow wf_a7491357-0f6), A2 takes, the real 斐林 found by image search (`lyre_reference_real.png`, `LYRE_REFERENCE.md`), A3 close copy approved as splash art (`A3_true_lyre/concept.png`), animated as #35.
- **Release v0.9.16:** the release check of 2026-10-16 ~02:00 (READY WITH NOTES, check_functions 22/22) predates #29–37, so it must run again (full tests, ui_shots light + dark at 100/150/200, check_functions). The notes draft (场景管理移到嘉宾页，可传3首歌 / 编辑嘉宾和组合时直接选场景 / 设置页改版，记录可一键加入名单) needs an update for #29–37 and the user's OK. Publishing only on their word.

## Next steps, in order

1. The user's music pick (#38, options in REPORT.md; already sent to them); with (a) or a listen to settle the hook, get their OK to download the official upload first.
2. Get the lyre 场景's name from the user.
3. One implementer for the lyre 场景's integration (bake ahead, 配乐, poster, SCENES/LOOKS, name), from improve/quality.
4. Small follow-ups (not blocking): posters at 960 px so the 场景管理 still is sharp (theme_posters rewrites every poster: run it when no scene branch is in flight); 演说家遇袭 takes ~0.9 s to make on its first click (claw.py `_cleared`/`fade`, `_fog_layer`, `_frayed`).
5. Release v0.9.16 when the user says so: new release check, notes, bump, make_release, sign, push, publish, check --each (memory `release-process`).

## Waiting on the user

- **The lyre 场景's name** (asked: 竖琴清风 or 风之诗) and, once #38 is read, **which music** it plays (and their OK to download it).
- **Their look in the app** at the installed build (c0fc080). To confirm with them: the 设置 button texts 导出 / 查看 / 清空.
- **Release v0.9.16**: only on their word (see Next steps 5).
- The older green 场景 stills (dist/concepts_green/, 7 ideas) are superseded by the lyre 场景 (#28/#35): nothing waits on them.

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
