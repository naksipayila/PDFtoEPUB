$ErrorActionPreference = "SilentlyContinue"

Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class ConsoleWindowPosition {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr handle, out Rect rect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(
        IntPtr handle,
        IntPtr insertAfter,
        int x,
        int y,
        int width,
        int height,
        uint flags
    );

    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int index);
}
'@

$handle = [ConsoleWindowPosition]::GetConsoleWindow()
if ($handle -eq [IntPtr]::Zero) {
    exit 0
}

$rect = New-Object ConsoleWindowPosition+Rect
if (-not [ConsoleWindowPosition]::GetWindowRect($handle, [ref]$rect)) {
    exit 0
}

$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$screenWidth = [ConsoleWindowPosition]::GetSystemMetrics(0)
$screenHeight = [ConsoleWindowPosition]::GetSystemMetrics(1)
$x = [Math]::Max(0, [int](($screenWidth - $width) / 2))
$y = [Math]::Max(0, [int](($screenHeight - $height) / 2))

[ConsoleWindowPosition]::SetWindowPos(
    $handle,
    [IntPtr]::Zero,
    $x,
    $y,
    0,
    0,
    0x0001 -bor 0x0004 -bor 0x0010
) | Out-Null
