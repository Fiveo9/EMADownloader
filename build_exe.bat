@echo off
cd /d "%~dp0"

echo ============================================
echo   EMA 文件库 - 本地构建绿色版 exe
echo ============================================
echo.

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

"%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 goto installpyi

goto build

:installpyi
echo 首次构建，正在安装 PyInstaller ...
"%PYTHON_EXE%" -m pip install pyinstaller
if not errorlevel 1 goto build

echo [提示] 尝试使用 --user 模式安装 PyInstaller...
"%PYTHON_EXE%" -m pip install --user pyinstaller
if errorlevel 1 goto pyifail

:build
echo.
echo 正在打包（首次约 3-5 分钟，请耐心等待）...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean ema_downloader.spec
if errorlevel 1 goto buildfail

rem 把可编辑的配置文件放到 exe 旁边，方便用户修改
mkdir "dist\EMA文件库\config" 2>nul
copy /y "config\settings.toml" "dist\EMA文件库\config\" >nul
copy /y "config\classification_rules.csv" "dist\EMA文件库\config\" >nul

echo.
echo ============================================
echo   构建完成！
echo   产物位置: dist\EMA文件库\
echo   双击 dist\EMA文件库\EMA文件库.exe 即可使用
echo ============================================
pause
exit /b 0

:nopython
echo [错误] 未检测到可用的 Python 3.10+，请先安装 Python。
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
