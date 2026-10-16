# What the user asked for (2026-10-15, 22:25–22:45 UTC, in the "[BLA] Planner" session)

The source of truth for "done". Taken from the user's own messages in transcript a44fbfc6 (queued messages at
22:25:49, 22:30:37, 22:35:50, 22:40:11, 22:43:35, 22:45:18). Report against THIS list, not against packages.
Status as of 2026-10-16 ~02:20 UTC (local 19:20 PT). All of 1-27 are merged on improve/quality 902d56f and installed on the users PC (install_local); 1-2, 6-9, 15-20 are also in v0.9.15. Nothing past v0.9.15 is published. improve/quality = d6cdbba (+ handoff commits), local, not pushed past b9b35dd.

| # | Prompt | Job | Status |
|---|---|---|---|
| 1 | 设置 | Remove the sound volume slider (each 场景 has its own now); keep 静音 | released v0.9.15 |
| 2 | 设置 | Remove the 嘉宾 场景 on/off switch | released v0.9.15 |
| 3 | 场景管理 | 场景管理 leaves the top tabs; a button right of the 嘉宾 search box opens it as a modal | merged (21c0c6f), not released |
| 4 | 场景管理 | The panel looks better; previews keep autoplay (the user dropped the "frame at max" idea) | merged (21c0c6f + 9e5de32: no blank song rows, old notes cleared on reopen), not released |
| 5 | 场景管理 | Sound: 默认 or uploaded songs, up to 3 per 场景, one chosen | merged (d6cdbba), not released. Under 静音 every ▶ is off and says 已静音 |
| 6 | 选择片段 | Keeps playing past 5 s; 截取 takes the 5 s just heard | released v0.9.15 |
| 7 | 选择片段 | 试听 works; ◀ ▶ buttons for small moves, not only the keyboard | released v0.9.15 |
| 8 | 选择片段 | Bug: 确定 played the song once by itself; remove it; the sound row has its own ▶ | released v0.9.15; the ▶ per song merged with #5 |
| 9 | 场景 | 演说家遇袭's song is too loud; match the others | released v0.9.15 |
| 10 | 嘉宾 list | 组合 tag in blue, not the 黑名单 red | merged (482c80e), not released |
| 11 | 嘉宾 list | No 批量导入 for 嘉宾 | merged (482c80e), not released |
| 12 | 嘉宾 editor | Two panes: 嘉宾 on the left, 场景 on the right with a box each, preview below with ▶ and autoplay; 随机 on top greys the rest | merged (d5b18b6), not released; the user tried it 2026-10-16 and changed it: superseded by #22–24 |
| 13 | 我 | 我 on top of the 嘉宾 list on green; 我 can pick a 场景 | merged (482c80e row, d5b18b6 its 场景), not released |
| 14 | Priority | 组合 > 嘉宾 > 黑名单 > 我 | merged (63e5184), not released; on-game shots checked by the master |
| 15 | 检查 | Remove 用截图检查 under 记录 | released v0.9.15 |
| 16 | 检查 | The 检查 pill's grey background doesn't fit the theme | released v0.9.15 |
| 17 | 检查 | Remove the 黑名单 / 嘉宾 提醒 choices and what they do | released v0.9.15 |
| 18 | 检查 | 直播模式 out of the panel: its own switch in the header with its ⓘ | released v0.9.15 |
| 19 | 检查 | Remove 测试框 | released v0.9.15 |
| 20 | Testing | No sound from background tests unless a sound is being checked | released v0.9.15 |
| 21 | 记录 (2026-10-16 01:15 UTC) | On the 记录 page the hover 添加 button becomes two buttons on the right: a heart (add to 嘉宾) and a circle-with-slash 🚫 (add to 黑名单). A click adds at once; once added, it stays showing that state | merged (7c1ae51), not released. The tester caught that a real mouse never lit the seat; fixed and proved with a real cursor and real clicks |
| 22 | 嘉宾 dialogs (2026-10-16 01:25 UTC) | 添加嘉宾 / 编辑嘉宾 pick the 场景 in the same dialog: 名字/昵称/原因 + a 放场景 box + the scene list one per row with boxes + preview with ▶ and autoplay. No list of other 嘉宾 ("why should I see the full list of guests") | merged (2bbd20b), installed on the users PC, not released |
| 23 | 放场景 | The box says 放场景: unchecked = 不放; checked with none ticked = random among all; ticked = those, random among them if several | merged (2bbd20b), installed on the users PC, not released |
| 24 | 组合 dialogs | 添加组合 / 编辑组合: left, the 嘉宾 with checkmarks to pick members; right, the scene list one per row; bottom, the preview ("editing combo is completely trash, has no scene selection") | merged (2bbd20b), installed on the users PC, not released |
| 25 | 设置 (2026-10-16 01:30 UTC) | Bug: "on the first row, the second row is merged to the first row for no reason" (常规's 开机启动 and 关闭窗口时 share one row) | merged (fc6dc1e), installed on the users PC, not released. Button texts shortened to 导出 / 查看 / 清空 (to confirm with the user) |
| 26 | 设置 | Redesign "the Claude way" (the user pasted Claude's settings): a catalog of sections on the left, the chosen section on the right; each row has its name and a description on the left and its control on the right | merged (fc6dc1e), installed on the users PC, not released. Button texts shortened to 导出 / 查看 / 清空 (to confirm with the user) |
| 27 | Header (2026-10-16 01:40 UTC) | "On the top right we have too much to display ... I know I just split that out ... just merge that back first" — 直播模式 leaves the header and goes back into the 检查 panel (undoes the header switch of #18; the pill colours, no 提醒, no 测试框 stay). "I will see what next change is" | merged (3e25cf3), not released; the panel also shrinks back when 直播模式 is turned off in it |
| 28 | Green 场景 v3 (2026-10-16 02:30 UTC) | From the friend: "原神风系小男孩" — 枫原万叶 and 温迪 (two Bilibili GMV links: BV1gU4y1V7Bw 万叶, BV1wy4y1t7MJ 温迪). Elements like 竖琴 (lyre), 枫叶 (maple leaves), 羽毛 (feathers); the frame green, maple leaves may be red, feathers white. "Plan a scene based on this, have three agents start designing together after researching" | research → plan → 3 designers (workflow, see HANDOFF "Running"); pictures to the user, who picks |
| 29 | 嘉宾 page (2026-10-16 03:30 UTC) | "move the button out to add a guest and add a combo": the 添加 menu becomes two buttons, 添加嘉宾 and 添加组合 | building (one agent for 29-32, as the user asked) |
| 30 | 添加/编辑嘉宾 | 放场景 starts OFF for a new 嘉宾 (master: and a new 组合); unchecked it shows no hint, checked it says "不勾选场景则随机播放"; 名字 and 昵称 on one row, leaving more room below; editing looks the same as adding | building |
| 31 | 添加/编辑组合 | Left column: the 嘉宾 list on top in a box with more room ("not enough box"), the preview bottom-aligned; the label 嘉宾 renamed 已添加的嘉宾; the right (scene list) is right as is; editing the same as adding | building |
| 32 | 场景管理 | The 场景 hotkey is shared, so it moves to the top of the LEFT panel: 快捷键 [box] with "播放勾选的场景" (the scene ticked in the list plays on the current window; the ✓ becomes clickable to pick it); the right side loses 快捷键放这个 and the 播放 button ("I don't even know what's that for"); 声音 renamed 配乐; under the preview the first row is 配乐 · 音量 · a clear ▶ play button outside the preview (the ▶ in the preview corner "is not so obvious"); then 默认 and the uploaded songs | building |
| — | Green 场景 | For the friend who mains 吴邪 (green + wind): border only, slow entrance, cute pandas, less middle | v2 rejected; the user wants picture ideas first. 7 concept stills sent 2026-10-16 (dist/concepts_green/: all_concepts.png + one folder per idea with its script): 1 草原风车, 2 竹风铃, 3 风筝, 4 水墨竹, 5 山雾萤火, 6 青铜门, 7 柳与燕. Waiting for the user's pick; then one concept frame of it, then the build. |

"Just changing UI for now" (22:40): no 直播模式 checklist is to be built.

Totals: 12 released, 6 merged not released (5, 10–14), 2 building (3, 4), the green 场景 waiting on the user.
Release v0.9.16 only on the user's word, after #3–4 merge and the final release check (dark theme and 100/200 % shots there).
