$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcherPath = Join-Path $projectRoot "baslat.ps1"

try {
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $launcherPath
    if ($LASTEXITCODE -ne 0) {
        throw "Launcher cikis kodu: $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Host "Uygulama baslatilamadi: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Kapatmak icin Enter'a basin"
    exit 1
}
