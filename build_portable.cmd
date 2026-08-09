@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_portable.ps1"
if errorlevel 1 (
    echo.
    echo Paketleme başarısız oldu. Ayrıntı için yukarıdaki hatayı inceleyin.
    pause
)
endlocal
