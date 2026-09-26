@echo off
setlocal

set "APP_DIR=%~dp0"
set "VENV_DIR=%LOCALAPPDATA%\DuoLingualPlayer\venv"
set "PYTHONW=%VENV_DIR%\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
    echo DuoLingual Player could not be started.
    echo.
    echo The virtual environment was not found:
    echo %VENV_DIR%
    echo.
    echo Complete the installation steps in README.md first.
    echo.
    pause
    exit /b 1
)

pushd "%APP_DIR%"
start "DuoLingual Player" "%PYTHONW%" -m duolingual_player
popd

endlocal
