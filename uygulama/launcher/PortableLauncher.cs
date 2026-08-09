using System;
using System.Diagnostics;
using System.IO;

internal static class PortableLauncher
{
    private static int Main()
    {
        string distributionRoot = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar
        );
        string scriptPath = Path.Combine(distributionRoot, "uygulama", "baslat-sessiz.vbs");
        string wscriptPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.System),
            "wscript.exe"
        );

        if (!File.Exists(scriptPath) || !File.Exists(wscriptPath))
        {
            return 1;
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = wscriptPath,
            Arguments = "\"" + scriptPath + "\"",
            WorkingDirectory = distributionRoot,
            CreateNoWindow = true,
            UseShellExecute = false,
            WindowStyle = ProcessWindowStyle.Hidden,
        });
        return 0;
    }
}
