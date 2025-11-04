#!/usr/bin/env bash
# 激活虚拟环境并运行小红书爬虫（交互式输入参数）

cd "$(dirname "$0")"

# 如果虚拟环境不存在，创建它
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（如果需要）
if [ ! -f "venv/.deps_installed" ]; then
    echo "安装依赖..."
    pip install -r requirements.txt
    touch venv/.deps_installed
fi

# 爬虫脚本路径（使用本地爬虫文件）
SPIDER_SCRIPT="xhs3.py"

# 如果提供了参数，直接运行爬虫（需要适配新爬虫的参数格式）
if [ $# -gt 0 ]; then
    echo "注意：新爬虫使用交互式输入，命令行参数将被忽略"
    echo "运行爬虫脚本..."
    python3 "$SPIDER_SCRIPT"
    exit 0
fi

# 交互式输入参数
echo "============================================================"
echo "小红书餐厅爬虫"
echo "============================================================"
echo ""

# 运行爬虫（新爬虫内置交互式输入）
python3 "$SPIDER_SCRIPT"

