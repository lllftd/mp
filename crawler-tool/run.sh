#!/usr/bin/env bash
# 爬虫工具统一启动脚本
# 支持独立运行各个模块，也可以组合运行

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
if [ $# -eq 0 ]; then
    echo ""
    echo "用法: ./run.sh [模块] [选项]"
    echo ""
    echo "独立模块运行:"
    echo "  # 爬虫模块 - 爬取小红书内容"
    echo "  ./run.sh --crawl --keyword \"上海美食\" --pages 5 --output notes.json"
    echo ""
    echo "  # 内容处理模块 - 处理笔记内容，提取餐厅，AI转述，上传数据库"
    echo "  ./run.sh --process --file notes.json --city 上海"
    echo "  ./run.sh --process --title \"餐厅名\" --description \"笔记描述\" --city 上海"
    echo ""
    echo "  # 评论生成模块 - 为推文生成评论"
    echo "  ./run.sh --comments --limit 50"
    echo "  ./run.sh --comments --tweet-id 123 --count 50"
    echo ""
    echo "  # 图片搜索模块 - 搜索并上传图片"
    echo "  ./run.sh --images --method bing --city 上海 --limit 10"
    echo "  ./run.sh --images --method amap --city 上海 --limit 10"
    echo ""
    echo "组合运行（完整流程）:"
    echo "  # 爬取 → 处理 → 生成评论 → 搜索图片"
    echo "  ./run.sh --crawl --keyword \"上海美食\" --pages 5 --process --comments --images"
    echo ""
    echo "其他工具:"
    echo "  批量更新地址: python3 app/services/address_service.py --city 上海 --limit 100"
    echo "  添加类目:      python3 app/tools/add_tweet_type.py --list"
    echo "                 python3 app/tools/add_tweet_type.py --parent \"旅游\""
    echo "                 python3 app/tools/add_tweet_type.py --child \"意大利菜\" --parent-id 5"
    echo "  更新推文类目:  ./run.sh --update-categories [选项]"
    echo "                 ./run.sh --update-categories --dry-run  # 预览模式"
    echo "                 ./run.sh --update-categories --limit 100  # 只更新前100条"
    echo "                 ./run.sh --update-categories --skip-existing  # 跳过已有分类"
    echo "  验证图片URL:   ./run.sh --validate-images [选项]"
    echo "                 ./run.sh --validate-images --dry-run  # 预览模式"
    echo "                 ./run.sh --validate-images --limit 100  # 只验证前100条"
    echo "                 ./run.sh --validate-images --where \"tweets_location = '上海'\"  # 验证指定城市
  更新所属地区:  ./run.sh --update-location [选项]
                 ./run.sh --update-location --dry-run  # 预览模式
                 ./run.sh --update-location --limit 100  # 只更新前100条
                 ./run.sh --update-location --where \"tweets_type_pid = 5\"  # 添加额外条件
                 ./run.sh --update-location --force  # 强制更新所有记录（包括已有格式）
  整合高德API更新: ./run.sh --update-from-amap [选项]
                 ./run.sh --update-from-amap --dry-run  # 预览模式
                 ./run.sh --update-from-amap --limit 100  # 只更新前100条
                 ./run.sh --update-from-amap --city 上海  # 只更新特定城市
                 ./run.sh --update-from-amap --type-pid 5  # 只更新特定类型
                 ./run.sh --update-from-amap --skip-existing  # 只更新空值
  修复未完成推文:  ./run.sh --fix-incomplete [选项]
                 ./run.sh --fix-incomplete --dry-run  # 预览模式
                 ./run.sh --fix-incomplete --limit 100  # 只修复前100条
                 ./run.sh --fix-incomplete --where \"tweets_location = '上海'\"  # 修复指定城市"
    echo ""
    echo "整合爬虫（活动和餐厅）:"
    echo "  ./run.sh --crawl-all --keyword \"上海\" --pages 5 --city 上海  # 同时爬取活动和餐厅"
    echo "  ./run.sh --crawl-all --keyword \"上海活动\" --pages 3 --no-restaurants  # 只爬取活动"
    echo "  ./run.sh --crawl-all --keyword \"上海美食\" --pages 3 --city 上海 --no-activities  # 只爬取餐厅"
    echo "  ./run.sh --crawl-all --keyword \"上海\" --pages 5 --activity-limit 5 --restaurant-limit 10  # 限制数量"
    echo ""
    echo "示例："
    echo "  # 只爬取内容"
    echo "  ./run.sh --crawl --keyword \"上海美食\" --pages 5 --output notes.json"
    echo ""
    echo "  # 只处理内容"
    echo "  ./run.sh --process --file notes.json --city 上海"
    echo ""
    echo "  # 只生成评论"
    echo "  ./run.sh --comments --limit 50"
    echo ""
    echo "  # 只搜索图片"
    echo "  ./run.sh --images --method bing --city 上海 --limit 10"
    echo ""
    echo "  # 完整流程（爬取+处理+评论+图片）"
    echo "  ./run.sh --crawl --keyword \"上海美食\" --pages 5 --process --comments --images --city 上海"
    echo ""
    exit 0
fi

# 解析参数，确定要运行的模块
RUN_CRAWL=false
RUN_PROCESS=false
RUN_COMMENTS=false
RUN_IMAGES=false
RUN_UPDATE_CATEGORIES=false
RUN_VALIDATE_IMAGES=false
RUN_UPDATE_LOCATION=false
RUN_UPDATE_FROM_AMAP=false
RUN_FIX_INCOMPLETE=false
RUN_CRAWL_ALL=false

CRAWL_OUTPUT=""
CRAWL_KEYWORD=""
CRAWL_PAGES=5

PROCESS_FILE=""
PROCESS_TITLE=""
PROCESS_DESC=""
PROCESS_CITY="上海"

COMMENTS_LIMIT=100
COMMENTS_TWEET_ID=""
COMMENTS_COUNT=""

IMAGES_METHOD="bing"
IMAGES_CITY="上海"
IMAGES_LIMIT=""
IMAGES_TWEET_ID=""
IMAGES_FORCE=false
IMAGES_SINCE_TIME=""

UPDATE_CATEGORIES_LIMIT=""
UPDATE_CATEGORIES_OFFSET=""
UPDATE_CATEGORIES_BATCH_SIZE=""
UPDATE_CATEGORIES_DRY_RUN=false
UPDATE_CATEGORIES_WHERE=""
UPDATE_CATEGORIES_SKIP_EXISTING=false

VALIDATE_IMAGES_LIMIT=""
VALIDATE_IMAGES_OFFSET=""
VALIDATE_IMAGES_BATCH_SIZE=""
VALIDATE_IMAGES_DRY_RUN=false
VALIDATE_IMAGES_WHERE=""
VALIDATE_IMAGES_MAX_WORKERS=""

UPDATE_LOCATION_LIMIT=""
UPDATE_LOCATION_OFFSET=""
UPDATE_LOCATION_DRY_RUN=false
UPDATE_LOCATION_WHERE=""
UPDATE_LOCATION_FORCE=false

UPDATE_FROM_AMAP_LIMIT=""
UPDATE_FROM_AMAP_OFFSET=""
UPDATE_FROM_AMAP_DRY_RUN=false
UPDATE_FROM_AMAP_WHERE=""
UPDATE_FROM_AMAP_SKIP_EXISTING=false
UPDATE_FROM_AMAP_TYPE_PID=""
UPDATE_FROM_AMAP_CITY=""

FIX_INCOMPLETE_LIMIT=""
FIX_INCOMPLETE_OFFSET=""
FIX_INCOMPLETE_DRY_RUN=false
FIX_INCOMPLETE_WHERE=""
FIX_INCOMPLETE_MIN_LENGTH=""

CRAWL_ALL_KEYWORD=""
CRAWL_ALL_PAGES=5
CRAWL_ALL_CITY="上海"
CRAWL_ALL_HEADLESS=false
CRAWL_ALL_NO_ACTIVITIES=false
CRAWL_ALL_NO_RESTAURANTS=false
CRAWL_ALL_ACTIVITY_LIMIT=""
CRAWL_ALL_RESTAURANT_LIMIT=""
CRAWL_ALL_NO_COMMENTS=false

# 解析参数
ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --crawl)
            RUN_CRAWL=true
            shift
            ;;
        --process)
            RUN_PROCESS=true
            shift
            ;;
        --comments)
            RUN_COMMENTS=true
            shift
            ;;
        --images)
            RUN_IMAGES=true
            shift
            ;;
        --update-categories)
            RUN_UPDATE_CATEGORIES=true
            shift
            ;;
        --validate-images)
            RUN_VALIDATE_IMAGES=true
            shift
            ;;
        --update-location)
            RUN_UPDATE_LOCATION=true
            shift
            ;;
        --update-from-amap)
            RUN_UPDATE_FROM_AMAP=true
            shift
            ;;
        --fix-incomplete)
            RUN_FIX_INCOMPLETE=true
            shift
            ;;
        --crawl-all)
            RUN_CRAWL_ALL=true
            shift
            ;;
        --no-activities)
            CRAWL_ALL_NO_ACTIVITIES=true
            shift
            ;;
        --no-restaurants)
            CRAWL_ALL_NO_RESTAURANTS=true
            shift
            ;;
        --activity-limit)
            CRAWL_ALL_ACTIVITY_LIMIT="$2"
            shift 2
            ;;
        --restaurant-limit)
            CRAWL_ALL_RESTAURANT_LIMIT="$2"
            shift 2
            ;;
        --no-comments)
            CRAWL_ALL_NO_COMMENTS=true
            shift
            ;;
        --headless)
            CRAWL_ALL_HEADLESS=true
            shift
            ;;
        --keyword)
            CRAWL_KEYWORD="$2"
            CRAWL_ALL_KEYWORD="$2"
            shift 2
            ;;
        --pages)
            CRAWL_PAGES="$2"
            CRAWL_ALL_PAGES="$2"
            shift 2
            ;;
        --output)
            CRAWL_OUTPUT="$2"
            shift 2
            ;;
        --file)
            PROCESS_FILE="$2"
            shift 2
            ;;
        --title)
            PROCESS_TITLE="$2"
            shift 2
            ;;
        --description)
            PROCESS_DESC="$2"
            shift 2
            ;;
        --city)
            PROCESS_CITY="$2"
            IMAGES_CITY="$2"
            UPDATE_FROM_AMAP_CITY="$2"
            CRAWL_ALL_CITY="$2"
            shift 2
            ;;
        --type-pid)
            UPDATE_FROM_AMAP_TYPE_PID="$2"
            shift 2
            ;;
        --limit)
            COMMENTS_LIMIT="$2"
            IMAGES_LIMIT="$2"
            UPDATE_CATEGORIES_LIMIT="$2"
            UPDATE_LOCATION_LIMIT="$2"
            UPDATE_FROM_AMAP_LIMIT="$2"
            FIX_INCOMPLETE_LIMIT="$2"
            shift 2
            ;;
        --tweet-id)
            COMMENTS_TWEET_ID="$2"
            IMAGES_TWEET_ID="$2"
            shift 2
            ;;
        --count)
            COMMENTS_COUNT="$2"
            shift 2
            ;;
        --method)
            IMAGES_METHOD="$2"
            shift 2
            ;;
        --force)
            IMAGES_FORCE=true
            UPDATE_LOCATION_FORCE=true
            shift
            ;;
        --since-time)
            IMAGES_SINCE_TIME="$2"
            shift 2
            ;;
        --offset)
            UPDATE_CATEGORIES_OFFSET="$2"
            UPDATE_LOCATION_OFFSET="$2"
            UPDATE_FROM_AMAP_OFFSET="$2"
            FIX_INCOMPLETE_OFFSET="$2"
            shift 2
            ;;
        --batch-size)
            UPDATE_CATEGORIES_BATCH_SIZE="$2"
            shift 2
            ;;
        --dry-run)
            UPDATE_CATEGORIES_DRY_RUN=true
            UPDATE_LOCATION_DRY_RUN=true
            UPDATE_FROM_AMAP_DRY_RUN=true
            FIX_INCOMPLETE_DRY_RUN=true
            shift
            ;;
        --where)
            UPDATE_CATEGORIES_WHERE="$2"
            UPDATE_LOCATION_WHERE="$2"
            UPDATE_FROM_AMAP_WHERE="$2"
            FIX_INCOMPLETE_WHERE="$2"
            shift 2
            ;;
        --skip-existing)
            UPDATE_CATEGORIES_SKIP_EXISTING=true
            UPDATE_FROM_AMAP_SKIP_EXISTING=true
            shift
            ;;
        --headless)
            ARGS+=("--headless")
            shift
            ;;
        --no-comments)
            ARGS+=("--no-comments")
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

# 如果没有指定任何模块，使用旧版兼容模式（调用crawler.py）
if [ "$RUN_CRAWL" = false ] && [ "$RUN_PROCESS" = false ] && [ "$RUN_COMMENTS" = false ] && [ "$RUN_IMAGES" = false ] && [ "$RUN_UPDATE_CATEGORIES" = false ] && [ "$RUN_VALIDATE_IMAGES" = false ] && [ "$RUN_UPDATE_LOCATION" = false ] && [ "$RUN_UPDATE_FROM_AMAP" = false ] && [ "$RUN_FIX_INCOMPLETE" = false ] && [ "$RUN_CRAWL_ALL" = false ]; then
    echo "未指定模块，使用兼容模式（调用 crawler.py）"
    python3 "$SCRIPT_DIR/crawler.py" "${ARGS[@]}"
    exit $?
fi

# 执行各个模块
TEMP_FILE=""

# 1. 爬虫模块
if [ "$RUN_CRAWL" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行爬虫模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    if [ -z "$CRAWL_KEYWORD" ]; then
        echo "错误: 爬虫模式需要指定 --keyword 参数"
        exit 1
    fi
    
    if [ -z "$CRAWL_OUTPUT" ]; then
        CRAWL_OUTPUT="notes_$(date +%Y%m%d_%H%M%S).json"
        echo "未指定输出文件，使用默认文件名: $CRAWL_OUTPUT"
    fi
    
    CRAWL_ARGS=("--keyword" "$CRAWL_KEYWORD" "--pages" "$CRAWL_PAGES" "--output" "$CRAWL_OUTPUT")
    if [[ " ${ARGS[@]} " =~ " --headless " ]]; then
        CRAWL_ARGS+=("--headless")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/crawl_all.py" "${CRAWL_ARGS[@]}"
    CRAWL_EXIT_CODE=$?
    
    if [ $CRAWL_EXIT_CODE -ne 0 ]; then
        echo "爬虫模块执行失败，退出码: $CRAWL_EXIT_CODE"
        exit $CRAWL_EXIT_CODE
    fi
    
    # 如果后续需要处理，设置临时文件
    if [ "$RUN_PROCESS" = true ] && [ -z "$PROCESS_FILE" ]; then
        PROCESS_FILE="$CRAWL_OUTPUT"
    fi
    
    TEMP_FILE="$CRAWL_OUTPUT"
fi

# 2. 内容处理模块
if [ "$RUN_PROCESS" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行内容处理模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    PROCESS_ARGS=("--city" "$PROCESS_CITY")
    
    if [ -n "$PROCESS_FILE" ]; then
        PROCESS_ARGS+=("--file" "$PROCESS_FILE")
    elif [ -n "$PROCESS_TITLE" ]; then
        PROCESS_ARGS+=("--title" "$PROCESS_TITLE")
        if [ -n "$PROCESS_DESC" ]; then
            PROCESS_ARGS+=("--description" "$PROCESS_DESC")
        fi
    else
        echo "错误: 内容处理模式需要指定 --file 或 --title 参数"
        exit 1
    fi
    
    if [[ " ${ARGS[@]} " =~ " --no-comments " ]]; then
        PROCESS_ARGS+=("--no-comments")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/data_processor.py" process "${PROCESS_ARGS[@]}"
    PROCESS_EXIT_CODE=$?
    
    if [ $PROCESS_EXIT_CODE -ne 0 ]; then
        echo "内容处理模块执行失败，退出码: $PROCESS_EXIT_CODE"
        exit $PROCESS_EXIT_CODE
    fi
fi

# 3. 评论生成模块
if [ "$RUN_COMMENTS" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行评论生成模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    COMMENTS_ARGS=("--limit" "$COMMENTS_LIMIT")
    
    if [ -n "$COMMENTS_TWEET_ID" ]; then
        COMMENTS_ARGS=("--tweet-id" "$COMMENTS_TWEET_ID")
    fi
    
    if [ -n "$COMMENTS_COUNT" ]; then
        COMMENTS_ARGS+=("--count" "$COMMENTS_COUNT")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/data_processor.py" comments "${COMMENTS_ARGS[@]}"
    COMMENTS_EXIT_CODE=$?
    
    if [ $COMMENTS_EXIT_CODE -ne 0 ]; then
        echo "评论生成模块执行失败，退出码: $COMMENTS_EXIT_CODE"
        exit $COMMENTS_EXIT_CODE
    fi
fi

# 4. 图片搜索模块
if [ "$RUN_IMAGES" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行图片搜索模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    IMAGES_ARGS=("--method" "$IMAGES_METHOD" "--city" "$IMAGES_CITY")
    
    if [ -n "$IMAGES_LIMIT" ]; then
        IMAGES_ARGS+=("--limit" "$IMAGES_LIMIT")
    fi
    
    if [ -n "$IMAGES_TWEET_ID" ]; then
        IMAGES_ARGS+=("--tweet-id" "$IMAGES_TWEET_ID")
    fi
    
    if [ "$IMAGES_FORCE" = true ]; then
        IMAGES_ARGS+=("--force")
    fi
    
    if [ -n "$IMAGES_SINCE_TIME" ]; then
        IMAGES_ARGS+=("--since-time" "$IMAGES_SINCE_TIME")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/data_processor.py" images "${IMAGES_ARGS[@]}"
    IMAGES_EXIT_CODE=$?
    
    if [ $IMAGES_EXIT_CODE -ne 0 ]; then
        echo "图片搜索模块执行失败，退出码: $IMAGES_EXIT_CODE"
        exit $IMAGES_EXIT_CODE
    fi
fi

# 5. 更新推文类目模块
if [ "$RUN_UPDATE_CATEGORIES" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行更新推文类目模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    UPDATE_CATEGORIES_ARGS=()
    
    if [ -n "$UPDATE_CATEGORIES_LIMIT" ]; then
        UPDATE_CATEGORIES_ARGS+=("--limit" "$UPDATE_CATEGORIES_LIMIT")
    fi
    
    if [ -n "$UPDATE_CATEGORIES_OFFSET" ]; then
        UPDATE_CATEGORIES_ARGS+=("--offset" "$UPDATE_CATEGORIES_OFFSET")
    fi
    
    if [ -n "$UPDATE_CATEGORIES_BATCH_SIZE" ]; then
        UPDATE_CATEGORIES_ARGS+=("--batch-size" "$UPDATE_CATEGORIES_BATCH_SIZE")
    fi
    
    if [ "$UPDATE_CATEGORIES_DRY_RUN" = true ]; then
        UPDATE_CATEGORIES_ARGS+=("--dry-run")
    fi
    
    if [ -n "$UPDATE_CATEGORIES_WHERE" ]; then
        UPDATE_CATEGORIES_ARGS+=("--where" "$UPDATE_CATEGORIES_WHERE")
    fi
    
    if [ "$UPDATE_CATEGORIES_SKIP_EXISTING" = true ]; then
        UPDATE_CATEGORIES_ARGS+=("--skip-existing")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/maintain_tweets.py" update-categories "${UPDATE_CATEGORIES_ARGS[@]}"
    UPDATE_CATEGORIES_EXIT_CODE=$?
    
    if [ $UPDATE_CATEGORIES_EXIT_CODE -ne 0 ]; then
        echo "更新推文类目模块执行失败，退出码: $UPDATE_CATEGORIES_EXIT_CODE"
        exit $UPDATE_CATEGORIES_EXIT_CODE
    fi
fi

# 6. 验证图片URL模块
if [ "$RUN_VALIDATE_IMAGES" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行验证图片URL模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    VALIDATE_IMAGES_ARGS=()
    
    if [ -n "$VALIDATE_IMAGES_LIMIT" ]; then
        VALIDATE_IMAGES_ARGS+=("--limit" "$VALIDATE_IMAGES_LIMIT")
    fi
    
    if [ -n "$VALIDATE_IMAGES_OFFSET" ]; then
        VALIDATE_IMAGES_ARGS+=("--offset" "$VALIDATE_IMAGES_OFFSET")
    fi
    
    if [ -n "$VALIDATE_IMAGES_BATCH_SIZE" ]; then
        VALIDATE_IMAGES_ARGS+=("--batch-size" "$VALIDATE_IMAGES_BATCH_SIZE")
    fi
    
    if [ "$VALIDATE_IMAGES_DRY_RUN" = true ]; then
        VALIDATE_IMAGES_ARGS+=("--dry-run")
    fi
    
    if [ -n "$VALIDATE_IMAGES_WHERE" ]; then
        VALIDATE_IMAGES_ARGS+=("--where" "$VALIDATE_IMAGES_WHERE")
    fi
    
    if [ -n "$VALIDATE_IMAGES_MAX_WORKERS" ]; then
        VALIDATE_IMAGES_ARGS+=("--max-workers" "$VALIDATE_IMAGES_MAX_WORKERS")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/maintain_tweets.py" validate-images "${VALIDATE_IMAGES_ARGS[@]}"
    VALIDATE_IMAGES_EXIT_CODE=$?
    
    if [ $VALIDATE_IMAGES_EXIT_CODE -ne 0 ]; then
        echo "验证图片URL模块执行失败，退出码: $VALIDATE_IMAGES_EXIT_CODE"
        exit $VALIDATE_IMAGES_EXIT_CODE
    fi
fi

# 7. 更新所属地区模块
if [ "$RUN_UPDATE_LOCATION" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行更新所属地区模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    UPDATE_LOCATION_ARGS=()
    
    if [ -n "$UPDATE_LOCATION_LIMIT" ]; then
        UPDATE_LOCATION_ARGS+=("--limit" "$UPDATE_LOCATION_LIMIT")
    fi
    
    if [ -n "$UPDATE_LOCATION_OFFSET" ]; then
        UPDATE_LOCATION_ARGS+=("--offset" "$UPDATE_LOCATION_OFFSET")
    fi
    
    if [ "$UPDATE_LOCATION_DRY_RUN" = true ]; then
        UPDATE_LOCATION_ARGS+=("--dry-run")
    fi
    
    if [ -n "$UPDATE_LOCATION_WHERE" ]; then
        UPDATE_LOCATION_ARGS+=("--where" "$UPDATE_LOCATION_WHERE")
    fi
    
    if [ "$UPDATE_LOCATION_FORCE" = true ]; then
        UPDATE_LOCATION_ARGS+=("--force")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/maintain_tweets.py" update-location "${UPDATE_LOCATION_ARGS[@]}"
    UPDATE_LOCATION_EXIT_CODE=$?
    
    if [ $UPDATE_LOCATION_EXIT_CODE -ne 0 ]; then
        echo "更新所属地区模块执行失败，退出码: $UPDATE_LOCATION_EXIT_CODE"
        exit $UPDATE_LOCATION_EXIT_CODE
    fi
fi

# 8. 整合高德地图API更新模块
if [ "$RUN_UPDATE_FROM_AMAP" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行整合高德地图API更新模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    UPDATE_FROM_AMAP_ARGS=()
    
    if [ -n "$UPDATE_FROM_AMAP_LIMIT" ]; then
        UPDATE_FROM_AMAP_ARGS+=("--limit" "$UPDATE_FROM_AMAP_LIMIT")
    fi
    
    if [ -n "$UPDATE_FROM_AMAP_OFFSET" ]; then
        UPDATE_FROM_AMAP_ARGS+=("--offset" "$UPDATE_FROM_AMAP_OFFSET")
    fi
    
    if [ "$UPDATE_FROM_AMAP_DRY_RUN" = true ]; then
        UPDATE_FROM_AMAP_ARGS+=("--dry-run")
    fi
    
    if [ -n "$UPDATE_FROM_AMAP_WHERE" ]; then
        UPDATE_FROM_AMAP_ARGS+=("--where" "$UPDATE_FROM_AMAP_WHERE")
    fi
    
    if [ "$UPDATE_FROM_AMAP_SKIP_EXISTING" = true ]; then
        UPDATE_FROM_AMAP_ARGS+=("--skip-existing")
    fi
    
    if [ -n "$UPDATE_FROM_AMAP_TYPE_PID" ]; then
        UPDATE_FROM_AMAP_ARGS+=("--type-pid" "$UPDATE_FROM_AMAP_TYPE_PID")
    fi
    
    if [ -n "$UPDATE_FROM_AMAP_CITY" ]; then
        UPDATE_FROM_AMAP_ARGS+=("--city" "$UPDATE_FROM_AMAP_CITY")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/maintain_tweets.py" update-from-amap "${UPDATE_FROM_AMAP_ARGS[@]}"
    UPDATE_FROM_AMAP_EXIT_CODE=$?
    
    if [ $UPDATE_FROM_AMAP_EXIT_CODE -ne 0 ]; then
        echo "整合高德地图API更新模块执行失败，退出码: $UPDATE_FROM_AMAP_EXIT_CODE"
        exit $UPDATE_FROM_AMAP_EXIT_CODE
    fi
fi

# 9. 修复未完成推文模块
if [ "$RUN_FIX_INCOMPLETE" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行修复未完成推文模块..."
    printf "=%.0s" {1..80}
    echo ""
    
    FIX_INCOMPLETE_ARGS=()
    
    if [ -n "$FIX_INCOMPLETE_LIMIT" ]; then
        FIX_INCOMPLETE_ARGS+=("--limit" "$FIX_INCOMPLETE_LIMIT")
    fi
    
    if [ -n "$FIX_INCOMPLETE_OFFSET" ]; then
        FIX_INCOMPLETE_ARGS+=("--offset" "$FIX_INCOMPLETE_OFFSET")
    fi
    
    if [ "$FIX_INCOMPLETE_DRY_RUN" = true ]; then
        FIX_INCOMPLETE_ARGS+=("--dry-run")
    fi
    
    if [ -n "$FIX_INCOMPLETE_WHERE" ]; then
        FIX_INCOMPLETE_ARGS+=("--where" "$FIX_INCOMPLETE_WHERE")
    fi
    
    if [ -n "$FIX_INCOMPLETE_MIN_LENGTH" ]; then
        FIX_INCOMPLETE_ARGS+=("--min-length" "$FIX_INCOMPLETE_MIN_LENGTH")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/maintain_tweets.py" fix-incomplete "${FIX_INCOMPLETE_ARGS[@]}"
    FIX_INCOMPLETE_EXIT_CODE=$?
    
    if [ $FIX_INCOMPLETE_EXIT_CODE -ne 0 ]; then
        echo "修复未完成推文模块执行失败，退出码: $FIX_INCOMPLETE_EXIT_CODE"
        exit $FIX_INCOMPLETE_EXIT_CODE
    fi
fi

# 10. 整合爬虫模块（活动和餐厅）
if [ "$RUN_CRAWL_ALL" = true ]; then
    echo ""
    printf "=%.0s" {1..80}
    echo ""
    echo "执行整合爬虫模块（活动和餐厅）..."
    printf "=%.0s" {1..80}
    echo ""
    
    if [ -z "$CRAWL_ALL_KEYWORD" ]; then
        echo "错误: --crawl-all 需要指定 --keyword 参数"
        exit 1
    fi
    
    CRAWL_ALL_ARGS=()
    
    CRAWL_ALL_ARGS+=("--keyword" "$CRAWL_ALL_KEYWORD")
    CRAWL_ALL_ARGS+=("--pages" "$CRAWL_ALL_PAGES")
    CRAWL_ALL_ARGS+=("--city" "$CRAWL_ALL_CITY")
    
    if [ "$CRAWL_ALL_HEADLESS" = true ]; then
        CRAWL_ALL_ARGS+=("--headless")
    fi
    
    if [ "$CRAWL_ALL_NO_ACTIVITIES" = true ]; then
        CRAWL_ALL_ARGS+=("--no-activities")
    fi
    
    if [ "$CRAWL_ALL_NO_RESTAURANTS" = true ]; then
        CRAWL_ALL_ARGS+=("--no-restaurants")
    fi
    
    if [ -n "$CRAWL_ALL_ACTIVITY_LIMIT" ]; then
        CRAWL_ALL_ARGS+=("--activity-limit" "$CRAWL_ALL_ACTIVITY_LIMIT")
    fi
    
    if [ -n "$CRAWL_ALL_RESTAURANT_LIMIT" ]; then
        CRAWL_ALL_ARGS+=("--restaurant-limit" "$CRAWL_ALL_RESTAURANT_LIMIT")
    fi
    
    if [ "$CRAWL_ALL_NO_COMMENTS" = true ]; then
        CRAWL_ALL_ARGS+=("--no-comments")
    fi
    
    python3 "$SCRIPT_DIR/app/scripts/crawl_all.py" "${CRAWL_ALL_ARGS[@]}"
    CRAWL_ALL_EXIT_CODE=$?
    
    if [ $CRAWL_ALL_EXIT_CODE -ne 0 ]; then
        echo "整合爬虫模块执行失败，退出码: $CRAWL_ALL_EXIT_CODE"
        exit $CRAWL_ALL_EXIT_CODE
    fi
fi

# 清理临时文件（可选）
# if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
#     echo "清理临时文件: $TEMP_FILE"
#     rm "$TEMP_FILE"
# fi

echo ""
printf "=%.0s" {1..80}
echo ""
echo "所有模块执行完成！"
printf "=%.0s" {1..80}
echo ""
