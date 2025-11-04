#!/usr/bin/env bash
# 集成爬虫脚本 - 一键运行：爬虫 → AI转述 → 水印清洗 → 上传数据库

cd "$(dirname "$0")"

# 查找虚拟环境：优先使用项目根目录的 env，否则使用当前目录的 venv
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH=""

if [ -d "$PROJECT_ROOT/env" ]; then
    # 使用项目根目录的 env
    VENV_PATH="$PROJECT_ROOT/env"
    echo "使用项目根目录虚拟环境: $VENV_PATH"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    # 使用当前目录的 venv（向后兼容）
    VENV_PATH="$SCRIPT_DIR/venv"
    echo "使用当前目录虚拟环境: $VENV_PATH"
else
    # 如果都不存在，在当前目录创建 venv
    echo "未找到虚拟环境，正在创建..."
    python3 -m venv "$SCRIPT_DIR/venv"
    VENV_PATH="$SCRIPT_DIR/venv"
fi

# 激活虚拟环境
if [ "$(uname)" == "Darwin" ] || [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # Linux/Mac
    source "$VENV_PATH/bin/activate"
else
    # Windows (Git Bash)
    source "$VENV_PATH/Scripts/activate"
fi

# 安装依赖（如果需要）
DEPS_FLAG="$VENV_PATH/.deps_installed"
if [ ! -f "$DEPS_FLAG" ]; then
    echo "安装依赖..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
    touch "$DEPS_FLAG"
fi

# 检查参数
if [ $# -lt 2 ]; then
    echo "用法: ./run.sh <关键词> <页数>"
    echo "示例: ./run.sh 深圳美食 5"
    exit 1
fi

# 运行集成爬虫脚本
python3 "$SCRIPT_DIR/crawler.py" "$@"

