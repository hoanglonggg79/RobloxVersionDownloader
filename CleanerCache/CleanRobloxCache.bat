@echo off
title Roblox Downloader Cache Cleaner
color 0A

echo ======================================================
echo             ROBLOX DOWNLOADER CACHE CLEANER
echo ======================================================
echo.
echo Target folder: %%LOCALAPPDATA%%\Roblox\Downloads\
echo (This is where temporary .zip installer files are stored)
echo.

:ask
set /p choice="Are you sure you want to clear all cache? (Y/N): "

if /i "%choice%"=="Y" goto confirm
if /i "%choice%"=="N" goto cancel
echo Invalid choice. Please enter Y or N.
goto ask

:confirm
echo.
echo Clearing cache data...
if exist "%LOCALAPPDATA%\Roblox\Downloads" (
    del /q /s "%LOCALAPPDATA%\Roblox\Downloads\*.*"
    echo.
    echo [OK] Cache successfully cleared!
) else (
    echo [!] Cache folder not found. It might have been deleted already.
)
pause
exit

:cancel
echo.
echo Operation canceled. No files were deleted.
pause
exit
