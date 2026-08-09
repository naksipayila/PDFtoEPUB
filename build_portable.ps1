param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

function Invoke-Python {
    param([string[]]$Arguments)

    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python komutu başarısız oldu: python $($Arguments -join ' ')"
    }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python bulunamadı. Bu betik yalnızca taşınabilir paketi oluşturulan bilgisayarda çalıştırılmalıdır."
}

if (-not $SkipDependencyInstall) {
    Write-Host "Paketleme bağımlılıkları hazırlanıyor..."
    Invoke-Python @("-m", "pip", "install", "-r", "requirements.txt", "pyinstaller")
}

$portableRoot = Join-Path $projectRoot "portable"
$buildRoot = Join-Path $projectRoot "build"
if (Test-Path -LiteralPath $portableRoot) {
    Remove-Item -LiteralPath $portableRoot -Recurse -Force
}

Write-Host "Windows taşınabilir paketi oluşturuluyor..."
Invoke-Python @(
    "-m",
    "PyInstaller",
    "--clean",
    "--noconfirm",
    "--distpath",
    $portableRoot,
    "--workpath",
    $buildRoot,
    "pdf_to_epub.spec"
)

$packageRoot = Join-Path $portableRoot "PDFtoEPUB"
$readmeSource = Join-Path $projectRoot "packaging\PORTABLE_README.txt"
Copy-Item -LiteralPath $readmeSource -Destination (Join-Path $packageRoot "KULLANIM.txt")

$tesseractCandidates = @()
$tesseractCommand = Get-Command tesseract -ErrorAction SilentlyContinue
if ($tesseractCommand) {
    $tesseractCandidates += Split-Path -Parent $tesseractCommand.Source
}
$tesseractCandidates += @(
    "C:\Program Files\Tesseract-OCR",
    "C:\Program Files (x86)\Tesseract-OCR",
    (Join-Path $projectRoot "tools\tesseract")
)

$tesseractSource = $tesseractCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $_ "tesseract.exe")) } |
    Select-Object -First 1
if ($tesseractSource) {
    $tesseractDestination = Join-Path $packageRoot "tesseract"
    Copy-Item -LiteralPath $tesseractSource -Destination $tesseractDestination -Recurse -Force
    Write-Host "Tesseract OCR pakete dahil edildi."
} else {
    Write-Warning "Tesseract bulunamadı; metin katmanı olmayan PDF'lerde OCR devre dışı kalır."
}

Write-Host "Hazır: $packageRoot"
Write-Host "Başlatmak için PDFtoEPUB.exe dosyasına çift tıklayın."
