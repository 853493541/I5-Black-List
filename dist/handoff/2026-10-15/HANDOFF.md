Read CLAUDE.md first (team rules, cost rules, release rules). This file is state only.

# Handoff, 2026-10-15 ~16:30 PT

## Code

| What | Where |
|---|---|
| Released | **v0.9.14** = `main` = `origin/main` = `df8957d` |
| `improve/quality` | **`e62a1f7`**, local, **not pushed**. Full tests: 665 passed, ruff clean. |
| `__version__` | `v0.9.14` |

On `improve/quality` since v0.9.14, in order:
- `fb2902d` 演说家遇袭's notice is no longer boosted; the tune is as loud as the others.
- `1f07b9c` Only `run_app` makes sound (`ui_music.allow_sound`). Tests, tools and scripts are silent.
- `10d831b` CLAUDE.md "Cost" rules.
- `c41c3e8`, `1d1458f`, `f33b2ee` 设置 loses the 声音 slider (静音 stays) and the 嘉宾 › 场景 switch. One-time migrations on load:
  - the old 声音 is folded into each 场景's 音量, rounding down, so nothing gets louder;
  - an old switch-off becomes 不放 on every 嘉宾 and 组合.
- `e62a1f7` CLAUDE.md wording for the above.

## Nothing is running

No agents and no workflows.

## Branches not merged

- **`feature/check-header`**, worktree `.claude/worktrees/check-header`, head `4a05770`. Built; NOT yet reviewed or tested by a master. Its 4 commits:
  - `b13070f` removes 用截图检查;
  - `677c356` drops 提醒, so both lists are always checked;
  - `2335c13` removes 测试框;
  - `4a05770` gives 直播模式 a header switch beside the 检查 pill, and the pill uses theme colours instead of grey.

  It sits on the OLD settings-trim commit `0f6a6c6`. Bring it over with `git rebase --onto improve/quality 0f6a6c6 feature/check-header`, then review, run the full tests and ruff, take ui_shots of the header, the 检查 panel and 记录, and merge.
- **`feature/bamboo-frame`**, worktree `.claude/worktrees/agent-a0b18785ef4023894`, head `cde23e9`. The new green 场景 「竹风」, key `bamboo`, at the concept checkpoint (v2):
  - a jade band on the edges only, bamboo, the 蛇眉铜鱼 ring, a heart, and 3 chibi pandas;
  - not in SCENES or LOOKS; no sound or poster;
  - frames in its `dist/bamboo_v2/`.

  **Waiting on the user's approval of v2.** Then the full build:
  - polish: the panda arms, the climbing panda's size, how each panda leaves;
  - its sound in `build/theme_tunes.py`, its poster, and its SCENES/LOOKS entries;
  - review, merge.

  It is a gift for a friend who mains 小说家-吴邪 (green + wind).
- **Parked, not to ship.** Leave these unless the user asks:
  - `feature/wind-notebook` (`agent-aca4fb31e9a3990eb`, rejected);
  - `feature/sheep-scene-v2` (`agent-af314d75e03110601`, 喜羊羊 dropped by the user);
  - `feature/breeze-silk` (`agent-a755becc1e757f49c`, rejected);
  - `feature/sheep-scene` and `feature/breeze-scene` (rejected v1 drafts, uncommitted).

  `.claude/worktrees/test-frame-box` is not this session's.

## Next steps, in order

1. **Merge check-header** as described above.
2. **v0.9.15 嘉宾/场景 packages.** The spec and mockups are in `dist/plan_v0915/PLAN.md`; its §0 holds the decisions taken. The user saw the summary and has not objected. Packages, in waves:
   - P1 `feature/guest-scene-editor`: the 嘉宾场景 two-pane editor, the green 我 row, the blue 组合 tag, and no 批量导入 for 嘉宾.
   - P3 `feature/clip-picker`: 选择片段 keeps playing; 截取 keeps the last 5 s; ◀ ▶ buttons; no auto-play after 确定.
   - P2 `feature/lobby-priority`: 组合 > 嘉宾 > 黑名单 > 我.
   - P4 `feature/scene-songs`: up to 3 songs per 场景 plus 默认, one chosen.
   - P5 `feature/scene-manager-dialog`: 场景管理 leaves the tabs and becomes a button right of the 嘉宾 search box that opens a modal.

   Run waves P1 ‖ P3, then P2 ‖ P4, then P5, after check-header merges. Two plan items are moot now that check-header removed 提醒 and 测试框: ignore "我 follows 提醒".
3. **竹风:** show v2 if the user hasn't answered, and do the full build after approval.
4. **Release v0.9.15** only when the user says so. Use `memory/release-process`. Update notes are at most 3 lines and say 场景, not 特效.

## Gotchas from this session

- A Bash `cd` into an agent worktree moved the desktop session's working folder. The folder move that followed restarted the session's background process and silently killed the running workflows. Use `git -C <path>` and `(cd … && …)` subshells.
- Workflows can be resumed only in the session that started them. A new session restarts them from their scripts (in `~/.claude/projects/…/workflows/scripts/`) or finishes by hand.
