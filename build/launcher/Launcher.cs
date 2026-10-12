// 黑名单检测.exe: starts the app with the Python that ships beside it.
//
// A friend needs nothing installed. The exe sits next to runtime\ and blacklist_detect\,
// and runs runtime\I5黑名单.exe -m blacklist_detect (a folder from before that exe
// existed still has runtime\pythonw.exe). Arguments are passed on, so the start at sign-in
// can ask for --background. Built by build/build_launcher.py with the C# compiler that
// comes with Windows; .NET Framework 4.8, which it needs, is part of Windows 10 and 11.
//
// Updates: the app unpacks a new version into update.new (see blacklist_detect/updater.py).
// Before starting Python, the launcher lays those files over the folder, moving each file it
// replaces into update.old, and leaves update.check behind. The new version deletes
// update.check once it is running; if the launcher finds update.check still there, the new
// version never got that far, and the files in update.old go back. --wait-pid N waits for the
// app that asked for the restart to close first; --apply-only does the update step and stops.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

static class Launcher
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int MessageBoxW(IntPtr owner, string text, string caption, uint type);

    [STAThread]
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        string python = Path.Combine(root, "runtime", "I5黑名单.exe");
        if (!File.Exists(python))
            python = Path.Combine(root, "runtime", "pythonw.exe");
        var passed = new List<string>();
        int waitPid = 0;
        bool applyOnly = false;
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--wait-pid" && i + 1 < args.Length)
                int.TryParse(args[++i], out waitPid);
            else if (args[i] == "--apply-only")
                applyOnly = true;
            else
                passed.Add(args[i]);
        }
        if (waitPid > 0)
        {
            try { Process.GetProcessById(waitPid).WaitForExit(30000); }
            catch (ArgumentException) { }
        }
        string news = Updates.Run(root);
        if (news != null && !applyOnly)
            MessageBoxW(IntPtr.Zero, news, "黑名单检测", 0x30);
        if (applyOnly)
            return news == null ? 0 : 2;
        if (!File.Exists(python))
        {
            MessageBoxW(IntPtr.Zero, "缺少运行环境。请解压整个压缩包后再双击本程序。", "黑名单检测", 0x10);
            return 1;
        }
        var command = new StringBuilder("-m blacklist_detect");
        foreach (string arg in passed)
            command.Append(' ').Append(Quote(arg));
        var start = new ProcessStartInfo(python, command.ToString())
        {
            UseShellExecute = false,
            WorkingDirectory = root,
        };
        start.EnvironmentVariables["PYTHONPATH"] = root;
        start.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
        start.EnvironmentVariables["PYTHONUTF8"] = "1";
        start.EnvironmentVariables["QT_QPA_PLATFORM"] = "windows";
        Process.Start(start);
        return 0;
    }

    // One argument, quoted the way Windows splits a command line back into arguments.
    static string Quote(string arg)
    {
        if (arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            return arg;
        var quoted = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in arg)
        {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') quoted.Append('\\', slashes * 2 + 1);
            else quoted.Append('\\', slashes);
            slashes = 0;
            quoted.Append(c);
        }
        quoted.Append('\\', slashes * 2).Append('"');
        return quoted.ToString();
    }
}

static class Updates
{
    const string Staged = "update.new";
    const string Backup = "update.old";
    const string Pending = "update.check";
    // Files the update added, which a roll back removes.
    const string Added = ".added";

    // Lay a waiting update over the folder, or put the old files back after a failed one.
    // Returns a message for the player, or null when there is nothing to say.
    public static string Run(string root)
    {
        string staged = Path.Combine(root, Staged);
        string backup = Path.Combine(root, Backup);
        string pending = Path.Combine(root, Pending);
        try
        {
            if (Directory.Exists(staged))
            {
                // Never under a copy running from this folder: it holds its files open. The next start does it.
                if (RunningHere(root))
                    return null;
                Apply(root, staged, backup, pending);
                return null;
            }
            if (File.Exists(pending))
            {
                Restore(root, backup, pending);
                return "新版本没能正常打开，已换回原来的版本。";
            }
        }
        catch (Exception error)
        {
            try { Restore(root, backup, pending); } catch (Exception) { }
            try { Directory.Delete(staged, true); } catch (Exception) { }
            return "更新没有完成，已保留原来的版本。" + Environment.NewLine + error.Message;
        }
        return null;
    }

    static bool RunningHere(string root)
    {
        string mine = Path.GetFullPath(Path.Combine(root, "runtime", "I5黑名单.exe"));
        foreach (Process process in Process.GetProcessesByName("I5黑名单"))
        {
            try
            {
                if (string.Equals(Path.GetFullPath(process.MainModule.FileName), mine, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
            catch (Exception) { }
        }
        return false;
    }

    static void Apply(string root, string staged, string backup, string pending)
    {
        if (Directory.Exists(backup))
            Directory.Delete(backup, true);
        Directory.CreateDirectory(backup);
        string version = "";
        string marker = Path.Combine(staged, ".version");
        if (File.Exists(marker))
        {
            version = File.ReadAllText(marker).Trim();
            File.Delete(marker);
        }
        // update.check first: if this stops halfway, the next start puts back what moved.
        File.WriteAllText(pending, version);
        var added = new List<string>();
        foreach (string file in Directory.GetFiles(staged, "*", SearchOption.AllDirectories))
        {
            string rel = file.Substring(staged.Length + 1);
            string target = Path.Combine(root, rel);
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            if (File.Exists(target))
            {
                string kept = Path.Combine(backup, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(kept));
                // A running exe can be renamed, so the launcher can move itself aside too.
                File.Move(target, kept);
            }
            else
            {
                added.Add(rel);
                File.AppendAllText(Path.Combine(backup, Added), rel + Environment.NewLine);
            }
            File.Move(file, target);
        }
        Directory.Delete(staged, true);
    }

    static void Restore(string root, string backup, string pending)
    {
        if (Directory.Exists(backup))
        {
            string addedList = Path.Combine(backup, Added);
            if (File.Exists(addedList))
            {
                foreach (string rel in File.ReadAllLines(addedList))
                {
                    string extra = Path.Combine(root, rel.Trim());
                    if (rel.Trim().Length > 0 && File.Exists(extra))
                        File.Delete(extra);
                }
                File.Delete(addedList);
            }
            foreach (string file in Directory.GetFiles(backup, "*", SearchOption.AllDirectories))
            {
                string rel = file.Substring(backup.Length + 1);
                string target = Path.Combine(root, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(target));
                if (File.Exists(target))
                {
                    // The launcher itself is running: move the new one aside instead of deleting it.
                    string aside = target + ".failed";
                    if (File.Exists(aside))
                        File.Delete(aside);
                    File.Move(target, aside);
                }
                File.Move(file, target);
            }
            Directory.Delete(backup, true);
        }
        if (File.Exists(pending))
            File.Delete(pending);
    }
}
