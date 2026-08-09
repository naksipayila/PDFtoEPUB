@echo off
setlocal

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0olustur-wt-kisayolu.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Kisayol olusturulamadi. Yukaridaki hata mesajini inceleyin.
    pause
)

endlocal & exit /b %EXIT_CODE%
