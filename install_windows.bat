@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo        H.A.V.E. Pro Editor - Windows Installer
echo ========================================================

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.10+
    pause
    goto :EOF
)

REM Create Virtual Environment
echo [1/4] Creating Python Virtual Environment (venv)...
if not exist "venv" (
    python -m venv venv
)

REM Activate venv and install requirements
echo [2/4] Activating venv and installing requirements...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

REM Find Icon
if exist "icons\HAVE_Pro_Logo.ico" (
    echo Icon Found
) else (
    echo [WARNING] icons\HAVE_Pro_Logo.ico not found. Skipping icon generation.
)

REM Create Desktop Shortcut
echo [4/4] Creating Desktop Shortcut...
set VENV_PYTHON="%~dp0venv\Scripts\python.exe"
set WORK_DIR="%~dp0"
set SHORTCUT_PATH="%USERPROFILE%\Desktop\HAVE Pro Editor.lnk"
set ICON_PATH="%~dp0icons\HAVE_Pro_Logo.ico"

echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%USERPROFILE%\Desktop\HAVE Pro Editor.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = %VENV_PYTHON% >> CreateShortcut.vbs
echo oLink.Arguments = "main_gui.py" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = %WORK_DIR% >> CreateShortcut.vbs
echo oLink.Description = "H.A.V.E. Pro Editor" >> CreateShortcut.vbs
if exist "icons\HAVE_Pro_Logo.ico" (
    echo oLink.IconLocation = %ICON_PATH% >> CreateShortcut.vbs
)
echo oLink.Save >> CreateShortcut.vbs

cscript /nologo CreateShortcut.vbs
del CreateShortcut.vbs

echo ========================================================
echo Installation Complete!
echo You can now launch "HAVE Pro Editor" from your Desktop.
echo ========================================================
pause
