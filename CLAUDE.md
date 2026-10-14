# 模仿者小工具 (blacklist_detect)

Windows desktop app. On a hotkey it copies the screen, reads the twelve names in the 模仿者狂欢 lobby with
PaddleOCR, and marks 黑名单 and 心动 players on the game. Friends get it as GitHub releases with in-app
updates. README.md covers running it and the OCR model.

## Layout

- `blacklist_detect/`: the app. `ui.py` (MainWindow, about 4,500 lines) is where most changes land; the
  `ui_*.py` modules split the rest by area; `love_scenes/` has one module per 心动 scene; pictures and
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
- Every choice in 设置 lists its default first. 设置 fits 900x760 without scrolling, so it gets no new rows.
  Every dialog fits 672 px of usable height (1080p at 150%) with its buttons in view;
  `tests/test_dialog_fit.py` guards this. 心动特效 is the tallest, so a row added there is paid for elsewhere.
- `reference-lobby.png` and `assets/sample-lobby.jpg` are crops of a lobby, not whole screens. Check
  anything about where the game, border or cards sit on a whole 16:9 frame.
- Child processes get `paths.child_env()`. Paddle sets `OMP_NUM_THREADS=1`, which made OCR in a child
  3-14x slower.
- A new 心动 scene is a `love_scenes` module plus entries in `SCENES` and `ui_overlay.LOOKS`. Render it at
  full size over the sample lobby and look at it (small tiles hide flaws); its median frame stays under
  20 ms at 1920x1080. 经典花边 (classic) stays exactly as it is. Shade per pixel: flat vector gradients
  read as cheap clip-art to the user.
- Chosen on purpose, not defects: red tags everywhere, 无 in red in 心动特效, 检查失败 (not 无法检查).
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
