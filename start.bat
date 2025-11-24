@echo off
chcp 65001 >nul
echo ===============================
echo      启动后端服务器...
echo ===============================

REM 进入 backend 目录
cd backend

REM 激活虚拟环境
call ..\venv\Scripts\activate.bat

REM 后端后台运行
start cmd /k "python app.py"

REM 返回根目录
cd ..

echo.
echo ===============================
echo      启动前端服务器...
echo ===============================

cd frontend

REM 激活虚拟环境（只执行，不重复开启窗口）
call ..\venv\Scripts\activate.bat >nul

REM 前端后台运行
start cmd /k "python -m http.server 8000"

cd ..

echo.
echo ===============================
echo      打开系统主页...
echo ===============================
start http://localhost:8000

echo 所有服务已启动。
pause
