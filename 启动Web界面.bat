@echo off
cd /d "%~dp0"

set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto found_python
)
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
    goto found_python
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto found_python
)
if exist "%ProgramFiles%\Python312\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
    goto found_python
)
if exist "%ProgramFiles%\Python311\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
    goto found_python
)
if exist "%ProgramFiles%\Python313\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python313\python.exe"
    goto found_python
)
if exist "%ProgramFiles%\Python310\python.exe" (
    set "PYTHON_EXE=%ProgramFiles%\Python310\python.exe"
    goto found_python
)
if exist "C:\Python312\python.exe" (
    set "PYTHON_EXE=C:\Python312\python.exe"
    goto found_python
)
if exist "C:\Python311\python.exe" (
    set "PYTHON_EXE=C:\Python311\python.exe"
    goto found_python
)

for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /i /c:"LibreOffice" /c:"WindowsApps" >nul
    if errorlevel 1 (
        if not defined PYTHON_EXE (
            set "PYTHON_EXE=%%I"
            goto found_python
        )
    )
)

:found_python
if not defined PYTHON_EXE goto nopython

"%PYTHON_EXE%" -c "import flask" >nul 2>nul
if errorlevel 1 goto install

echo 正在启动 EMA 文件库，正在为您自动打开浏览器...
"%PYTHON_EXE%" -m ema_downloader.webapp
pause
exit /b 0

:install
echo 首次运行，正在安装依赖（约 1 分钟，之后不再需要）...
"%PYTHON_EXE%" -m pip install -e ".[ui]"
if not errorlevel 1 goto installok

echo [提示] 尝试使用 --user 模式重新安装...
"%PYTHON_EXE%" -m pip install --user -e ".[ui]"
if errorlevel 1 goto installfail

:installok
echo 安装完成，正在启动 EMA 文件库...
"%PYTHON_EXE%" -m ema_downloader.webapp
pause
exit /b 0

:installfail
echo [错误] 依赖安装失败，请检查网络或代理设置后重试。
pause
exit /b 1

:nopython
echo [提示] 本机未检测到可用的 Python 3.10+ 环境。
echo 推荐直接前往本项目 GitHub Releases 页面下载免安装版：
echo 解压后双击 EMA文件库.exe 即可使用，无需安装任何依赖。
pause
exit /b 1
