@echo off
setlocal EnableExtensions DisableDelayedExpansion

title PDF to EPUB

echo Uygulama baslatiliyor...
set "DISPATCH_SCRIPT=%~dp0uygulama\baslat-dispatch.ps1"
if not exist "%DISPATCH_SCRIPT%" goto :fail
powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%DISPATCH_SCRIPT%"
set "LAUNCH_ERROR=%ERRORLEVEL%"
if not "%LAUNCH_ERROR%"=="0" goto :fail
exit /b 0

:fail
echo.
echo PDFtoEPUB baslatilamadi.
echo Lutfen Windows PowerShell'i ve uygulama dosyalarini kontrol edin.
pause
exit /b 1
