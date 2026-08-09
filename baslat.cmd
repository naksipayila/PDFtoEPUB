@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0baslat.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Uygulama baslatilamadi. Yukaridaki hata mesajini inceleyin.
    pause
)

endlocal & exit /b %EXIT_CODE%
