@echo off
REM Spring Boot 服务器启动脚本
REM 功能：固定端口启动服务器，退出脚本时自动关闭服务器

cd /d "%~dp0"

set SERVER_PORT=8080

echo ========================================
echo   Spring Boot 服务器启动脚本
echo   端口: %SERVER_PORT%
echo ========================================
echo.

REM 检查Maven是否安装
where mvn >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Maven，请先安装 Maven
    pause
    exit /b 1
)

REM 检查Java是否安装
where java >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Java，请先安装 Java
    pause
    exit /b 1
)

REM 检查端口是否被占用
netstat -ano | findstr ":%SERVER_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo 警告: 端口 %SERVER_PORT% 已被占用
    echo 正在尝试关闭占用该端口的进程...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%SERVER_PORT%" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    netstat -ano | findstr ":%SERVER_PORT%" | findstr "LISTENING" >nul 2>&1
    if %errorlevel% equ 0 (
        echo 错误: 无法关闭占用端口 %SERVER_PORT% 的进程
        echo 请手动关闭占用该端口的进程后重试
        pause
        exit /b 1
    ) else (
        echo 端口已释放
    )
)

REM 编译项目（如果需要）
echo 正在编译项目...
call mvn clean package -DskipTests -q
if %errorlevel% neq 0 (
    echo 编译失败
    pause
    exit /b 1
)

REM 启动服务器
echo 正在启动服务器（端口: %SERVER_PORT%）...
echo 按 Ctrl+C 退出服务器
echo.

cd jxwq-server

REM 启动服务器（前台运行）
call mvn spring-boot:run

REM 如果服务器正常退出，清理端口
echo.
echo 正在关闭服务器...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%SERVER_PORT%" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo 服务器已关闭

pause

