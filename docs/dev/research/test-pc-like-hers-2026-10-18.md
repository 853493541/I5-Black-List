# A test setup like the friend's PC (2026-10-18)

The question (the user): can we test on a Windows 10, low-end setup like hers, by limiting this PC or with testing
tools, the way web pages are tested at many screen sizes?

## How it is done elsewhere

Three layers, each catching what the others miss:

1. **Emulation on the developer's machine**: a web page is checked at phone sizes and with the browser's CPU slowdown;
   a desktop program is run with fewer cores or a CPU limit. Cheap and repeatable, but only an approximation.
2. **Other systems in virtual machines**: one virtual machine per Windows version, for install, update, layout and
   system behaviour. Not for speed: a virtual machine shares this PC's processor.
3. **Real devices**: game makers keep a compatibility lab of minimum, mainstream and recommended PCs and test on a
   matrix of them (for example a Frontier Developments compatibility-lab posting and WeTest's PC guide); web and phone
   apps use device farms. Plus reports from players' own machines.

For us, layer 3 is her laptop and its log, which records the PC, every check's time and CPU, and from 1.0.1 the OCR
thread count.

## Her PC (from her logs)

i5-11400H, 6 cores / 12 threads (hyperthreading, all cores one speed), 15.6 GB (4-6 GB free with MuMu open), Intel UHD
+ RTX 3050 Laptop, Windows 10 Home China 22H2 build 19045, one 1920x1080 screen at 125 %. MuMu windowed (game
1538x914), 直播姬 open. v1.0.0: a check 2.2-2.5 s with the CPU at 98-100 %; the environment check alone 1.6 s.

## What this PC can stand in for

This PC: Ultra 9 285K, 8 fast and 16 efficiency cores (fast: CPUs 0, 1, 10-13, 22, 23), no hyperthreading, 63.5 GB,
Windows 11 Home with memory integrity on (Windows' hypervisor always running).

- **Speed, by choosing cores**: the closest to her CPU is 12 cores of one speed, the efficiency cores 2-9 and 14-17,
  with a stand-in game (processes doing fixed small steps) on the same cores. Use it to compare settings with each
  other, never as her absolute times: it is faster than her laptop and has no hyperthreading. Sets that mix fast and
  slow cores mislead: CPUs 0-11 made 12 threads look 3x slower than on one speed of core (check-cpu-2026-10-18.md,
  "Correction").
- **Speed, by a CPU limit** (a Windows job object with a hard cap, `JOBOBJECT_CPU_RATE_CONTROL_INFORMATION`): it works,
  but it freezes the program in bursts, and the OCR's threads wait on each other: v1.0.0's check went from 1.35 s to
  2.91 s at a 30 % cap and 4.84 s at 16 %, slower than her laptop. Good only as a rough "much slower PC" check.
- **Windows 10**: a virtual machine (VirtualBox 7.2.20 is installed). Memory integrity puts VirtualBox in Windows'
  hypervisor mode, which is slow and was only stable with 2 CPUs (BIOS) in October's tries. So it is for Windows 10
  behaviour, not speed. Turning memory integrity off would make it faster but weakens this PC's security: not done.

## The Windows 10 machine (`C:\VMs\Win10-Test`)

Made on 2026-10-14 for the 直播姬 stream work, then set aside. Checked 2026-10-18: Windows Setup never finished. The
machine boots to Setup's error ("the computer restarted unexpectedly ... cannot continue"); its last run ended when this
PC shut down. No Guest Additions (no shared folder, 1024x768 only). The install disc beside it is complete and
Microsoft's own: Windows 10 22H2 zh-CN (5.68 GB), with 家庭版 (Home) among its editions.

To make it usable (build-ready, needs the user's go: it replaces the broken machine's 9.8 GB disk):

1. A fresh unattended install from that disc: Windows 10 家庭版 zh-CN, 2 CPUs, BIOS, 8 GB, with Guest Additions
   (`VBoxManage unattended install ... --install-additions`), headless, in the background (Setup in this mode took
   hours in October: poll the screen with `controlvm screenshotpng`, never block on it).
2. 1920x1080 at 125 %, like hers; a shared folder for releases and logs; a snapshot of the clean desktop, so each test
   starts from the same state.
3. Use: install a release zip, first start, update from the previous version, the 设置 and dialogs at 125 %, screen
   copy on Windows 10. The app's own log from inside is the result.

## Recommended

- Speed questions: compare settings on the 12 one-speed cores with the stand-in game; then confirm on her next log.
- Windows 10 questions: the rebuilt virtual machine.
- Not recommended: a cloud Windows machine (server processors, not like hers, and paid), a paid compatibility lab
  (for studios), turning memory integrity off. A used laptop of her class would be the only exact copy of her speed;
  that is a purchase, the user's call.

Sources: https://www.intel.com/content/www/us/en/docs/onednn/developer-guide-reference/2025-1/configuring-onednn-for-benchmarking.html,
https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_cpu_rate_control_information,
https://hitmarker.net/jobs/frontier-developments-qa-compatibility-tester-825845,
https://www.wetest.net/blog/compatibility-testing-for-pc-games-a-full-guide-1056.html.
