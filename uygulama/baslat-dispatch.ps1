$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$pythonw = Join-Path $venvRoot "Scripts\pythonw.exe"
$localTessdata = Join-Path $projectRoot ".runtime\tesseract\tessdata\tur.traineddata"
$localOsdData = Join-Path $projectRoot ".runtime\tesseract\tessdata\osd.traineddata"
$localTessdataMarker = Join-Path $projectRoot ".runtime\tesseract\tessdata\tur.model"
$requiredTessdataVersion = "tessdata_best-e12c65a915945e4c28e237a9b52bc4a8f39a0cec"

function Find-Tesseract {
    $candidates = @(
        (Get-Command tesseract -ErrorAction SilentlyContinue).Source,
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        (Join-Path $projectRoot ".runtime\tesseract\tesseract.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Test-SupportedPython {
    try {
        & $venvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
    } catch {
        return $false
    }
    return $LASTEXITCODE -eq 0
}

function Test-Ready {
    if (-not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath $pythonw)) {
        return $false
    }
    if (-not (Test-SupportedPython)) {
        return $false
    }

    try {
        & $venvPython -c "import PySide6, pymupdf, PIL, pytesseract" 2>$null
    } catch {
        return $false
    }
    if ($LASTEXITCODE -ne 0) {
        return $false
    }

    if (-not (Find-Tesseract) -or -not (Test-Path -LiteralPath $localTessdata) -or -not (Test-Path -LiteralPath $localOsdData)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $localTessdataMarker)) {
        return $false
    }
    return (Get-Content -LiteralPath $localTessdataMarker -Raw).Trim() -eq $requiredTessdataVersion
}

if (Test-Ready) {
    $env:PDFTOEPUB_TESSERACT = Find-Tesseract
    $env:TESSDATA_PREFIX = Split-Path -Parent $localTessdata
    Start-Process -FilePath $pythonw -WorkingDirectory $projectRoot -ArgumentList @("run.py")
    exit 0
}

$wtCommand = Get-Command wt.exe -ErrorAction SilentlyContinue
$launcherScript = Join-Path $projectRoot "baslat.ps1"
$terminalArguments = '-d "' + $projectRoot + '" powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "' + $launcherScript + '"'

if ($wtCommand) {
    try {
        Start-Process -FilePath $wtCommand.Source -WorkingDirectory $projectRoot -ArgumentList $terminalArguments -ErrorAction Stop
        exit 0
    } catch {
        # Fall back to the Windows PowerShell console when Terminal is unavailable.
    }
}

$windowsPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
if (-not (Test-Path -LiteralPath $windowsPowerShell)) {
    throw "Windows PowerShell bulunamadi. Kurulum baslatilamiyor."
}
Start-Process -FilePath $windowsPowerShell -WorkingDirectory $projectRoot -ArgumentList @(
    "-NoLogo",
    "-NoProfile",
    "-ExecutionPolicy",
    "RemoteSigned",
    "-File",
    $launcherScript
) -WindowStyle Normal -ErrorAction Stop
