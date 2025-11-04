@echo off
REM 集成爬虫脚本 - 一键运行：爬虫 → AI转述 → 水印清洗 → 上传数据库

cd /d "%~dp0"

REM 查找虚拟环境：优先使用项目根目录的 env，否则使用当前目录的 venv
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "VENV_PATH="

if exist "%PROJECT_ROOT%\env" (
    REM 使用项目根目录的 env
    set "VENV_PATH=%PROJECT_ROOT%\env"
    echo 使用项目根目录虚拟环境: %VENV_PATH%
) else if exist "%SCRIPT_DIR%venv" (
    REM 使用当前目录的 venv（向后兼容）
    set "VENV_PATH=%SCRIPT_DIR%venv"
    echo 使用当前目录虚拟环境: %VENV_PATH%
) else (
    REM 如果都不存在，在当前目录创建 venv
    echo 未找到虚拟环境，正在创建...
    python -m venv "%SCRIPT_DIR%venv"
    set "VENV_PATH=%SCRIPT_DIR%venv"
)

REM 激活虚拟环境
call "%VENV_PATH%\Scripts\activate.bat"

REM 安装依赖（如果需要）
if not exist "%VENV_PATH%\.deps_installed" (
    echo 安装依赖...
    pip install -r "%SCRIPT_DIR%requirements.txt"
    type nul > "%VENV_PATH%\.deps_installed"
)

REM 检查参数
if "%~2"=="" (
    echo 用法: run.bat ^<关键词^> ^<页数^>
    echo 示例: run.bat 深圳美食 5
    exit /b 1
)

REM 运行集成爬虫脚本
python "%SCRIPT_DIR%crawler.py" %*

