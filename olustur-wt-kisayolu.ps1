$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherPath = Join-Path $projectRoot "baslat.ps1"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPaths = @(
    (Join-Path $desktopPath "PDFtoEPUB (Windows Terminal).lnk")
    (Join-Path $projectRoot "PDFtoEPUB-WindowsTerminal.lnk")
)

if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "baslat.ps1 bulunamadi: $launcherPath"
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

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wtPath
    $shortcut.Arguments = '-d "' + $projectRoot + '" powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -File "' + $launcherPath + '"'
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "PDFtoEPUB uygulamasini Windows Terminal ile baslatir"
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    Write-Host "Kisayol olusturuldu: $shortcutPath"
}
