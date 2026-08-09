@echo off
setlocal EnableExtensions DisableDelayedExpansion

title PDF to EPUB

if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"

set "APP_ROOT=%LOCALAPPDATA%\PDFtoEPUB"
set "STAGING_ROOT=%TEMP%\PDFtoEPUB-%RANDOM%-%RANDOM%"
set "ARCHIVE_PATH=%STAGING_ROOT%\source.zip"
set "SOURCE_ARCHIVE_ROOT=%STAGING_ROOT%\source"
set "PDFTOEPUB_ARCHIVE=%ARCHIVE_PATH%"
set "PDFTOEPUB_SOURCE=%SOURCE_ARCHIVE_ROOT%"

if not exist "%STAGING_ROOT%" mkdir "%STAGING_ROOT%" >nul 2>&1
if not exist "%STAGING_ROOT%" goto :fail

echo PDFtoEPUB GitHub surumu indiriliyor...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/naksipayila/PDFtoEPUB/archive/refs/heads/main.zip' -OutFile $env:PDFTOEPUB_ARCHIVE; Expand-Archive -LiteralPath $env:PDFTOEPUB_ARCHIVE -DestinationPath $env:PDFTOEPUB_SOURCE -Force"
if errorlevel 1 goto :fail

set "SOURCE_ROOT="
for /d %%D in ("%SOURCE_ARCHIVE_ROOT%\PDFtoEPUB-*") do (
    if exist "%%~fD\uygulama\baslat-sessiz.vbs" set "SOURCE_ROOT=%%~fD"
)
if not defined SOURCE_ROOT goto :fail

if not exist "%APP_ROOT%" mkdir "%APP_ROOT%" >nul 2>&1
if not exist "%APP_ROOT%" goto :fail

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SOURCE_ROOT%\uygulama\ortala-konsol.ps1" >nul 2>&1

robocopy "%SOURCE_ROOT%\uygulama" "%APP_ROOT%\uygulama" /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo Uygulama baslatiliyor...
set "WSCRIPT_PATH=%WINDIR%\System32\wscript.exe"
set "SILENT_SCRIPT=%APP_ROOT%\uygulama\baslat-sessiz.vbs"
if not exist "%WSCRIPT_PATH%" goto :fail
if not exist "%SILENT_SCRIPT%" goto :fail
start "" /wait "%WSCRIPT_PATH%" "%SILENT_SCRIPT%"
set "LAUNCH_ERROR=%ERRORLEVEL%"
call :cleanup
if not "%LAUNCH_ERROR%"=="0" goto :fail_after_cleanup
exit /b 0

:fail
echo.
echo PDFtoEPUB indirilemedi veya hazirlanamadi.
call :cleanup

:fail_after_cleanup
echo Lutfen internet baglantinizi ve Windows PowerShell'i kontrol edin.
pause
exit /b 1

:cleanup
if exist "%STAGING_ROOT%" rmdir /s /q "%STAGING_ROOT%" >nul 2>&1
exit /b 0
