# 模仿者小工具 (blacklist_detect)

Windows desktop app. On a hotkey it copies the screen, reads the twelve names in the 模仿者狂欢 lobby with
PaddleOCR, and marks 黑名单 and 嘉宾 players on the game. Friends get it as GitHub releases with in-app
updates. README.md covers running it and the OCR model.

## Layout

- `blacklist_detect/`: the app. `ui.py` (MainWindow, about 4,500 lines) is where most changes land; the
  `ui_*.py` modules split the rest by area; `love_scenes/` has one module per 嘉宾 scene; pictures and
  sounds are in `blacklist_detect/assets/`.
- `tests/`: pytest. `tests/fixtures/reference-lobby.png` is a real lobby.
- `tools/ui_shots.py`: screenshots of every page, dialog and on-game card, per Windows scale.
- `build/`: release scripts; update notes in `build/notes/<version>.txt`.

## Commands

Run them from the root of the checkout you work in, so the code tested is that checkout's. In the main
checkout:

```bash
PYTHONPATH=. .venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
```

An agent worktree (`.claude/worktrees/<name>`) has no `.venv`; it uses the main checkout's, three
folders up:

```bash
PYTHONPATH=. ../../../.venv/Scripts/python.exe -m pytest -q
../../../.venv/Scripts/python.exe -m ruff check .
```

Inside an agent worktree, run commands one per call and as written: a command whose program is a variable
(`"$PY"`), a quoted path with spaces, or a chain of steps is refused there. pytest prints its own time.

The full run is about 400 tests in under a minute. The OCR reference tests use every core. A timing test that fails while another test run is going is
rerun alone before it counts as a failure.

## Rules

- Pictures shown to users (assets, guides, samples, screenshots for the user) use made-up names:
  示例坏人, 心动小鹿, 心动星星, or the `SEATS` in `tools/ui_shots.py`. The real names in
  `tests/fixtures/reference-lobby.png` never appear in anything user-facing. Check a new asset before
  committing it.
- Every choice in 设置 lists its default first. 设置 is laid out the way Claude's settings are (the user's ask):
  a catalog on the left (常规, 外观, 帮助, 关于), and for the chosen section one row per setting, its name and a gray
  line on what it does on the left, its control on the right. A new setting is a row in the section it belongs
  to; each section fits the window at 900x560 without scrolling. 检查's own settings stay in the panel under the
  header's 检查 pill (显示, 方式, 直播模式).
  Every dialog fits 672 px of usable height (1080p at 150%) with its buttons in view;
  `tests/test_dialog_fit.py` guards this. 添加嘉宾 / 编辑嘉宾 are the tallest (their fields and preview beside a list
  of every scene), then 场景管理; a scene added makes the scene lists scroll in their column rather than grow a dialog.
- `reference-lobby.png` and `assets/sample-lobby.jpg` are crops of a lobby, not whole screens. Check
  anything about where the game, border or cards sit on a whole 16:9 frame.
- Child processes get `paths.child_env()`. Paddle sets `OMP_NUM_THREADS=1`, which made OCR in a child
  3-14x slower.
- A new 嘉宾 scene is a `love_scenes` module plus entries in `SCENES` and `ui_overlay.LOOKS`. Render it at
  full size over the sample lobby and look at it (small tiles hide flaws); its median frame stays under
  20 ms at 1920x1080. 玫瑰花边 (lace, the app's first border, once 经典花边) stays exactly as it is. Shade per pixel: flat vector gradients
  read as cheap clip-art to the user.
- Chosen on purpose, not defects: red tags everywhere except the 嘉宾 list's blue 组合 tag and green 我 row (the player
  asked for them), 静音 a checkbox in 常规's 声音 row (the player asked for one), 检查失败 (not 无法检查).
- Only the app as the player runs it makes a sound (`run_app` calls `ui_music.allow_sound`). Tests, `tools/ui_shots.py`,
  the release check and agents' scripts stay silent; the user hears every sound played in the background. Set
  `BLACKLIST_DETECT_SOUND=1` only when a sound itself is being checked by ear, and say so.
- The user's own list, settings and running copy of the app are never touched. Tests and tools run in a
  data folder of their own (`APPDATA` pointed elsewhere, as `ui_shots.py` does).
- Update notes: at most 3 lines of about 15 字, saying what changed for the player. No how-to, no reasons.
- Code reads like the code around it. Ruff, line length 130. Commit messages are one sentence on what
  changed for the player (see `git log`); release commits start with `vX.Y.Z:`.

## Branches

- `main`: releases only, fast-forwarded from `improve/quality` when a version is published.
- `improve/quality`: where finished work lands. Other sessions commit here at the same time, so work on a
  branch of your own and fast-forward.
- `feature/<slug>`, `fix/<slug>`: one branch per piece of work, each in its own worktree.

## Working as a team

The session talking to the user is the master. It plans with the user, hands work to the agents in
`.claude/agents/`, checks what comes back, merges, and reports. Agents see this file and the prompt
they are given, nothing of the conversation or the master's memory, so a brief carries everything the
agent needs. Agent worktrees are under `.claude/worktrees/`; a worktree with commits stays until
`git worktree remove <path>`.

- `planner`: splits a request into work packages, each with its branch, the files it touches, how it
  is tested, and whether it needs the desktop. Read-only.
- `researcher`: answers one question with evidence (file:line, measurements). Read-only.
- `implementer`: builds one package on its own branch in its own worktree, tests it, commits. Never
  merges or pushes.
- `tester`: tests one branch in its worktree and tries to break it. Never edits code.

Every agent, the four above and any workflow or one-off agent, runs on Opus at effort high, and high is the
maximum: no extra high, no max (the user's rule, 2026-10-15; the same in ZPS `AGENTS.md`). Name the model on every
call: an agent call without one inherits the master's. The master itself runs on Opus with Ultracode on. No Fable
anywhere: it was unstable and too expensive (Fable masters burned about 26 % of the 5-hour window per hour, against
about 15 % for Opus masters).

The master's rules:

1. Small or back-and-forth changes (UI polish, wording) the master makes itself. The team is for work
   big enough to plan.
2. Give each implementer its base as a commit hash (`git rev-parse improve/quality`); an agent's
   worktree starts from `origin/main` and the implementer moves it there. Only committed work is in a
   worktree: commit first, or leave packages that need uncommitted work for later.
3. Implementers run side by side only when their file lists do not overlap. Packages that touch the same
   file (usually `ui.py`) run one after another, each from the previous merge.
4. One merge at a time: bring the branch up to the current `improve/quality`, run the full tests and
   ruff on the result, then fast-forward `improve/quality`. Remove the worktree and branch afterwards.
5. The desktop is one agent at a time, granted by name in the brief: anything that opens real windows,
   takes screenshots, presses hotkeys, or drives MuMu or 直播姬, `tools/ui_shots.py` included.
6. An agent's "done" is checked, not trusted: the master reads the diff and runs the tests itself.
7. Pushing, releasing and publishing are the master's, after the user says so.

### Cost

Measured on 2026-10-15; the same numbers are in the user's other project (ZPS `AGENTS.md`, "Token cost"). Agents
are most of the spend, and a session's 5 longest agents were 84% of its agent spend. Every turn re-reads the
whole conversation, and command output and file reads are almost all of what fills an agent.

- Agents keep output small: commands with short output (`pytest -q`, `git diff --stat` before a full diff), and
  big files such as `ui.py` read by line range after a grep, never whole.
- Read less, read once: file reading is about 90 % of what fills an agent. Grep first, read only the lines needed,
  put several ranges or files in one call, never re-read what is already in the conversation, and for a big file
  write the parts that matter into a temp note and work from that.
- Fewer turns: every turn re-reads the agent's whole start (about 60-80k tokens), so independent reads, greps and
  checks go into one turn, never one small read per turn.
- No tiny agents: a step shorter than about 10 turns does not get its own agent. Fold it into the brief of the agent
  that needs it, or continue a running or just-finished agent with SendMessage instead of starting a fresh one.
- A package is sized to finish in about 50 agent turns. An agent that gets there unfinished commits what works,
  reports what is done, what is next and the commit to continue from, and stops; the master starts a fresh agent
  from that commit.
- Agent reports are about 30 lines: verdict, commits, files, open items.
- Screenshots (`tools/ui_shots.py`) open real windows on the user's screen and were the most repeated check (51
  runs in 75 minutes on 2026-10-15). Per package: the implementer shoots once, at the end; the tester makes the
  one full pass; the master re-shoots only what the tester flagged. Light theme at `--scale 150`; 100 and 200 only
  when the change is about layout or scale. Dark theme (`--dark`) only in the final release check before
  publishing. Never two screenshot runs at once: the desktop is one agent at a time (rule 5 above).
- The master's own conversation: once it passes about 300k tokens, or when a batch of work is done, the master
  writes a handoff to `dist/handoff/<date>/HANDOFF.md` and the work continues in a fresh session that reads it.
  The handoff holds state only (branches, commits, what is running, next steps); the rules stay in this file.
  The master updates it after each merge, so a session that runs out of usage loses nothing.
- The user's asks are state, so every handoff carries them: each ask in the user's own words with its status (not
  started, building, merged, released), in the handoff or in an `ASKS.md` beside it. A new ask goes on the list the
  moment it arrives. That list is what "done" means: the master reports progress against it, never in package names
  alone. (2026-10-15: a handoff that carried only the packages lost the user's 20 asks, and an hour of real work,
  a release included, read to the user as nothing done.)
