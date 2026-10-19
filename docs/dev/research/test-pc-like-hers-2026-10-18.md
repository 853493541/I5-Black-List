# A test setup like the friend's PC (2026-10-18)

The question (the user): can we test on a Windows 10, low-end setup like hers, by limiting this PC or with testing
tools, the way web pages are tested at many screen sizes? And how does the industry test across the hardware its users
have?

## How the industry does it

There is no one switch like a browser's phone sizes. Five layers, each catching what the others miss:

1. **Pick the tiers to test** from hardware surveys (Steam Hardware & Software Survey, StatCounter) or the app's own
   data: minimum, mainstream and recommended PCs.
2. **Emulate a weaker PC on a fast one**: Chrome's CPU throttling, calibrated to a target device; on Windows, fewer
   cores, a job object's CPU cap, a virtual machine. Cheap, repeatable, and admittedly inexact: Chrome itself calls a
   real device "the gold standard" and lists what throttling cannot copy (memory speed, heat, the graphics chip).
3. **Keep real low-end machines**: Chromium's perf lab of real devices, including low-end "Android Go" phones; Mozilla's
   Talos on fixed reference machines; game studios' compatibility labs (outsourced labs advertise hundreds of PCs).
   Timings are compared only on the same machine, two versions side by side, as distributions.
4. **Device farms** (Firebase Test Lab, Sauce Labs, BrowserStack, AWS Device Farm) cover phones and browsers. For a
   native Windows program on varied real PCs there is next to nothing: they offer Windows virtual machines.
5. **Field data**: crash and timing reports from players' machines, beta channels and staged rollouts (Chrome goes out
   to 5 %, 15 %, 50 %, then 100 % of users; Steam beta branches; Windows Insider rings). And programs that size
   themselves to the machine they find: Unreal scores the PC and picks quality presets; AMD and NVIDIA advise sizing
   thread pools by physical cores.

A one-to-three person team: one cheap laptop of the lowest tier kept as a reference, a few trusted testers on an early
channel, an exported log with timings and the PC's details, defaults that size themselves, and emulation as a smoke
test, not proof. Ours: this PC held to her speed (below), a Windows 10 virtual machine, her laptop's log, and the OCR's
thread count sized to the PC's cores.

## Her PC (from her logs)

i5-11400H, 6 cores / 12 threads (hyperthreading, all cores one speed), 15.6 GB (4-6 GB free with MuMu open), Intel UHD
+ RTX 3050 Laptop, Windows 10 Home China 22H2 build 19045, one 1920x1080 screen at 125 %. MuMu windowed (game
1538x914), 直播姬 open. v1.0.0: a check 2.2-2.5 s (read 2.1-2.3 s) with the CPU at 98-100 %, this app 67-72 % of it;
the environment check alone 1.6 s.

## This PC held to her speed: `tools/slow_pc.py`

This PC: Ultra 9 285K, 8 fast and 16 efficiency cores (fast: CPUs 0, 1, 10-13, 22, 23), no hyperthreading, 63.5 GB,
Windows 11 Home with memory integrity on.

The tool runs whole checks of the sample lobby, in her 1538 px window on a 1920x1080 screen, each version with the
thread count it picks on her PC (v1.0.0: one per CPU, 12; 1.x: one per core, 6), and puts three things on them:

- **12 one-speed cores** (the efficiency cores 2-9, 14-17), one per CPU of hers. Sets that mix fast and slow cores
  mislead: 12 threads looked 3x slower on CPUs 0-11 (check-cpu-2026-10-18.md, "Correction").
- **A hard CPU cap** (a Windows job object, `JOBOBJECT_CPU_RATE_CONTROL_INFORMATION`) on the run and everything it
  starts: her PC's total speed.
- **A stand-in game** in the same job: threads drawing 60 frames a second, each frame busy a set time. A frame not done
  in its own sixtieth of a second is late: a stutter the player sees.

Calibrated to her log, as Chrome calibrates its throttling to a device. Only the cap and the game were tuned; the
target was v1.0.0's numbers in her log:

| Cap, game | v1.0.0 check | v1.0.0 share of her PC |
|---|---|---|
| 30 %, 6 x 8 ms | 1.19 s | app 82 %, game 23 % |
| 16 %, 4 x 5 ms | 1.63 s | app 94 %, game 13 % |
| 15 %, 6 x 6 ms | 2.37 s | app 85 %, game 17 % |
| 18 %, 8 x 6 ms | 2.13 s | app 78 %, game 21 % |
| **18 %, 10 x 6 ms (the default)** | **2.36-2.41 s** | **app 74-78 %, game 25-27 %** |
| her log | 2.2-2.5 s | app 67-72 %, the rest about 30 % |

So on this profile her PC is about 18 % of this one, with a game taking a quarter to a third of it. That is about half
of what her laptop's specification would give (estimate from memory, LOW): her laptop may run below its speed (power
mode, battery or heat). A hypothesis; her next log can show it.

### v1.0.0 against 1.x on it (3 runs each, `bench_out/slowpc-final.txt` in the session scratch)

| | v1.0.0 (12 threads) | 1.x (6 threads) |
|---|---|---|
| hotkey check | 2.36-2.41 s | 1.18-1.24 s |
| environment check (no game) | 1.92-2.32 s | 1.27-1.29 s |
| app's share of her PC during a check | 74-78 % | 59-62 % |
| game frames on time during a check | 23-24 % | 44-46 % |
| game frames on time with no check | 100 % | 99-100 % |
| names read | 12 of 12 | 12 of 12 |

Half the time, and the game keeps about twice as many frames: 60-65 % fewer late frames per check (2.4 s x 76 % late,
against 1.2 s x 55 %). The game still stutters during a check, for about two thirds of a second's worth of frames.

Other thread counts for 1.x on the same profile (2 runs each): 4 threads 1.24 s, game 56-57 % on time; 8 threads
1.23-1.24 s, 37 %. Four is as fast as six here and a little kinder to the game, but the profile has no hyperthreading:
on her PC six threads on six cores likely leave the second thread of each core to the game (a hypothesis). Kept at one per core; her 1.0.1
log decides (check time, CPU, how the game feels). If the game still stutters there, the next step to measure is fewer
threads on PCs of her size.

What it cannot copy: hyperthreading, her memory speed, heat and power limits, the graphics chip, MuMu's own threads.
The cap stops the whole run in short bursts once its share is used, as Chrome's throttling does. Compare only runs made
here with the same settings, never with her own times.

    .venv\Scripts\python.exe tools\slow_pc.py <v1.0.0 folder> <checkout> --rounds 3

with each version's `blacklist_detect` taken out of git (`git archive v1.0.0 blacklist_detect | tar -x -C <folder>`)
and `BLACKLIST_DETECT_MODEL_DIR` set when the folder has no models. A run of two versions takes about a minute.

## The Windows 10 machine

**Why it got stuck before** (from `C:\VMs\Win10-Test\Logs` and this PC's System log):

1. 2026-10-14, EFI with 4 CPUs: stalled after 20 minutes. Memory integrity puts VirtualBox in Windows' hypervisor mode,
   where only BIOS with 2 CPUs was stable.
2. BIOS, 2 CPUs: copied the files in 5 minutes, restarted at 41 minutes into the last setup stage, and was powered off at
   55 minutes, in the middle of that stage. Windows Setup cannot resume from that: every later start shows "the computer
   restarted unexpectedly ... cannot continue".
3. The next run sat on that error for 2 h 42 min, until Windows Update restarted this PC (09:52, MoUsoCoreWorker) and
   VirtualBox saved the machine.

So nothing was wrong with the machine's settings at the end: the install was cut off, once by hand and once by an update
restart.

**The rebuild** (2026-10-18): a new machine, `C:\VMs\Win10-Home` (the broken one is left as it was; deleting it is the
user's call). Windows 10 家庭版 zh-CN from the same Microsoft disc, unattended, with Guest Additions; BIOS, 2 CPUs, 8 GB,
64 GB disk with the host's disk cache on; sound, clipboard and USB off; this PC kept awake; no update restart pending
and inside active hours. A watcher reports each restart and when the test user is signed in with Guest Additions
running; nothing powers it off mid-setup. The local test user's password is in that folder, nowhere else.
Progress: files copied in 5 minutes, second restart at 10 minutes (the old run's took 41).

Next on it: 1920x1080 at 125 %, a shared folder for releases and logs, and a snapshot of the clean desktop so every test
starts from the same state. Then: install a release zip, first start, update from the previous version, 设置 and the
dialogs at 125 %, screen copy on Windows 10. MuMu cannot run inside it (no nested virtualisation here), so a check there
reads a picture, not the game.

## Recommended

- Speed: `tools/slow_pc.py`, two versions side by side, then her next log.
- Windows 10 behaviour: the rebuilt virtual machine.
- Her laptop: the real device. A used laptop of her class would be the only exact copy; that is a purchase, the user's
  call.
- Not recommended: a cloud Windows machine (server processors, paid), a paid compatibility lab, turning memory integrity
  off (weakens this PC's security).

Sources: [Chrome DevTools, CPU throttling calibrated to devices](https://developer.chrome.com/blog/devtools-grounded-real-world),
[job object CPU cap](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_cpu_rate_control_information),
[EcoQoS](https://devblogs.microsoft.com/performance-diagnostics/introducing-ecoqos/) (tried: no slowdown on this PC
when plugged in), [Steam survey](https://store.steampowered.com/hwsurvey),
[Chromium perf regressions](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/speed/addressing_performance_regressions.md),
[Chrome release cycle](https://chromium.googlesource.com/chromium/src/+/900d25159ac083fda1702706cfc8da4c09087411/docs/process/release_cycle.md),
[Firebase Test Lab](https://firebase.google.com/docs/test-lab/overview),
[AWS Device Farm desktop browsers](https://docs.aws.amazon.com/devicefarm/latest/testgrid/what-is-testgrid.html),
[Unreal hardware benchmark](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/UGameUserSettings/RunHardwareBenchmark),
[AMD GPUOpen on core counts](https://gpuopen.com/learn/cpu-core-counts/),
[Intel oneDNN threads](https://www.intel.com/content/www/us/en/docs/onednn/developer-guide-reference/2025-1/configuring-onednn-for-benchmarking.html),
[Frontier compatibility tester](https://hitmarker.net/jobs/frontier-developments-qa-compatibility-tester-825845),
[WeTest PC compatibility](https://www.wetest.net/blog/compatibility-testing-for-pc-games-a-full-guide-1056.html).
