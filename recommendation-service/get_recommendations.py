#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推荐算法命令行脚本
可以直接从Java调用，无需启动服务

用法:
    python3 get_recommendations.py <user_id> [method] [top_n]

参数:
    user_id: 用户ID（必需）
    method:  推荐方法（默认: hybrid）
              - collaborative/cf: 协同过滤推荐
              - content/cb: 内容过滤推荐
              - hybrid: 混合推荐（协同过滤+内容过滤，默认）
              - popular: 热门推荐
    top_n:   推荐数量（默认: 20）

示例:
    python3 get_recommendations.py 1 hybrid 20
    python3 get_recommendations.py 1 collaborative
    python3 get_recommendations.py 1  # 默认使用混合推荐
"""
import sys
import json
import os
import logging

# 配置日志（只输出错误，避免干扰JSON输出）
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]  # 错误输出到stderr
)

# 添加项目根目录到Python路径（支持作为包调用）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine import Recommender
from config import Config

def parse_args():
    """解析命令行参数"""
    if len(sys.argv) < 2:
        return None, None, None
    
    try:
        user_id = int(sys.argv[1])
        method = sys.argv[2] if len(sys.argv) > 2 else 'hybrid'  # 默认使用混合推荐
        top_n = int(sys.argv[3]) if len(sys.argv) > 3 else Config.RECOMMENDATION_COUNT
        
        # 验证参数
        if user_id <= 0:
            return None, None, None
        
        # 支持的推荐方法
        valid_methods = ['collaborative', 'cf', 'content', 'cb', 'hybrid', 'popular']
        if method not in valid_methods:
            method = 'hybrid'  # 如果不是有效方法，默认使用混合推荐
        
        if top_n <= 0:
            top_n = Config.RECOMMENDATION_COUNT
        
        return user_id, method, top_n
        
    except (ValueError, IndexError):
        return None, None, None

def output_json(code, data, message):
    """输出JSON格式结果"""
    result = {
        "code": code,
        "data": data,
        "message": message
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()  # 确保输出立即刷新

def main():
    """主函数：从命令行参数获取输入，输出JSON结果"""
    try:
        # 解析命令行参数
        user_id, method, top_n = parse_args()
        
        if user_id is None:
            output_json(400, None, "参数错误。用法: python3 get_recommendations.py <user_id> [method] [top_n]")
            sys.exit(1)
        
        # 执行推荐
        recommender = Recommender()
        recommendations = recommender.get_recommendations(user_id, method=method, top_n=top_n)
        
        # 如果没有推荐结果，返回热门物品
        if not recommendations:
            recommendations = recommender.get_popular_items(top_n)
        
        # 输出JSON结果
        output_json(200, recommendations, "success")
        
    except KeyboardInterrupt:
        output_json(500, None, "执行被中断")
        sys.exit(1)
    except Exception as e:
        # 错误信息输出到stderr，避免干扰JSON输出
        logging.error(f"获取推荐失败: {str(e)}", exc_info=True)
        output_json(500, None, f"Internal server error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

