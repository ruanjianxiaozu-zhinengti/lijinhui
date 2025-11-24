@echo off
chcp 65001 >nul
echo 启动前端服务器...
cd frontend
call ..\venv\Scripts\activate.bat
python -m http.server 8000
pause