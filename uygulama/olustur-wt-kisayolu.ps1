$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$dispatcherPath = Join-Path $projectRoot "baslat-dispatch.ps1"
$silentLauncherPath = Join-Path $projectRoot "baslat-sessiz.vbs"
$distributionRoot = Split-Path -Parent $projectRoot
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPaths = @(
    (Join-Path $desktopPath "PDF to EPUB.lnk")
    (Join-Path $distributionRoot "PDF to EPUB.lnk")
)

if (-not (Test-Path -LiteralPath $dispatcherPath)) {
    throw "baslat-dispatch.ps1 bulunamadi: $dispatcherPath"
}
if (-not (Test-Path -LiteralPath $silentLauncherPath)) {
    throw "baslat-sessiz.vbs bulunamadi: $silentLauncherPath"
}

$wtPath = $null
$wtCommand = Get-Command "wt.exe" -ErrorAction SilentlyContinue
if ($wtCommand -and $wtCommand.CommandType -eq "Application") {
    $wtPath = $wtCommand.Source
}
if (-not $wtPath) {
    $wtCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\wt.exe"),
        (Join-Path $env:ProgramFiles "WindowsApps\Microsoft.WindowsTerminal_8wekyb3d8bbwe\wt.exe")
    )
    foreach ($candidate in $wtCandidates) {
        if (Test-Path -LiteralPath $candidate) {
            $wtPath = $candidate
            break
        }
    }
}
if (-not $wtPath) {
    throw "Windows Terminal (wt.exe) bulunamadi. Once Windows Terminal'i kurun."
}

$iconPath = Join-Path $projectRoot "assets\pdf-to-epub.ico"
if (-not (Test-Path -LiteralPath $iconPath)) {
    $iconPath = $wtPath
    $terminalPackage = Get-AppxPackage -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "Microsoft.WindowsTerminal*" } |
        Sort-Object Version -Descending |
        Select-Object -First 1
    if ($terminalPackage) {
        $packageIcon = Join-Path $terminalPackage.InstallLocation "Images\terminal_contrast-black.ico"
        if (Test-Path -LiteralPath $packageIcon) {
            $iconPath = $packageIcon
        }
    }
}

$shortcutInterop = @'
using System;
using System.Runtime.InteropServices;

namespace PDFtoEPUB {
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IShellLinkW {
        void GetPath(IntPtr path, int maxPath, IntPtr findData, uint flags);
        void GetIDList(out IntPtr idList);
        void SetIDList(IntPtr idList);
        void GetDescription(IntPtr description, int maxDescription);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string description);
        void GetWorkingDirectory(IntPtr directory, int maxDirectory);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string directory);
        void GetArguments(IntPtr arguments, int maxArguments);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
        void GetHotkey(out short hotkey);
        void SetHotkey(short hotkey);
        void GetShowCmd(out int showCommand);
        void SetShowCmd(int showCommand);
        void GetIconLocation(IntPtr iconPath, int maxIconPath, out int iconIndex);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string iconPath, int iconIndex);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string shortcutPath, uint reserved);
        void Resolve(IntPtr windowHandle, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string targetPath);
    }

    [ComImport, Guid("45E2B4AE-B1C3-11D0-B92F-00A0C90312E1"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IShellLinkDataList {
        void AddDataBlock(IntPtr dataBlock);
        void CopyDataBlock(uint signature, out IntPtr dataBlock);
        void RemoveDataBlock(uint signature);
        void GetFlags(out uint flags);
        void SetFlags(uint flags);
    }

    [ComImport, Guid("0000010B-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IPersistFile {
        void GetClassID(out Guid classId);
        void IsDirty();
        void Load([MarshalAs(UnmanagedType.LPWStr)] string fileName, uint mode);
        void Save([MarshalAs(UnmanagedType.LPWStr)] string fileName, bool remember);
        void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string fileName);
        void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string fileName);
    }

    public static class ShortcutFactory {
        public static void Save(
            string shortcutPath,
            string targetPath,
            string workingDirectory,
            string iconPath,
            string description
        ) {
            var link = (IShellLinkW)Activator.CreateInstance(
                Type.GetTypeFromCLSID(new Guid("00021401-0000-0000-C000-000000000046"))
            );
            link.SetPath(targetPath);
            link.SetArguments("");
            link.SetWorkingDirectory(workingDirectory);
            link.SetDescription(description);
            link.SetShowCmd(1);
            link.SetIconLocation(iconPath, 0);
            link.SetRelativePath(shortcutPath, 0);

            var dataList = (IShellLinkDataList)link;
            uint flags;
            dataList.GetFlags(out flags);
            dataList.SetFlags(flags | 0x00000100u | 0x00040000u);
            ((IPersistFile)link).Save(shortcutPath, true);
        }
    }
}
'@
Add-Type -TypeDefinition $shortcutInterop

$rootPrefix = [IO.Path]::GetFullPath($distributionRoot).TrimEnd("\") + "\"
$portableIconPath = "uygulama\assets\pdf-to-epub.ico"
$description = "PDFtoEPUB uygulamasini baslatir"
foreach ($shortcutPath in $shortcutPaths) {
    $fullShortcutPath = [IO.Path]::GetFullPath($shortcutPath)
    $isPortable = $fullShortcutPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)
    $linkIconPath = if ($isPortable -and (Test-Path -LiteralPath (Join-Path $projectRoot $portableIconPath))) {
        $portableIconPath
    } else {
        $iconPath
    }
    $workingDirectory = if ($isPortable) { "" } else { $projectRoot }
    [PDFtoEPUB.ShortcutFactory]::Save(
        $shortcutPath,
        $silentLauncherPath,
        $workingDirectory,
        $linkIconPath,
        $description
    )
    Write-Host "Kisayol olusturuldu: $shortcutPath"
}
