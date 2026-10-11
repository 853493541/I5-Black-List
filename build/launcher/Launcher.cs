// 黑名单检测.exe: starts the app with the Python that ships beside it.
//
// A friend needs nothing installed. The exe sits next to runtime\ and blacklist_detect\,
// and runs runtime\I5黑名单.exe -m blacklist_detect (a folder from before that exe
// existed still has runtime\pythonw.exe). Arguments are passed on, so the start at sign-in
// can ask for --background. Built by build/build_launcher.py with the C# compiler that
// comes with Windows; .NET Framework 4.8, which it needs, is part of Windows 10 and 11.

using System;
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
        if (!File.Exists(python))
        {
            MessageBoxW(IntPtr.Zero, "缺少运行环境。请解压整个压缩包后再双击本程序。", "黑名单检测", 0x10);
            return 1;
        }
        var command = new StringBuilder("-m blacklist_detect");
        foreach (string arg in args)
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
