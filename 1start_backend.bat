@echo off
chcp 65001 >nul
echo 启动后端服务器...
cd backend
call ..\venv\Scripts\activate.bat
python app.py
pause