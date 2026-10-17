# 温迪's music for the lyre 场景 (ask #38)

Workflow wf_83277528-06f, 2026-10-16: three researchers, a verifier, a summary (all read-only, nothing downloaded).
The summary comes first; the verification and the three reports follow as they came back.

# 温迪's music for the lyre 场景

## 1. 温迪's music: what it is and where it comes from

His piece is **《诗人的工作》 / "Bard's Adventure"**. It is the music of his character demo 「温迪：诗人的工作」 ("Venti: A Bard's Business"). 陈致逸 (Yu-Peng Chen) composed it and 苑迪萌 arranged it. It is track 01 of HOYO-MiX's *闪耀的群星 / The Stellar Moments* and runs 1:47 (NetEase id 1817410055).
- Official upload: https://www.youtube.com/watch?v=APFVfv9klmg (HOYO-MiX). The demo on Bilibili is BV1st4y1q7V4, uploaded by 原神 (10.2 M views).
- Track lists: https://wiki.biligame.com/ys/闪耀的群星 (01 诗人的工作, 角色演示-温迪) and https://www.shazam.com/en-us/album/1666680443/genshin-impact-the-stellar-moments-original-game-soundtrack
- Instruments, from the Fandom wiki credits: violin, electric and acoustic guitar, and a string quartet. No lyre or harp is credited, so the plucked sound is most likely guitar.

How strongly players tie each piece to him:
1. **诗人的工作.** Fan uploads title it "Venti's Theme", for example https://www.youtube.com/watch?v=f8JIqJwm0mU and the concert upload X77EwmxF3dE. HOYO-MiX plays it as 温迪's piece in its concerts (Symphony 2022, Concert 2023, Tour 2024, per wikiwiki.jp/genshinwiki/BGM). It was also used in the 3.5 风花节 rhythm event. *Not confirmed:* that HOYO-MiX itself calls it "Venti's theme". Its official title is only "Bard's Adventure".
2. **希望的和风 / "A Yearning Breeze".** Music for his story quest 「若你困于无风之地」: https://www.youtube.com/watch?v=P8x-HrWRuso
3. **Weaker ties, from the 风龙 prologue:**
   - 重归青天的歌 "Welcome Back, My Companion" (0mi0F4zqGow).
   - 追忆 "Reminiscence" (K8aLWuJVCEw). It shares its theme with the in-game lyre song, which was never released.

## 2. The most representative part

These times come from YouTube's most-replayed data. Nobody has listened yet.

- **诗人的工作, 0:40–0:45 in APFVfv9klmg.** Replays climb from 0:36, reach 0.94 at 0:40 and peak at 1.00 at 0:42.5–0:43.6. The English demo (TSsWsCdiiPI) peaks at the same spot, 0:36–0:44, top at 0:39.9. This is the part players come back to most.
- **Second choice: 1:04–1:09 of the same upload.** Replays stay at 0.98–1.00 from 1:04.3 to 1:09.8.
- **希望的和风:** no replay data was gathered, so there is no timestamp for it.
- **Still open:** whether 0:40–0:45 is a clean phrase, and whether its accents fall near the 场景's strums at 0.9, 2.9 and 4.4 s.
  - **How to settle it:** someone listens to 0:36–0:50 and 1:04–1:10 of the official upload. A cut for testing needs your OK to download it. Checking it inside the app also needs `BLACKLIST_DETECT_SOUND=1`, which is said out loud first.

## 3. The friend's GMVs

Neither GMV uses Genshin music. Both were uploaded by 霍宝Moira.
- **温迪, BV1wy4y1t7MJ:** "If Rain" by 萨吉. It is an insert song (插曲) from the drama 以家人之名 (https://zh.wikipedia.org/wiki/以家人之名). The danmaku is busiest at 1:20–1:35, where viewers comment "bgm绝了".
- **万叶, BV1gU4y1V7Bw:** "Rain" by 秦基博. It is the ending song of the film 言の葉の庭 (https://ja.wikipedia.org/wiki/言の葉の庭).
- **万叶's own music,** for comparison: 流风无涯 "Flow of Autumn Wind" (his demo) and 荒波椛叶 "Drifter's Destiny" (his teaser). Both are from *The Stellar Moments Vol. 2*, per https://classical.music.apple.com/us/album/1605918576

## 4. How it becomes the 场景's 配乐

The app's rule is that its built-in tunes are its own or public domain, so a stream can carry them. The 喜羊羊 场景 kept to that rule and did not ship the real theme song.
- **(a) Ship a 5 s cut of 诗人的工作 as the default.** It needs a download (your OK), a small mixing script and a test. It breaks the stream rule and risks a takedown, which would stop updates for everyone. The only time this was done before (演说家遇袭) was your explicit choice.
- **(b) Replay the 诗人的工作 melody on the app's own harp, timed to the three strums.** This is about one function of code. No recording ships, but the melody still belongs to HoYoverse, and someone has to work it out by ear first.
- **(c) An original lyre tune in the same mood:** harp notes rolled on each strum plus a soft wind sound. The work is the same as (b), and it is safe for the stream.
- **(d) You upload 诗人的工作 yourself through 场景管理** and pick 0:40–0:45 in 选择片段. This needs no code and already works. Any stream risk sits with your own copy.

**Recommendation: (c) as the default plus (d).** Every 场景 needs a built-in tune, so (c) fills that safely, and (d) puts the real 温迪 theme on the scene for you. This is the same plan as 喜羊羊. Choose (a) only if you accept the takedown risk, as you did for 演说家遇袭.

---

## Research report 1

The repo can give the lyre 场景 its 配乐 four ways, and only two of them keep the stream rule. The rule (build/theme_tunes.py:9-10, blacklist_detect/ui_music.py:6) is that tunes are the script's own or public domain, so a stream can carry them. (c), an original lyre tune made by the build script, keeps it. So does (d), where the default stays the app's own and the player uploads the real song through 场景管理 himself, which needs no code. Both are the same plan as the 喜羊羊 scene (dist/handoff/2026-10-15/briefs/sheep-v2-concept.md:58-65).

I could not confirm an official 温迪 theme track. The two GMVs the friend sent don't use Genshin music. 温迪's uses 萨吉 "If Rain"; 万叶's uses 秦基博 "Rain".

Read in the main checkout at d08725d (fix/scene-manager-speed) and the worktree at 84386f2 (feature/lyre-scene).

**How a 配乐 is made and played**
- Each tune is rendered by a script, not recorded: mono, 16-bit, 44.1 kHz, as long as its scene, about -19 dBFS with peaks under -3 dBFS (theme_tunes.py:14, wedding_tunes.py:8-9).
- The script's instruments include `harp` (wedding_tunes.py:71) and `music_box` (:59); the sample rate `SR = 44100` is at :20.
- `finish()` cuts to length, fades and levels (wedding_tunes.py:140-146); `write()` is at :194. 星河许愿's harp and music box are a model to copy (theme_tunes.py:273-292).
- Tunes are listed in `TUNES` (ui_music.py:34). The worktree has no "lyre" entry yet. `tests/test_love_music.py:34` requires every scene except 经典 to have a tune, so a TUNES line is needed whichever option is picked.
- The exception is 演说家遇袭: its music is the game's own recording, the 指挥家 music cut from its start, "the user chose it knowing NetEase owns it" (build/ambush_tune.py:5-6, ui_music.py:7-8).
- For 喜羊羊, the real theme song was not shipped for copyright reasons ("a GitHub takedown would kill updates for everyone"), and the player can upload it himself (sheep-v2-concept.md:64-65).
- **Player uploads:** up to `MAX_SONGS = 3` per 场景 (storage.py:28). Each is cut to `CLIP_S = 5.0` s (sound_import.py:45) and levelled to `TARGET_RMS_DBFS = -19.0` (:49). 选择片段 picks which 5 s (`LIMIT_S = 5.0`, ui_sound_trim.py:37), and 上传 is in ui_effects.py:563-625.
- **The lyre scene:** `DURATION = 5.0` (lyre.py:36) and `STRUMS = ((0.9, 0.06), (2.9, 0.07), (4.4, 0.07))` (lyre.py:68). That is a strum at 0.9, 2.9 and 4.4 s across 7 strings, left to right, 0.06 or 0.07 s apart, so each strum takes about 0.36-0.42 s (lyre.py:333-341).

**What each option takes**
- **(a) A 5 s cut of an official recording as the default:** someone downloads it (needs the user's OK), adds a mixing script like ambush_tune.py, `assets/theme-lyre.wav` and the TUNES line. It breaks the stream rule and carries the takedown risk the 喜羊羊 brief rejected. The 演说家遇袭 recording is the only precedent, and it rested on the user's explicit choice. Also, nothing confirmed exists to cut: none of the sources I could read names a 温迪 track.
- **(b) The official motif re-played on the script's harp, its notes landing on the three strums:** about one function (`lyre_take()`) plus the TUNES line. It ships no recording, but the melody is still HoYoverse's, so the "own or public domain" rule still doesn't hold. Someone would also have to work out the motif by ear, and no source for it is confirmed.
- **(c) An original tune in the same mood:** the same work as (b), within the rule. For example, 7 harp notes rolled at each strum's start and spacing, a soft wind sound, `finish(sig, 5.0, fade)`.
- **(d) The player uploads the song through 场景管理:** no code, and it already works. The default stays (c) or the game's own; the 5 s and the level are handled by 选择片段. Stream risk sits with the player's own copy.

**Music I found for the characters**
- **万叶:** his demo track appears as "Kaedehara Kazuha: Wandering Winds" ([last.fm](https://www.last.fm/zh/music/New+Character+Demo/+tracks)), and a teaser "Kaedehara Kazuha: Moonlit Breeze" appears in sheet-music listings ([shaint.gumroad.com](https://shaint.gumroad.com)). These are fan and aggregator sources, not HoYoverse.
- **温迪:** his demo is called "Venti: A Bard's Business", from version 1.4 ([sportskeeda](https://www.sportskeeda.com/esports/news-genshin-impact-1-4-update-venti-s-character-demo-officially-released)). I found no title for its music. [Wikipedia](https://en.wikipedia.org/wiki/Venti_(Genshin_Impact)) names no 温迪 music, and the Fandom wiki's 温迪 and 万叶 Media pages returned HTTP 402.
- **The GMVs:** credits read from the Bilibili API descriptions. 温迪's ([api](https://api.bilibili.com/x/web-interface/view?bvid=BV1wy4y1t7MJ)) says "BGM：If Rain—萨吉"; 万叶's ([api](https://api.bilibili.com/x/web-interface/view?bvid=BV1gU4y1V7Bw)) says "BGM:秦基博 (はたもとひろ) - Rain". Both are by the uploader 霍宝Moira.

**What I could not settle**
- The name of 温迪's demo music, and which part of it is most representative. Someone can check the official 温迪 demo's YouTube credits or the HOYO-MiX album track lists on Spotify or Apple Music, then pick the bars by listening. That needs the desktop and audio, which this brief did not grant.
- Whether HoYoverse tolerates fan apps carrying its music. I found no policy page.

---

## Research report 2

The friend's two GMVs don't use Genshin music. 霍宝Moira, the uploader of both, picked a pop song for each, and neither song is linked to the character. Each character does have its own official music, listed at the end.
- **温迪 (BV1wy4y1t7MJ)** uses "If Rain" by 萨吉 (Saji). It is an insert song (插曲) from the 2020 Hunan TV drama 以家人之名 (Go Ahead), not Genshin music. The video is 210 s long. The viewers' peak is about **1:12–1:35**.
- **万叶 (BV1gU4y1V7Bw)** uses "Rain" by 秦基博 (Motohiro Hata). It is the ending song of Makoto Shinkai's 2013 film 言の葉の庭 (The Garden of Words), a cover of a song by 大江千里. The video is 219 s long. There is no single strong peak; the clearest marks are **0:39**, **1:01** and **2:06–2:10**.

**Sources that worked**
- The video data API (`api.bilibili.com/x/web-interface/view?bvid=…`) gave the title, length and description:
  - 温迪: aid 802242472, cid 316330286, duration 210, description credits "If Rain—萨吉".
  - 万叶: aid 673883647, cid 363203046, duration 219, description credits 秦基博 - Rain.
- The comments API (`api.bilibili.com/x/v2/reply?type=1&oid=<aid>&sort=1`) shows the uploader's pinned comment on each video, naming the same songs ("BGM：If Rain—萨吉" with 1049 likes, "BGM:秦基博 - Rain" with 933 likes). No comment gives a timestamp or the word 高能.
- The tags API (`api.bilibili.com/x/tag/archive/tags?bvid=BV1wy4y1t7MJ`) has no music tag, only plain tags such as 温迪, 风花节 and GMV.
- The 高能进度条 data (`bvc.bilivideo.com/pbp/data?cid=…`) returned 404 for both videos.
- The danmaku (`comment.bilibili.com/<cid>.xml`, raw deflate) worked. I read it as text, counted comments per 5 s, and searched for keywords:
  - **温迪, 804 danmaku.** Apart from the opening, the busiest stretch is 80–95 s (29, 35 and 26 per 5 s). The comments there:
    - 72.6 s: "就是这个瞬间！屹立于天地之间的，神明！"
    - 81.2 s: "这个踩点绝了"
    - 83.0 s: "绝了"
    - 89.0 s: "bgm绝了"
    - A second, smaller rise comes at 150–178 s (about 25 per 5 s).
  - **万叶, 799 danmaku.** After the opening (0–10 s, mostly "来了") the count stays flat. The comments that stand out:
    - 39.1 s: "前方高能"
    - 61.2 s: "这里绝了"
    - 126–130 s: a burst of "这个眼神！"
    - 7.9 s and 20.8 s: viewers name the song as 言叶之庭's Rain.
- Sources for the songs:
  - "If Rain": https://zh.wikipedia.org/wiki/以家人之名 (soundtrack track 6, 插曲; lyrics by 萨吉, music by 孙秋 and 金东映).
  - "Rain": https://www.allcinema.net/cinema/pdf/344686 and https://utaten.com/specialArticle/index/1880.

**The characters' official music** (Genshin wiki's own text, read through `genshin-impact.fandom.com/api.php?action=parse&page=…`)
- **温迪:** "Bard's Adventure" (诗人的工作), track 1 of *The Stellar Moments* (2021). It plays in his Character Demo and was also used in the 风花节 event. Composed by 陈致逸, arranged by 苑迪萌. Confirmed by https://www.shazam.com/en-us/album/1666680443/genshin-impact-the-stellar-moments-original-game-soundtrack.
- **万叶:** two tracks on *The Stellar Moments Vol. 2* (2022-01-26), both composed by 苑迪萌 with shakuhachi:
  - "Flow of Autumn Wind" (流风无涯), track 10, from his Character Demo.
  - "Drifter's Destiny" (荒波椛叶), track 9, from his Character Teaser.
  - Track list: https://classical.music.apple.com/us/album/1605918576.

**What I could not settle**
- **Song timestamps.** The peaks above are in video time. I did not listen to anything and did not download audio, so I can't say which part of each song (chorus or bridge) they fall on, or where the climax of the official tracks is. To settle it, someone listens to the GMVs at 1:12–1:35 and 0:39/1:01, and to the NetEase pages for the official tracks (song ids 1817410055, 1913532412 and 1913533270). The ids come from the wiki's citations; I did not open those pages.
- **Licensing.** Both GMV songs are commercial releases from a TV drama and a film. The HoYoMiX tracks belong to miHoYo. I did not check whether any of them may ship inside the app.

Scratch files (danmaku counts, track text) are in `C:\Users\ZHIBIN~1\AppData\Local\Temp\claude\C--Users-Zhibin-Ren-Desktop-Black-List-App\4e73d4f5-e751-4fc2-9a63-5de144d4da0e\scratchpad\`. Nothing in the repo was changed.

---

## Research report 3

**Answer.** The track most players know as "温迪's theme" is **《诗人的工作》 / "Bard's Adventure"**, the music of his character demo 「温迪：诗人的工作」 ("Venti: A Bard's Business"). Yu-Peng Chen (陈致逸) composed it and HOYO-MiX released it as track 01 of *The Stellar Moments* (闪耀的群星), the first character-theme album. Fans title their uploads "Venti Theme" or "Venti's Theme", and HOYO-MiX plays it as Venti's piece in its official concerts. For the part players come back to most, YouTube's most-replayed data on HOYO-MiX's upload points to about **0:41 to 0:44**. A second plateau runs about 1:03 to 1:10. I could not listen to the track, so this is a lead to check by ear, and I could not confirm the key, tempo or notes.

**Ranked by how much players tie it to 温迪**
1. **诗人的工作 / Bard's Adventure.**
   - Official upload: HOYO-MiX on YouTube, https://www.youtube.com/watch?v=APFVfv9klmg, 108 s, uploaded 2021-02-07.
   - Demo: Bilibili 原神 account, BV1st4y1q7V4, 112 s, 10.24 M views, 2020-09-26. YouTube EN demo: TSsWsCdiiPI, 113 s, 4.69 M views.
   - The track's wiki page (genshin-impact.fandom.com, page "Bard's_Adventure", read through its API) lists it as "Character Demo;;Venti". It was also a song in the 3.5 Windblume rhythm game, Ballads of Breeze (2023). Credits there: violin, electric and acoustic guitar, and a string quartet. No lyre or harp is credited, so the plucked sound is probably guitar.
   - wiki.biligame.com/ys/闪耀的群星 lists it as 01 诗人的工作 for 角色演示-温迪.
   - tam-vem.hatenablog.com calls it the 「ウェンティ」テーマ曲 (Venti's theme song). wikiwiki.jp/genshinwiki/BGM lists it in Genshin Symphony 2022, Concert 2023 (staged at 风龙废墟) and Concert Tour 2024.
   - Fan uploads that title it "Venti Theme": I66mUEZ4g9M ("Venti Theme Music EXTENDED", 152 k views), X77EwmxF3dE, f8JIqJwm0mU, a MuseScore score called "Venti's Theme", Animenz piano versions, and Windsong Lyre covers on Bilibili (BV1AR4y1F7NM).
2. **希望的和风 / "A Yearning Breeze".** From *The Shimmering Voyage*, and it is the cutscene music of his own story quest 「若你困于无风之地」. Official audio: https://www.youtube.com/watch?v=P8x-HrWRuso, 86 s. The wiki ties it to that quest; wikiwiki.jp ties it to the 「微风与少年」 movie.
   - The story teaser itself: 「微风与少年」 / "The Boy and the Whirlwind" is BV1JV411m7tc on Bilibili (95 s) and S_V0TX6MyGw on YouTube (97 s).
3. **重归青天的歌 / "Welcome Back, My Companion"**, also from *The Shimmering Voyage*. It plays in the cutscene of "A Long Shot", in Prologue Act III, the Venti and Dvalin act. Official audio: 0mi0F4zqGow, 100 s.
   - **追忆 / "Reminiscence"** (*City of Winds and Idylls*): K8aLWuJVCEw, 95 s. It plays in that act's quests. The wiki says it shares its theme with the unreleased lyre music of 「天空之琴」 (State of the Holy Lyre der Himmel), so it is the closest thing to "the song 温迪 plays on the lyre" in the archon quests.
4. **Weak ties.**
   - 「四方之风」 / "Venti: The Four Winds", his character teaser: BV1xk4y117tg, 101 s, 7.74 M views. I found no name for its music.
   - 「吟游诗人的把戏」 / "A Cunning Trick": music for one cutscene ("Ending Note"), no wider tie.
   - The EP "Genial Breeze of Hope" (Jan 2021) has a Venti picture but its tracks are main-theme variations.
   - "The Long Way Home" (5th-anniversary song, 2025) is sung by Venti's English voice actor, not by Venti in character.
   - The danmaku 「风与飞鸟」 is a fan song, not HOYO-MiX.

**How I located the representative part.** I read YouTube's most-replayed data from each watch page (100 bins per video):
- **APFVfv9klmg** (1.08 s per bin): replays climb to 0.72 by about 0:36, then jump to the maximum, 1.00, at **42.1 to 43.2 s**. They stay at 0.97 to 1.00 across **63 to 70 s**, with 0.99 again at 90.5 s.
- **EN demo TSsWsCdiiPI:** the peak is 36.5 to 44.5 s (top at 39.9 s). This roughly matches the OST, but replays of the demo also reflect what is on screen.
- I fetched the demo's Bilibili danmaku: 600 comments, almost all in the first 15 s, with none about the music.

The script is in my scratchpad at `C:\Users\ZHIBIN~1\AppData\Local\Temp\claude\C--Users-Zhibin-Ren-Desktop-Black-List-App\4e73d4f5-e751-4fc2-9a63-5de144d4da0e\scratchpad\scripts\yt.py`, and its outputs are `yt1.out` and `yt2.out` in the `dm` folder next to it.

**Could not settle**
- **Key, tempo, notes and instrument of the hook.** I did not listen to the track and downloaded no audio. MuseScore, Tunebat, Musicstax and Sheet Music Plus all refused my requests (HTTP 403), and Everyonepiano's free sheet (Piano-14732) is images only. How to settle: someone listens to APFVfv9klmg from 0:36 to 0:50 and 1:03 to 1:10, or reads a free score such as musescore.com/user/36860648/scores/7448756 in a browser.
- **Whether the 5 s at about 0:41 is a clean phrase start.** That needs listening, with `BLACKLIST_DETECT_SOUND=1` only if it is checked through the app.
- **Track length:** 108 s on YouTube against 1:47 in the maintitles.net review. Spotify (id 3T1kzkVt4tkJWwIetV5IyD) would settle it.
- **The 「四方之风」 teaser's music title** is unknown.
- **The lyre song Venti plays in the archon quest.** The wiki says the in-game version is unreleased; only 追忆 shares its theme. No official sung version of it turned up.

---

## Verification of the web claims

**Verdict.** Almost every claim I could check holds up. I found no wrong title, no wrong official URL and no wrong track attribution. Three details need correcting. On the YouTube peak of "Bard's Adventure", replays climb gradually rather than jumping, and the top bin sits about 0.4 s later than reported. The 温迪 GMV's danmaku peak starts at 1:20, not 1:12. The uploader's song credits are featured "vote-top" comments, not pinned ones. 诗人的工作 / "Bard's Adventure" is the best-supported pick for 温迪's own theme, and its strongest part is about 0:40–0:45 by YouTube replays. Nobody has listened to it yet, so whether that stretch makes a clean 5 s cut is still open.

**Official track (researcher "official")**
- Bard's Adventure on YouTube, APFVfv9klmg (HOYO-MiX, 108 s, uploaded 2021-02-07): **confirmed** from the watch page metadata, 204,030 views. https://www.youtube.com/watch?v=APFVfv9klmg
- The track's real length: **settled at 1:47**. NetEase id 1817410055 gives 107,012 ms, track no 1, album 闪耀的群星, artists 陈致逸 and HOYO-MiX (`music.163.com/api/song/detail/?ids=[1817410055]`). YouTube's 108 s is the upload length.
- Track 1 of The Stellar Moments: **confirmed** by https://www.shazam.com/en-us/album/1666680443/genshin-impact-the-stellar-moments-original-game-soundtrack and by NetEase.
- The biligame wiki lists it as 01 诗人的工作, linked to 角色演示-「温迪：诗人的工作」: **confirmed**. https://wiki.biligame.com/ys/闪耀的群星
- Fandom's credits are **confirmed**: "Character Demo;;Venti", event "Windblume's Breath/Ballads of Breeze" (Version 3.5, 2023-03-03 to 2023-03-20), composer 陈致逸, arranger 苑迪萌, then violin, electric and acoustic guitar, and strings by 龙之艺四重奏. No lyre or harp is credited. I read the wikitext through the genshin-impact.fandom.com api.php "parse" call.
- Most-replayed data on APFVfv9klmg: **mostly confirmed, two details wrong.**
  - My fetch shows bins of 1.09 s, not 1.08 s.
  - The 1.00 top is at **42.5–43.6 s**, not 42.1–43.2 s.
  - The rise is not a jump. It goes 0.72 at 36.0 s, 0.83 at 37.1 s, 0.94 at 40.3 s, 0.95 at 41.4 s, then 1.00.
  - Plateau: 0.98–1.00 across 64.3–69.8 s, as reported. I also found 0.99 at 90.5 s, plus 0.98 at 85.0 s, which they did not mention.
- EN demo TSsWsCdiiPI (113 s, 4.69 M views, peak 1.00 at 39.9 s, 36.5–44.5 s at 0.76 or more): **confirmed**.
- Bilibili videos, all **confirmed** through api.bilibili.com/x/web-interface/view:
  - BV1st4y1q7V4: 112 s, 10,243,754 views, 2020-09-26, uploader 原神.
  - BV1JV411m7tc 「微风与少年」: 95 s.
  - BV1xk4y117tg 「四方之风」: 101 s, 7.74 M views. Its description names no music.
  - BV1AR4y1F7NM: a 风物之诗琴 cover titled 诗人的工作.
- Fan uploads, **confirmed** on their watch pages:
  - I66mUEZ4g9M "Venti Theme Music EXTENDED…": 152,493 views.
  - X77EwmxF3dE: "Bard's Adventure | Venti's theme from GENSHIN CONCERT 2021".
  - f8JIqJwm0mU: "Bard's Adventure (Venti Theme Song)".
- Concerts on wikiwiki.jp/genshinwiki/BGM (Symphony 2022, Concert 2023, Tour 2024): **confirmed**. The 風龍廃墟 stage is **wrong as stated**. The page puts 風龍廃墟 as the backdrop of 「詩人の仕事(ウェンティ)」 in the 2023 *online* concert, not the 2023 concert.
- 希望的和风 "A Yearning Breeze": **confirmed** from P8x-HrWRuso (86 s) and Fandom (quest "Should You Be Trapped in a Windless Land", cutscene). wikiwiki.jp names it 希望の微風 and links it to 「微風と少年」.
- 重归青天的歌 "Welcome Back, My Companion": **confirmed**. 0mi0F4zqGow is 100 s, and Fandom lists "A Long Shot//cutscene".
- 追忆 "Reminiscence": **confirmed**. K8aLWuJVCEw is 95 s, the album is City of Winds and Idylls, and Fandom says it shares its theme with "Unnamed State of the Holy Lyre der Himmel Soundtrack 1".
- "A Cunning Trick" plays in the "Ending Note" cutscene: **confirmed**. "The Long Way Home" is the 5th-anniversary EP released 2025-09-28: **confirmed**.
- YouTube story teaser S_V0TX6MyGw is 97 s: **confirmed**.

**GMVs (researcher "gmv")**
- 温迪 GMV BV1wy4y1t7MJ: **confirmed**. Uploader 霍宝Moira, 210 s, aid 802242472, cid 316330286; the description credits "If Rain" by 萨吉.
- 万叶 GMV BV1gU4y1V7Bw: **confirmed**. 219 s, aid 673883647, cid 363203046; the description and comment credit 秦基博 - Rain.
- "Pinned comment": **wrong word**. `upper.top` is null on both videos. The uploader's comments (1049 and 933 likes) are vote-top entries in `top_replies`.
- "If Rain" is track 6 and an 插曲 of 以家人之名: **confirmed**. https://zh.wikipedia.org/wiki/以家人之名
- "Rain" is the ending of 言の葉の庭 and a 大江千里 cover: **confirmed**. https://ja.wikipedia.org/wiki/言の葉の庭 (the allcinema PDF was unreadable).
- Danmaku, recounted from comment.bilibili.com/<cid>.xml:
  - Totals and comment times: **confirmed**. 804 and 799 danmaku; 温迪 at 72.6, 81.2, 83.0 and 89.0 s; 万叶 at 39.1, 61.2, 126–130, 7.9 and 20.8 s.
  - The 温迪 peak "1:12–1:35": **partly wrong**. 70–75 s holds only 12 comments. The busy stretch is **80–95 s** (29, 35 and 26 per 5 s), and 60–70 s also has 25 and 25.
- Kazuha's two tracks, **confirmed** on NetEase and https://classical.music.apple.com/us/album/1605918576 (album released 2022-01-26):
  - Flow of Autumn Wind: track 10, 116.5 s.
  - Drifter's Destiny: track 9, 101.0 s.
  - Both are by 苑迪萌, both credit shakuhachi, and the Character Demo and Teaser ties match Fandom.

**Unconfirmed**
- The tam-vem.hatenablog page calling it a 「テーマ曲」: the search did not find it.
- The MuseScore and Animenz items.
- "Genial Breeze of Hope": no Fandom page under that name.
- Whether "The Long Way Home" is sung by 温迪's English voice actor: the wiki text gives no singer.
- That HOYO-MiX itself calls the piece "Venti's theme": the official title is just "Bard's Adventure", and only fan and concert-upload titles say "Venti's theme".

**Could not settle**
- Whether 0:40–0:45 of APFVfv9klmg is a clean 5 s phrase, and which instrument plays the hook. Someone has to listen to 0:36–0:50 and 1:04–1:10 by ear.
- Licensing for shipping any of these tracks inside the app.

The Bilibili API gave my machine HTTP 412, so I read it through WebFetch. Fandom gave WebFetch HTTP 402, so I read it from a script. My scripts are in `C:\Users\ZHIBIN~1\AppData\Local\Temp\claude\C--Users-Zhibin-Ren-Desktop-Black-List-App\4e73d4f5-e751-4fc2-9a63-5de144d4da0e\scratchpad\verify\` (v1.py to v8.py, with the saved wiki texts). Nothing was downloaded or played, and the repo is unchanged.

---
