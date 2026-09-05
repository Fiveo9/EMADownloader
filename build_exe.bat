@echo off
cd /d "%~dp0"

echo ============================================
echo   EMA 文件库 - 打包独立版 exe
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 goto nopython

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 goto installpyi

goto build

:installpyi
echo 首次构建，正在安装 PyInstaller ...
python -m pip install pyinstaller
if errorlevel 1 goto pyifail

:build
echo.
echo 正在打包（首次约 3-5 分钟，请耐心等待）...
python -m PyInstaller --noconfirm --clean ema_downloader.spec
if errorlevel 1 goto buildfail

rem 把可编辑的配置文件放到 exe 旁边，供进阶用户调整
mkdir "dist\EMA文件库\config" 2>nul
copy /y "config\settings.toml" "dist\EMA文件库\config\" >nul
copy /y "config\classification_rules.csv" "dist\EMA文件库\config\" >nul

echo.
echo ============================================
echo   构建完成！
echo   输出位置: dist\EMA文件库\
echo   双击 dist\EMA文件库\EMA文件库.exe 即可运行
echo ============================================
pause
exit /b 0

:nopython
echo [错误] 未检测到 Python，请先安装 Python 3.10+。
pause
exit /b 1

:pyifail
echo [错误] PyInstaller 安装失败。
pause
exit /b 1

:buildfail
echo [错误] 打包失败，请查看上方报错信息。
pause
exit /b 1
