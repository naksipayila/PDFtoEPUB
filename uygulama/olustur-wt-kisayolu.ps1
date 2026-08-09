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

$shell = New-Object -ComObject WScript.Shell
$wscriptPath = Join-Path $env:WINDIR "System32\wscript.exe"
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wscriptPath
    $shortcut.Arguments = '"' + $silentLauncherPath + '"'
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "PDFtoEPUB uygulamasini Windows Terminal ile baslatir"
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    Write-Host "Kisayol olusturuldu: $shortcutPath"
}
