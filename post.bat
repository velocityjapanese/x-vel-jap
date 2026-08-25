@echo off
cd /d "%~dp0"
set /p TWEET="Enter tweet text: "
node post.js "%TWEET%"
pause
