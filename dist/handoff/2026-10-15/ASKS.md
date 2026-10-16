# What the user asked for (2026-10-15, 22:25–22:45 UTC, in the "[BLA] Planner" session)

The source of truth for "done". Taken from the user's own messages in transcript a44fbfc6 (queued messages at
22:25:49, 22:30:37, 22:35:50, 22:40:11, 22:43:35, 22:45:18). Report against THIS list, not against packages.
Status as of 2026-10-16 ~02:30 UTC. improve/quality = d6cdbba (+ handoff commits), local, not pushed past b9b35dd.

| # | Prompt | Job | Status |
|---|---|---|---|
| 1 | 设置 | Remove the sound volume slider (each 场景 has its own now); keep 静音 | released v0.9.15 |
| 2 | 设置 | Remove the 嘉宾 场景 on/off switch | released v0.9.15 |
| 3 | 场景管理 | 场景管理 leaves the top tabs; a button right of the 嘉宾 search box opens it as a modal | building (A / P5, workflow wf_6ca450e8-078: build → test → one fix round) |
| 4 | 场景管理 | The panel looks better; previews keep autoplay (the user dropped the "frame at max" idea) | building (part of A) |
| 5 | 场景管理 | Sound: 默认 or uploaded songs, up to 3 per 场景, one chosen | merged (d6cdbba), not released. Under 静音 every ▶ is off and says 已静音 |
| 6 | 选择片段 | Keeps playing past 5 s; 截取 takes the 5 s just heard | released v0.9.15 |
| 7 | 选择片段 | 试听 works; ◀ ▶ buttons for small moves, not only the keyboard | released v0.9.15 |
| 8 | 选择片段 | Bug: 确定 played the song once by itself; remove it; the sound row has its own ▶ | released v0.9.15; the ▶ per song merged with #5 |
| 9 | 场景 | 演说家遇袭's song is too loud; match the others | released v0.9.15 |
| 10 | 嘉宾 list | 组合 tag in blue, not the 黑名单 red | merged (482c80e), not released |
| 11 | 嘉宾 list | No 批量导入 for 嘉宾 | merged (482c80e), not released |
| 12 | 嘉宾 editor | Two panes: 嘉宾 on the left, 场景 on the right with a box each, preview below with ▶ and autoplay; 随机 on top greys the rest | merged (d5b18b6), not released |
| 13 | 我 | 我 on top of the 嘉宾 list on green; 我 can pick a 场景 | merged (482c80e row, d5b18b6 its 场景), not released |
| 14 | Priority | 组合 > 嘉宾 > 黑名单 > 我 | merged (63e5184), not released; on-game shots checked by the master |
| 15 | 检查 | Remove 用截图检查 under 记录 | released v0.9.15 |
| 16 | 检查 | The 检查 pill's grey background doesn't fit the theme | released v0.9.15 |
| 17 | 检查 | Remove the 黑名单 / 嘉宾 提醒 choices and what they do | released v0.9.15 |
| 18 | 检查 | 直播模式 out of the panel: its own switch in the header with its ⓘ | released v0.9.15 |
| 19 | 检查 | Remove 测试框 | released v0.9.15 |
| 20 | Testing | No sound from background tests unless a sound is being checked | released v0.9.15 |
| 21 | 记录 (2026-10-16 01:15 UTC) | On the 记录 page the hover 添加 button becomes two buttons on the right: a heart (add to 嘉宾) and a circle-with-slash 🚫 (add to 黑名单). A click adds at once; once added, it stays showing that state | not started |
| — | Green 场景 | For the friend who mains 吴邪 (green + wind): border only, slow entrance, cute pandas, less middle | v2 rejected; the user wants picture ideas first. 7 concept stills sent 2026-10-16 (dist/concepts_green/: all_concepts.png + one folder per idea with its script): 1 草原风车, 2 竹风铃, 3 风筝, 4 水墨竹, 5 山雾萤火, 6 青铜门, 7 柳与燕. Waiting for the user's pick; then one concept frame of it, then the build. |

"Just changing UI for now" (22:40): no 直播模式 checklist is to be built.

Totals: 12 released, 6 merged not released (5, 10–14), 2 building (3, 4), the green 场景 waiting on the user.
Release v0.9.16 only on the user's word, after #3–4 merge and the final release check (dark theme and 100/200 % shots there).
