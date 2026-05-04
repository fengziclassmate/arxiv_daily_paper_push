@echo off
setlocal

cd /d "%~dp0"

echo =========================================
echo Starting daily paper digest...
echo =========================================
echo.

"D:\Anaconda\envs\crawl\python.exe" "%~dp0main.py"

set EXIT_CODE=%ERRORLEVEL%
echo.
echo =========================================
echo Task finished with exit code %EXIT_CODE%.
echo =========================================

exit /b %EXIT_CODE%
