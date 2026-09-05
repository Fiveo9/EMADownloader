@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto nopython

python -c "import flask" >nul 2>nul
if errorlevel 1 goto install

echo 正在启动 EMA 文件库，浏览器将自动打开...
python -m ema_downloader.webapp
pause
exit /b 0

:install
echo 首次运行，正在安装依赖（约 1 分钟，之后不再需要）...
python -m pip install -e ".[ui]" -q
if errorlevel 1 goto installfail
echo 安装完成，正在启动 EMA 文件库...
python -m ema_downloader.webapp
pause
exit /b 0

:installfail
echo [错误] 依赖安装失败，请检查网络后重试。
pause
exit /b 1

:nopython
echo [提示] 本机未安装 Python。
echo 推荐做法：到本项目的 GitHub Releases 页面下载免安装版，
echo 解压后双击 EMA文件库.exe 即可使用，无需安装任何东西。
pause
exit /b 1
