$ErrorActionPreference = "SilentlyContinue"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$pythonw = Join-Path $venvRoot "Scripts\pythonw.exe"
$localTessdata = Join-Path $projectRoot ".runtime\tesseract\tessdata\tur.traineddata"

function Test-Ready {
    if (-not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath $pythonw)) {
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

    $tesseractCandidates = @(
        (Get-Command tesseract -ErrorAction SilentlyContinue).Source,
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        (Join-Path $projectRoot ".runtime\tesseract\tesseract.exe")
    )
    $hasTesseract = $false
    foreach ($candidate in $tesseractCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $hasTesseract = $true
            break
        }
    }
    return $hasTesseract -and (Test-Path -LiteralPath $localTessdata)
}

if (Test-Ready) {
    Start-Process -FilePath $pythonw -WorkingDirectory $projectRoot -ArgumentList @("run.py")
    exit 0
}

$wtCommand = Get-Command wt.exe -ErrorAction SilentlyContinue
if (-not $wtCommand) {
    exit 1
}

$terminalScript = Join-Path $projectRoot "baslat-terminal.ps1"
$terminalArguments = '-d "' + $projectRoot + '" powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + $terminalScript + '"'
Start-Process -FilePath $wtCommand.Source -WorkingDirectory $projectRoot -ArgumentList $terminalArguments
