$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeRoot = Join-Path $projectRoot ".runtime"
$venvRoot = Join-Path $projectRoot ".venv"
$requirements = Join-Path $projectRoot "runtime-requirements.txt"
$pythonVersion = "3.12.10"
$pythonInstallerUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-amd64.exe"
$tesseractInstallerUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
$turkishDataUrl = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/tur.traineddata"
$ProgressPreference = "Continue"

Set-Location -LiteralPath $projectRoot

function Download-WithProgress {
    param(
        [string]$Uri,
        [string]$OutFile,
        [string]$Activity
    )

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $partialFile = "$OutFile.download"
    if (Test-Path -LiteralPath $partialFile) {
        Remove-Item -LiteralPath $partialFile -Force
    }

    $request = [Net.HttpWebRequest]::Create($Uri)
    $request.Method = "GET"
    $request.UserAgent = "PDFtoEPUB bootstrapper"
    $response = $null
    $responseStream = $null
    $fileStream = $null
    try {
        $response = $request.GetResponse()
        $responseStream = $response.GetResponseStream()
        $fileStream = [IO.File]::Open($partialFile, [IO.FileMode]::Create)
        $totalBytes = $response.ContentLength
        $downloadedBytes = [int64]0
        $buffer = New-Object byte[] (1024 * 1024)
        $lastPercent = -1

        while (($read = $responseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $fileStream.Write($buffer, 0, $read)
            $downloadedBytes += $read
            if ($totalBytes -gt 0) {
                $percent = [int][math]::Min(100, [math]::Floor($downloadedBytes * 100 / $totalBytes))
                if ($percent -ne $lastPercent) {
                    $downloadedMb = $downloadedBytes / 1MB
                    $totalMb = $totalBytes / 1MB
                    $status = "{0:N1} MB / {1:N1} MB ({2}%)" -f $downloadedMb, $totalMb, $percent
                    Write-Progress -Activity $Activity -Status $status -PercentComplete $percent
                    $statusLine = "{0}: {1}% ({2:N1} MB / {3:N1} MB)" -f $Activity, $percent, $downloadedMb, $totalMb
                    Write-Host ("`r" + $statusLine.PadRight(100)) -NoNewline
                    $lastPercent = $percent
                }
            } else {
                $downloadedMb = $downloadedBytes / 1MB
                Write-Progress -Activity $Activity -Status ("{0:N1} MB indirildi" -f $downloadedMb)
            }
        }
        Write-Host ""
        $fileStream.Close()
        $fileStream = $null
        Move-Item -LiteralPath $partialFile -Destination $OutFile -Force
    } catch {
        if (Test-Path -LiteralPath $partialFile) {
            Remove-Item -LiteralPath $partialFile -Force
        }
        throw
    } finally {
        if ($fileStream) {
            $fileStream.Dispose()
        }
        if ($responseStream) {
            $responseStream.Dispose()
        }
        if ($response) {
            $response.Dispose()
        }
        Write-Progress -Activity $Activity -Completed
    }
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Komut basarisiz oldu: $FilePath $($Arguments -join ' ')"
    }
}

function Get-PythonVersion {
    param([string]$PythonPath)

    try {
        $version = & $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return [version]$version.Trim()
}

function Find-UsablePython {
    $candidates = @()
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $candidates += $pythonCommand.Source
    }
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        try {
            $launcherPython = & $pyCommand.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
        } catch {
            $launcherPython = $null
        }
        if ($LASTEXITCODE -eq 0 -and $launcherPython) {
            $candidates += $launcherPython.Trim()
        }
        try {
            $launcherPython = & $pyCommand.Source -3.11 -c "import sys; print(sys.executable)" 2>$null
        } catch {
            $launcherPython = $null
        }
        if ($LASTEXITCODE -eq 0 -and $launcherPython) {
            $candidates += $launcherPython.Trim()
        }
    }
    $candidates += Join-Path $runtimeRoot "python\python.exe"

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $version = Get-PythonVersion $candidate
            if ($version -and $version -ge [version]"3.11") {
                return $candidate
            }
        }
    }
    return $null
}

function Install-LocalPython {
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    $installer = Join-Path $runtimeRoot "python-installer.exe"
    if (-not (Test-Path -LiteralPath $installer)) {
        Write-Host "Python bulunamadi. Python $pythonVersion indiriliyor..."
        Download-WithProgress $pythonInstallerUrl $installer "Python indiriliyor"
    }

    $pythonDirectory = Join-Path $runtimeRoot "python"
    Write-Host "Python yerel klasore kuruluyor..."
    $arguments = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=0",
        "Include_launcher=0",
        "Include_pip=1",
        "Include_test=0",
        "SimpleInstall=1",
        "TargetDir=`"$pythonDirectory`""
    )
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Python kurulumu basarisiz oldu. Cikis kodu: $($process.ExitCode)"
    }
    $localPython = Join-Path $pythonDirectory "python.exe"
    if (-not (Test-Path -LiteralPath $localPython)) {
        throw "Python kurulumu tamamlandi ancak python.exe bulunamadi."
    }
    return $localPython
}

function Test-RuntimePackages {
    param([string]$PythonPath)

    try {
        & $PythonPath -c "import PySide6, pymupdf, PIL, pytesseract" 2>$null
    } catch {
        return $false
    }
    return $LASTEXITCODE -eq 0
}

function Find-Tesseract {
    $command = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @(
        "C:\Program Files\Tesseract-OCR\tesseract.exe",
        "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        (Join-Path $runtimeRoot "tesseract\tesseract.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Ensure-Tesseract {
    $tesseract = Find-Tesseract
    if (-not $tesseract) {
        New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
        $installer = Join-Path $runtimeRoot "tesseract-installer.exe"
        if (-not (Test-Path -LiteralPath $installer)) {
            Write-Host "Tesseract OCR bulunamadi. Tesseract indiriliyor..."
            Download-WithProgress $tesseractInstallerUrl $installer "Tesseract OCR indiriliyor"
        }
        Write-Host "Tesseract OCR kuruluyor..."
        $process = Start-Process -FilePath $installer -ArgumentList @("/S") -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Tesseract kurulumu basarisiz oldu. Cikis kodu: $($process.ExitCode)"
        }
        $tesseract = Find-Tesseract
    }
    if (-not $tesseract) {
        throw "Tesseract kurulumu tamamlandi ancak tesseract.exe bulunamadi."
    }

    $localTesseractRoot = Join-Path $runtimeRoot "tesseract"
    $localTessdata = Join-Path $localTesseractRoot "tessdata"
    $turkishData = Join-Path $localTessdata "tur.traineddata"
    if (-not (Test-Path -LiteralPath $turkishData)) {
        New-Item -ItemType Directory -Path $localTessdata -Force | Out-Null
        Write-Host "Turkce OCR verisi indiriliyor..."
        Download-WithProgress $turkishDataUrl $turkishData "Turkce OCR verisi indiriliyor"
    }
    $env:TESSDATA_PREFIX = $localTesseractRoot
    return $tesseract
}

Write-Host "PDF to EPUB baslaticisi hazirlaniyor..."
$systemPython = Find-UsablePython
if (-not $systemPython) {
    $systemPython = Install-LocalPython
}

$venvPython = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Uygulama sanal ortami olusturuluyor..."
    Invoke-Checked $systemPython @("-m", "venv", $venvRoot)
}

if (-not (Test-RuntimePackages $venvPython)) {
    Write-Host "Eksik uygulama paketleri indiriliyor ve kuruluyor..."
    Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked $venvPython @("-m", "pip", "install", "-r", $requirements)
} else {
    Write-Host "Gerekli Python paketleri zaten kurulu."
}

Ensure-Tesseract | Out-Null

$pythonw = Join-Path $venvRoot "Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) {
        throw "Sanal ortamin pythonw.exe dosyasi bulunamadi."
}

Write-Host "Arayuz aciliyor..."
Start-Process -FilePath $pythonw -WorkingDirectory $projectRoot -ArgumentList @("run.py")
