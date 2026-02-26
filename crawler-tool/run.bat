@echo off
chcp 65001 >nul
REM 爬虫工具启动脚本 - 完整流程：爬虫提取 → AI转述内容及评论 → 上传数据库

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
if "%~1"=="" (
    echo.
    echo 用法: run.bat [选项]
    echo.
    echo 完整流程模式（推荐）:
    echo   run.bat --title "笔记标题" --description "笔记描述" --city 上海 --page 5
    echo   run.bat --file notes.json --city 上海
    echo.
    echo 其他工具:
    echo   批量更新地址: python app\address_service.py --city 上海 --limit 100
    echo   生成评论:      python app\generate_comments.py --limit 50
    echo   搜索图片:      python app\search_images.py --method bing --city 上海 --limit 10
    echo.
    echo 任务队列模式（依次执行多个任务）:
echo   python app\tools\task_queue.py --file tasks_all_cities.json
echo   爬取全国所有省会城市和直辖市的美食（每个城市5页）
echo   python crawler.py --tasks-file tasks_all_cities.json --headless
echo   在单个浏览器会话中依次执行所有城市（推荐）
    echo.
    echo 示例：
    echo   run.bat --title "上海美食推荐" --description "今天去了xxx餐厅..." --city 上海
    echo   run.bat --file notes.json --city 上海 --limit 10
    echo   python app\search_images.py --method bing --city 上海 --limit 10
    echo   python app\tools\task_queue.py --file tasks.json
    echo.
    exit /b 0
)

REM 运行爬虫主入口脚本
python "%SCRIPT_DIR%crawler.py" %*

