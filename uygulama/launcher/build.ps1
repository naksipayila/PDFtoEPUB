$ErrorActionPreference = "Stop"

$launcherRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $launcherRoot
$distributionRoot = Split-Path -Parent $projectRoot
$compilerPath = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$sourcePath = Join-Path $launcherRoot "PortableLauncher.cs"
$outputPath = Join-Path $distributionRoot "PDFtoEPUBLauncher.exe"
$iconPath = Join-Path $projectRoot "assets\pdf-to-epub.ico"

foreach ($path in @($compilerPath, $sourcePath, $iconPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Gerekli dosya bulunamadi: $path"
    }
}

& $compilerPath /nologo /target:winexe "/out:$outputPath" "/win32icon:$iconPath" $sourcePath
if ($LASTEXITCODE -ne 0) {
    throw "Launcher derlenemedi. Cikis kodu: $LASTEXITCODE"
}

Write-Host "Launcher olusturuldu: $outputPath"
