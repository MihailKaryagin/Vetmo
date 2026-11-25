@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Missing venv\Scripts\python.exe. Run this file from the project folder with its existing venv.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
"venv\Scripts\python.exe" manage.py check_database
if errorlevel 1 goto failed
"venv\Scripts\python.exe" manage.py check
if errorlevel 1 goto failed
"venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto failed
if /i "%~1"=="--check" exit /b 0
echo Website: http://127.0.0.1:8000/
echo Support inbox: http://127.0.0.1:8000/admin/main/supportconversation/
echo Sign in with your Django admin account to reply to visitors.
"venv\Scripts\python.exe" manage.py runserver
exit /b
:failed
echo Startup failed. Check the error above and MySQL settings in config/settings.py.
pause
exit /b 1
