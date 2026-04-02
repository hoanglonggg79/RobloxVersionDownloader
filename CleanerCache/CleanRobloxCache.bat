@echo off
title Roblox Downloader Cache Cleaner
color 0A

echo ======================================================
echo           ROBLOX DOWNLOADER CACHE CLEANER
echo ======================================================
echo.
echo Thu muc sap xoa: %%LOCALAPPDATA%%\Roblox\Downloads\
echo (Day la noi chua cac file .zip tam thoi cua trinh tai)
echo.

:ask
set /p choice="Ban co chac chan muon xoa toan bo cache khong? (Y/N): "

if /i "%choice%"=="Y" goto confirm
if /i "%choice%"=="N" goto cancel
echo Lua chon khong hop le, vui long nhap Y hoac N.
goto ask

:confirm
echo.
echo Dang xoa du lieu cache...
if exist "%LOCALAPPDATA%\Roblox\Downloads" (
    del /q /s "%LOCALAPPDATA%\Roblox\Downloads\*.*"
    echo.
    echo [OK] Da don dep xong cache!
) else (
    echo [!] Khong tim thay thu muc cache. Co the no da duoc xoa truoc do.
)
pause
exit

:cancel
echo.
echo Da huy thao tac. Khong co file nao bi xoa.
pause
exit