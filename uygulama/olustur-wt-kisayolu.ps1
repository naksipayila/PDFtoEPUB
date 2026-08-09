$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$dispatcherPath = Join-Path $projectRoot "baslat-dispatch.ps1"
$silentLauncherPath = Join-Path $projectRoot "baslat-sessiz.vbs"
$distributionRoot = Split-Path -Parent $projectRoot
$portableLauncherPath = Join-Path $distributionRoot "PDFtoEPUBLauncher.exe"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPaths = @(
    (Join-Path $desktopPath "PDF to EPUB.lnk")
)

if (-not (Test-Path -LiteralPath $dispatcherPath)) {
    throw "baslat-dispatch.ps1 bulunamadi: $dispatcherPath"
}
if (-not (Test-Path -LiteralPath $silentLauncherPath)) {
    throw "baslat-sessiz.vbs bulunamadi: $silentLauncherPath"
}
if (-not (Test-Path -LiteralPath $portableLauncherPath)) {
    throw "Portable launcher bulunamadi: $portableLauncherPath"
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
            if (!String.IsNullOrEmpty(iconPath)) {
                link.SetIconLocation(iconPath, 0);
            }
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

$description = "PDFtoEPUB uygulamasini baslatir"
foreach ($shortcutPath in $shortcutPaths) {
    [PDFtoEPUB.ShortcutFactory]::Save(
        $shortcutPath,
        $portableLauncherPath,
        $projectRoot,
        $portableLauncherPath,
        $description
    )
    Write-Host "Kisayol olusturuldu: $shortcutPath"
}
