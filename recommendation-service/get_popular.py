#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取热门物品命令行脚本（优化版）

用法:
    python3 get_popular.py [top_n]

参数:
    top_n: 推荐数量（默认: 20）

示例:
    python3 get_popular.py 20
    python3 get_popular.py 10
"""
import sys
import json
import os
import logging

# 配置日志（只输出错误）
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine import Recommender
from config import Config

def output_json(code, data, message):
    """输出JSON格式结果"""
    result = {
        "code": code,
        "data": data,
        "message": message
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()

def main():
    """主函数：获取热门物品"""
    try:
        # 解析参数
        top_n = Config.RECOMMENDATION_COUNT
        if len(sys.argv) > 1:
            try:
                top_n = int(sys.argv[1])
                if top_n <= 0:
                    top_n = Config.RECOMMENDATION_COUNT
            except ValueError:
                top_n = Config.RECOMMENDATION_COUNT
        
        recommender = Recommender()
        popular_items = recommender.get_popular_items(top_n)
        
        output_json(200, popular_items, "success")
        
    except KeyboardInterrupt:
        output_json(500, None, "执行被中断")
        sys.exit(1)
    except Exception as e:
        logging.error(f"获取热门物品失败: {str(e)}", exc_info=True)
        output_json(500, None, f"Internal server error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

