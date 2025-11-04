#!/usr/bin/env bash
# 集成爬虫脚本 - 一键运行：爬虫 → AI转述 → 水印清洗 → 上传数据库

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

# 检查参数
if [ $# -lt 2 ]; then
    echo "用法: ./run.sh <关键词> <页数>"
    echo "示例: ./run.sh 深圳美食 5"
    exit 1
fi

# 运行集成爬虫脚本
python3 crawler.py "$@"

