Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only. The user's asks, with where
each stands, are in ASKS.md beside it: that list is what "done" means; report against it.

# Update 2026-10-16 ~18:35 local: v1.0.0 released; asks #69, #71, #72 done; stopped (commander: no new work)

- v1.0.0 published: https://github.com/853493541/I5-Black-List/releases/tag/v1.0.0 (main = improve/quality = 69eca95,
  full + update zips, check --each OK on GitHub and all 6 proxies). make_release verified 12 names.
- Ask #71: merged ee73fee, removal only (the user: "Don't add any more stuff ... Remove the hover."): every setToolTip,
  QToolTip.showText, the 详情 hover card (_DetailTip) and the tray tooltip gone; ui_theme.NoHoverText eats Qt's own
  tooltips app-wide (installed from _apply_theme); tests/test_no_hover.py walks every page and dialog. 868 passed.
- Follow-up list (not in v1.0, the commander's item 5 and the user's removal-only word): cut texts that only a hover
  showed whole: the joined load warning in the header pill, a 检查失败 reason (_watch_tip, now shown nowhere), 直播姬's
  HIDDEN/BEHIND state (cut after the comma), 添加组合 disabled with no reason shown, 选择片段 under mute; _watch_tip and
  _set_result's tip are now write-only. The first builder's versions are in the run wf_af562f6a-81f journal.
- Post-1.0 notes: runtime-save excepthook, launcher mid-Apply, 经典/cyber/neon warm, claw warm_ahead, 分享 comma,
  清空记录/清空数据 say done when a file cannot be written or was held, toasts after an unsaved change while a file is
  held, make_release relative/8.3 --out (VERIFY.md:319).
- Leftover empty folders: .claude/worktrees/agent-ae38f53789760ac49, agent-ab2cab4534a0724a8; v1-final may remain as a
  folder (its worktree entry is pruned). Not installed locally: the user's app updates itself to v1.0.0.
- Waiting on the user: CLAUDE.md lines relayed by Commander 2 (message the commander only for decisions, merges, the
  release, blockers, big estimate changes; no hover text anywhere) go in only on the user's OK.

# Handoff, 2026-10-16 ~00:55 PDT (master "BLA master", started ~23:00 by Commander 2; context ~335k, rotating)

## Code

| What | Where |
|---|---|
| Released | **v0.9.17** = `main` = `origin/main` = `origin/improve/quality` = `a290763` (GitHub + 6 proxies checked, ~01:35 PDT). Notes: 嘉宾列表显示场景色点 / 场景可选「随机」，勾选即播放 / 场景快捷键在基础模式也能看到. Release check by the master (5-hour window at 94 %): 815 tests, check_functions 22/22, ui_shots light+dark 100/150/200 (dist/release_check/v0.9.17/). |
| `improve/quality` | **`ddd4a09`** (+ this handoff), local, NOT pushed past `a290763` (v0.9.17). 828 passed, 5 skipped, ruff clean. Includes 竖琴清风's birds cut out of the friend's picture (re-cut closer in f6a7f18, ask #66; the flyer is bird F facing us, flapping both wings, 0d39360, ask #67; all three breathe calmly, the flyer's wings rest up and out, the lily bird looks into the frame, ddd4a09, ask #68) (assets/birds/, build/lyre_birds.py; fan art by Weibo @子沐子_, used at the user's decision). |
| `__version__` | `v0.9.17` |
| On the user's PC | `ddd4a09` installed (--verify) at ~15:19 local. |
| Running | nothing. |

## Done this cycle (in ASKS.md terms)

- F2 leftovers (#40's 场景管理 notes, volume-0 trim, duplicate 组合, theme switch with 场景管理 open): `4210731`.
- F1 竖琴清风 timing (#35/#38 follow-ups) + review fixes + tests: `7eb7930`..`09eee29`. Released in v0.9.16.
- v0.9.16 released on the user's word (notes: 新场景「竖琴清风」 / 嘉宾和组合可直接选场景，可传配乐 / 设置改版，记录可一键加入名单).
- UI batch #48-55 merged (`d3ef49d`..`6865a5c`), reviewed (wf_698bfea2-2e0: 2 confirmed, both fixed in `6865a5c`), installed.
  Pictures: dist/ui_batch_48/ (G1 list dots, G2 picker, sound_rows).

## Running (02:40 PDT)

- Polish A (`polish/scene-picker`: lyre first-click hitch, arrows scroll, Tab stops, 随机 preview, strike-out) and
  B (`polish/scene-manager`: left room with the hotkey note, dim layer, 选择片段 levelling, stale comments), both from
  930cd2a. Polish C merged (`db570c8`..`3891998`: 关于 long note elided, catalog always chosen, PictureResultDialog
  removed, render_gallery made-up names).
- New 场景 (#58-60): researchers on 凌雪阁 成男 (dist/research/lingxuege/) and the 模仿者 role "Yin Mojia"
  (dist/research/yinmojia/); a designer on 3 storm-night directions (dist/concepts_storm/). Pictures first, the user
  picks; no app code until then.

## Next steps, in order

1. #56 DONE: the user said yes ("the 场景 hotkey always plays on my screen ... in 基础模式 too, with or without
   直播模式, and still goes to the stream"). `dae2113` + `c77a2a1` (review wf_717cc65d-5b6: 直播模式 switched mid-play in
   基础模式 now ends the play, music and all). Merged, installed. Not checked on the real desktop yet (Alt+3 over
   another app, 基础模式 + 直播模式): the user's own press is that check.
2. The user's look at the installed build (#48-55); their verdict.
3. One desktop tester pass (ui_shots light 150) on the batch, if the user wants a v0.9.17; release only on their word.
4. Small, from the v0.9.16 release check (dist/release_check/v0.9.16/REPORT.md): 竖琴清风's first click in a dialog
   hitches ~0.2 s (ScenePreview bake start on the UI thread); 场景管理's list scrolls with its last row half cut while
   the hotkey warning shows (designed scroll, but CLAUDE.md says the left keeps room for every scene).
5. Open from before: green 场景 for the 吴邪 friend (waits on the user's pick of the 7 stills), #28 designer pictures.

## Gotchas (new)

- Offscreen pictures need `QT_QPA_FONTDIR=C:/Windows/Fonts` or Chinese draws as boxes.
- Worktrees `.claude/worktrees/ui-batch` (permission denied on remove), `agent-ab6e5f0c90018d9d1` (locked) and the
  merged agents' (`agent-a3c04...`, `agent-a7a51...`, `agent-a8f22...`, `sound-rows`, `ui-batch-base`) can be cleaned
  (ccd_host clean_up_worktrees); their branches are all merged.
- Agents hit their turn caps (implementer 60, tester 40) before reporting; a SendMessage "finish in ~15 turns and
  report" worked each time.

# Handoff, 2026-10-15 22:37 PDT (stopped by the user's #ec "end the cycle", relayed by the commander)

## Code

| What | Where |
|---|---|
| Released | **v0.9.15** = `main` = `origin/main` = `b9b35dd`. Nothing newer is published. |
| `improve/quality` | **`f5c33f1`** (+ this handoff's commit), local only, not pushed past `b9b35dd`. App code = `d1f1c04`; full tests on that merge: 790 passed, 5 skipped, ruff clean. |
| `__version__` | `v0.9.15` (not bumped) |
| On the user's PC | `d1f1c04` installed with `build/install_local.py --verify` at ~22:33 PDT (12 names verified, app restarted). |
| Worktrees / branches | none of this master's left: every package was merged or removed. Older parked ones are listed below. |

## Timeline (2026-10-15, PDT)

- ~21:20 this master starts (session started by the commander); asks the user the two open questions.
- 21:25 the user picks the name **竖琴清风** and music **(a) the real 诗人的工作**, and OKs the download. 21:27
  downloaded (dist/research/venti_music/audio/, git-ignored: the whole song, `bard_source.wav`, `lyre_preview.wav`
  sent to the user: song 0:40.45–0:45.45, the downbeat at 0:41.35 on the first strum at 0.9 s).
- ~21:30 lyre implementer starts; ~21:32 review workflow wf_e424b3a0-207 (5 finders + 5 skeptics) on b9b35dd..0f96c78.
- ~21:36 reinstall on the user's PC at the user's request (no files changed).
- ~21:45 the user's asks #39–46 (looking at the installed build) → workflow wf_e59f5ab5-67f (A, B, C, each tested).
- ~21:55 ask #47 (dropdowns like Claude's) → workflow wf_023a6eb1-de5 (D); review fixes → wf_42fa3d31-22f (E).
- ~22:00 merged #35/#38 竖琴清风 (`80b48fa`); ~22:10 D (`d0dfe3b`), E (`e8976e6`..`d49a1fc`) + stream tests' alpha for
  the jade card (`d02c185`); ~22:30 A (`ff564a3`), B (`6705063`), C (`d1f1c04`, after its fix round; rebased over
  another session's `96d172f` agent turn caps).
- ~22:33 installed `d1f1c04` on the user's PC. ~22:34 F1/F2 workflow wf_de33af10-b41 started.
- 22:37 stop (#ec): F1/F2 stopped before they changed or committed anything; their worktrees and branches removed.
- ~22:40 this handoff committed.

## Merged this cycle (all on improve/quality, none released)

- #35/#38 竖琴清风: SCENES entry (its own LOOK, no ui_overlay.LOOKS entry, like claw), `assets/lyre.wav` from
  `build/lyre_tune.py` (`START = 0.50`; `build/sounds/bard.wav`), poster at 2.95 s, bake-ahead in a thread before the
  clock starts (entrance from frame 1; 演说家遇袭 too), every poster redrawn at 960 px (`build/theme_posters.py`).
- #39–40 (A), #41–43 (B), #44–46 (C), #47 (D): see ASKS.md.
- Review fixes (E): a re-check whose winner changes (我 → 嘉宾 → 组合, or back) plays the new winner's 场景, music
  and look; a check hotkey pressed while the worker is busy leaves the marks; 清空数据 with 直播模式 on unlocks the
  黑名单 names and stops the 直播姬 watch; an unreadable settings.json is set aside and the uploaded songs recovered.
- CLAUDE.md: a new scene is SCENES + TUNES + LOOKS (or its own LOOK) + a poster.

## Next cycle (master started ~23:00 PDT by Commander 2)

- F2 **merged** (`4210731`, built by the master): a-d as listed below, f renamed, and e found real: an open
  场景管理 did not follow a theme switch at all (跟随系统 while it is open); it restyles now. 794 passed, 5 skipped,
  ruff clean. Not installed yet.
- F1 **merged** (`7eb7930` build, `baf72fa` the master's fixes from review wf_8bd27d86-a7f: a 场景 stopped before it
  shows gives its lobby back; ▶ on 场景管理 keeps its music over a 场景 that shows later; `c5daa64`/`09eee29` tests).
  improve/quality = `09eee29`: 806 passed, 5 skipped, ruff clean. Not installed yet.
- The user (23:20): "Finish F1's review, merge it, run the release check, then release v0.9.16 with those notes"
  (notes: 新场景「竖琴清风」 / 嘉宾和组合可直接选场景，可传配乐 / 设置改版，记录可一键加入名单). Release check: one tester
  with the desktop on `09eee29`, then bump, make_release, sign, push, publish, check --each.

- **v0.9.16 RELEASED** (~00:05 PDT): release check READY WITH NOTES (dist/release_check/v0.9.16/REPORT.md: 806
  tests, 325 shots light+dark 100/150/200, check_functions 22/22, v0.9.15 upgrade both ways). Commit `a2ab08c` =
  main = origin/main = origin/improve/quality. GitHub + 6 proxies serve v0.9.16 (check --each). Not installed by hand:
  the in-app update offers it. Check notes not fixed: 竖琴清风's first click in a dialog hitches ~0.2 s; 场景管理's list
  scrolls (last row half cut) while the hotkey warning shows.
- UI batch (#48-55): branch `ui/batch-48` (worktree .claude/worktrees/ui-batch) = a2ab08c + e743e87 (rename, 随机 dot)
  + 9749ab5 (G1 list dots) + 74adb19 (G2 随机 row) + bb55f3d (配乐 rows). Full tests + review workflow wf_698bfea2-2e0
  running; then fast-forward improve/quality. Pictures: dist/ui_batch_48/.
- #56 (hotkey unseen in 直播模式): researched. Not a regression: in 基础模式 + 直播模式 every mark, the hotkey's scene
  too, is WA_DontShowOnScreen and only drawn into the off-screen 直播画面 (ui.py ~2990-3005, since c13f5ca, v0.9.12).
  Fix (ui.py ~4214 and ~4328): the hotkey's play shows on screen too, back to stream-only after; needs the user's OK
  because 基础模式 exists to not draw over the game.

## Not built (stopped at #ec; the next master's first package, from improve/quality)

F1, 竖琴清风's timing (the user has not seen these yet; they come from the implementer's own report):
1. On a cold start (~2 s bake at 1920x1080) the lobby music starts at check time, so it runs ahead of the strums: start
   every scene's tune when its clock starts (LoveBorder started signal / callback; ui.py `_show_panel` music.lobby /
   music.mine, the 场景 hotkey quick play; 场景管理 ▶'s music when the preview starts, keeping C's 暂停/接着播放).
2. Warm 竖琴清风 ahead when it can be chosen and the stage is known; its pictures depend on the cards' gap, so a new
   card size bakes again (apply the gap at paint time if possible).
3. The 场景管理 / 嘉宾 dialog previews (ui_love_pick ScenePreview) make its pictures on the UI thread (~1.2 s over the
   first frames): warm off-thread first.
4. Its list dot is close to 毛茸茸保护协会's teal.
5. Tests that pick a random scene can draw 竖琴清风 (jade-glass card alpha 199, warm delay): pin or seed them. One
   unexplained test_stream failure in ~35 runs after the alpha fix.

F2, small leftovers (from the review and testers):
a. 场景管理's 场景 hotkey problem note (ui_effects.py ~119) not underlined like 检查's (#40): tone "warn".
b. 场景管理's 配乐 error notes (ui_effects.py `_tell(str(error))` ~590/~678) not underlined.
c. 选择片段 at 音量 0% acts as playing in silence: treat 0 like 静音 in `_trim`.
d. A 组合 with the same members as another can be saved (ComboDialog._accept): refuse it.
e. Offscreen, 上传 / 恢复默认 keep dark colours after a dark → light theme switch with 场景管理 open: verify.
f. Test comments still saying 放场景.

## Next steps, in order

1. Build F1 + F2 (two packages; both touch ui_effects.py in different regions), test, merge one at a time.
2. One tester full pass with the desktop (tools/ui_shots.py light 150) on the merged result; master re-shoots only
   what it flags. Real-window checks still owed: D's dropdown popup (corners, painted shadow, no roll-down, right
   edge under the text) and C's wave/⏸ rows.
3. Install locally for the user's look; their verdict on #39–47 and 竖琴清风.
4. Release v0.9.16 only on the user's word: new release check (full tests, ui_shots light + dark at 100/150/200,
   check_functions), notes (draft below), bump, make_release, sign, push, publish, check --each (memory `release-process`).
   Notes draft (needs the user's OK; ≤ 3 lines): 新场景「竖琴清风」 / 嘉宾和组合可直接选场景，可传配乐 / 设置改版，记录可一键加入名单

## Waiting on the user

- Their look at the installed build (`d1f1c04`): #39–47 and 竖琴清风; to confirm too: 设置 button texts 导出 / 查看 / 清空,
  whether #39's narrower 显示 (171 → 155 px) is narrow enough, whether the grey hotkey note underlined reads as a warning.
- Release v0.9.16 and its notes.

## Older small cleanups (not blocking)

- 嘉宾 dialogs: with more than 10 scenes, arrow keys don't scroll the list to the focused scene; empty Tab stops on
  scroll areas; a removed 嘉宾's strike-out is faint at 100%; stale comments (tests/test_likes.py:458,
  tests/test_scene_multi.py, ui_effects.py:3, model.Entry's docstring).
- 设置: a very long 检查更新 note could push the buttons off; Ctrl+click deselects the catalog row.
- 场景管理: uploading with the dialog at its minimum size lets the dim layer hang below the window until reopened.
- `PictureResultDialog` is dead in the app. 选择片段: the whole-song play is not levelled like the saved clip.

## Branches not merged (older, parked)

- `feature/bamboo-frame` (`agent-a0b18785ef4023894`, `cde23e9`): 竹风 v2, rejected (memory `bamboo-v2-feedback`).
- Parked, not to ship: `feature/wind-notebook`, `feature/sheep-scene-v2`, `feature/breeze-silk`, `feature/sheep-scene`,
  `feature/breeze-scene`. `.claude/worktrees/test-frame-box` is not this master's.

## Gotchas

- Every agent brief carries the user's seven lines (memory `brief-lines`); agents now also have turn caps of their own
  (`96d172f`: implementer 60, tester/researcher/planner 40).
- Workflow agents in parallel must not use the desktop; give the desktop to one tester after merging.
- Other sessions commit to `improve/quality` (e.g. `96d172f` this cycle): rebase right before each fast-forward.
- `dist/` is git-ignored but the handoff files are tracked: commit them with `git commit -a` (or `git add -f`).
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM: edit with Python or the Edit tool.
