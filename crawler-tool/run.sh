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

# 如果提供了参数，直接运行爬虫
if [ $# -gt 0 ]; then
    python3 xiaohongshu_selenium.py "$@"
    exit 0
fi

# 交互式输入参数
echo "============================================================"
echo "小红书餐厅爬虫"
echo "============================================================"
echo ""

# 输入关键词（必填）
read -p "请输入搜索关键词（如：深圳美食、潮汕菜）: " keyword
if [ -z "$keyword" ]; then
    echo "错误：关键词不能为空"
    exit 1
fi

# 输入城市（可选）
read -p "城市名称（可选，直接回车跳过）: " city

# 输入页数（可选，默认5）
read -p "爬取页数（默认：5）: " pages
pages=${pages:-5}

# 输入无头模式（可选）
read -p "无头模式（后台运行，不显示浏览器）？(y/n，默认n): " headless
if [ "$headless" = "y" ] || [ "$headless" = "Y" ]; then
    headless_flag="--headless"
else
    headless_flag=""
fi

# 输入上传选项
read -p "是否直接上传到数据库？(y/n，默认n): " upload
if [ "$upload" = "y" ] || [ "$upload" = "Y" ]; then
    upload_flag="--upload"
else
    upload_flag=""
fi

# 构建命令
cmd="python3 xiaohongshu_selenium.py --keyword \"$keyword\" --pages $pages"
if [ -n "$city" ]; then
    cmd="$cmd --city \"$city\""
fi
if [ -n "$headless_flag" ]; then
    cmd="$cmd $headless_flag"
fi
if [ -n "$upload_flag" ]; then
    cmd="$cmd $upload_flag"
fi

echo ""
echo "============================================================"
echo "开始爬取：关键词=$keyword, 页数=$pages, 上传=${upload:-n}"
echo "============================================================"
echo ""

# 执行命令
eval $cmd

