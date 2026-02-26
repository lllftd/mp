#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全能内容审核员 (AI Auditor)
模拟人类视角，对帖子的图片、标题、正文、评论进行全方位审核。
"""

import os
import sys
import json
import time
import base64
import logging
import argparse
import requests
from typing import List, Dict, Optional, Tuple, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from base.config import Config
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('full_audit.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class FullContentAuditor:
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        # 兼容处理
        if 'dashscope' in self.api_base and 'v1' not in self.api_base:
             self.api_base += '/compatible-mode/v1'
        
    def _get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _safe_json_load(self, content: str) -> Optional[Dict]:
        """安全解析JSON，处理Markdown代码块和常见的JSON错误"""
        try:
            content = content.strip()
            # 1. 移除 Markdown 标记
            if content.startswith('```'):
                # 找到第一个换行符
                first_newline = content.find('\n')
                if first_newline != -1:
                    content = content[first_newline+1:]
                # 移除结尾的 ```
                if content.endswith('```'):
                    content = content.rsplit('```', 1)[0]
            
            content = content.strip()
            
            # 2. 尝试解析
            return json.loads(content)
        except json.JSONDecodeError as e:
            # 3. 简单的自动修复尝试
            try:
                # 修复 "is_recommended": true, 后面可能缺少逗号或者 true 没被识别的问题
                # 尝试修复常见的尾部逗号缺失（例如 "reason": "..."}）
                fixed_content = content
                if '"}' in fixed_content and not '"}' in fixed_content.replace('\\"', ''):
                     # 如果看起来像是在字符串结束符后直接跟了花括号，可能是正常的
                     pass
                else:
                     # 尝试在某些特定模式下加逗号，但这很难通用
                     pass

                # 尝试使用 json5 (如果安装了)
                try:
                    import json5
                    return json5.loads(content)
                except:
                    pass

                # 尝试使用 ast.literal_eval (有时候模型输出的是 Python 字典格式 True/False)
                import ast
                # 将 true/false/null 替换为 Python 的 True/False/None
                py_content = content.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                return ast.literal_eval(py_content)
            except:
                pass
            
            # 如果还是失败，尝试正则表达式提取关键字段（针对特定的返回结构）
            try:
                import re
                result = {}
                
                # 提取 quality_score
                score_match = re.search(r'"quality_score"\s*:\s*(\d+)', content)
                if score_match:
                    result['quality_score'] = int(score_match.group(1))
                
                # 提取 is_recommended
                rec_match = re.search(r'"is_recommended"\s*:\s*(true|false|True|False)', content, re.IGNORECASE)
                if rec_match:
                    result['is_recommended'] = rec_match.group(1).lower() == 'true'
                
                # 提取 reason (比较难，因为可能包含换行)
                reason_match = re.search(r'"reason"\s*:\s*"(.*?)"', content, re.DOTALL)
                if reason_match:
                    result['reason'] = reason_match.group(1)
                
                # 如果提取到了关键信息，就返回
                if result:
                    logger.info("JSON解析失败，但通过正则提取到了部分信息")
                    return result
            except:
                pass
                
            logger.warning(f"JSON解析失败: {e} | 内容片段: {content[:100]}...")
            return None
        except Exception as e:
            logger.warning(f"JSON解析未知异常: {e}")
            return None

    def audit_images(self, image_urls: List[str], context_text: Dict) -> List[Tuple[str, int, str]]:
        """
        视觉审核：检查图片质量，并结合文本判断相关性
        Returns: (URL, 分数, 评价) 列表
        """
        if not image_urls:
            return []

        scored_images = []
        
        # 提示词：要求像人类编辑一样评分
        prompt = f"""你是一名严格的美食/生活方式主编。请评估这张图片作为"餐厅推荐"配图的质量。
        
        帖子标题：{context_text['title']}
        帖子正文摘要：{context_text['content'][:200]}...

        请从以下维度评分(0-10分):
        1. **构图与美感** (Composition): 构图是否专业，光线是否充足，是否有美感。
        2. **食欲感/吸引力** (Appeal): (如果是食物)是否让人有食欲，(如果是环境)是否让人想去。
        3. **清晰度与真实感** (Quality): 清晰度如何，是否过度P图/塑料感。
        4. **相关性** (Relevance): 图片内容是否与帖子描述的餐厅/食物高度一致。例如：帖子说火锅，图是寿司->0分。

        【拒绝标准】(直接0分，必须严厉拒绝):
        - 🚫 **图文不符**：图片内容与帖子描述完全无关（如描述中餐，图是西餐；描述火锅，图是奶茶）。
        - 🚫 **手机/App截图**：包含手机状态栏、电池图标、返回键、搜索框、底部导航栏、点赞/收藏按钮、用户头像条等UI元素。
        - 🚫 **脏乱差/环境恶劣**：后厨乱象、堆满杂物的台面、未清理的餐桌、不卫生的环境、垃圾堆。
        - 🚫 **牛皮癣文字/封面图**：图片上有后期添加的文字（如“第X集”、“店名”大字）、字幕、营销文案。
        - 🚫 **视频截图**：带有播放按钮、进度条、上下黑边或明显的字幕。
        - 🚫 **水印/Logo**：有明显的个人水印、营销号Logo（如“xx美食百科”）、第三方平台水印。
        - 🚫 **比例失调**：图片被严重拉伸或压扁，物体变形。
        - 🚫 **无关/低质**：二维码、纯文字截图、聊天记录、模糊不清。
        - 🚫 **拼图/多图拼接**：将多张图片拼接在一起的图片，或者像杂志排版一样的图片。
        - 🚫 **海报/广告图**：包含大量排版文字、促销信息、像传单一样的图片。

        请返回JSON: 
        {{
            "score": 8,
            "reason": "图文相符(火锅)，构图诱人",
            "is_high_quality": true
        }}
        """

        for url in image_urls:
            if not url.startswith('http'): 
                continue
                
            try:
                # 针对 Qwen-VL 等支持 URL 的模型
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": url}}
                            ]
                        }
                    ],
                    "max_tokens": 200,
                    "temperature": 0.1
                }
                
                resp = requests.post(f"{self.api_base}/chat/completions", headers=self._get_headers(), json=payload, timeout=30)
                
                if resp.status_code == 200:
                    res_json = resp.json()
                    content = res_json['choices'][0]['message']['content']
                    result = self._safe_json_load(content)
                    
                    if result:
                        score = result.get('score', 0)
                        reason = result.get('reason', 'unknown')

                        if score >= 4:
                            scored_images.append((url, score, reason))
                            logger.info(f"  🖼️ 图片评分 {score}: {reason}")
                        else:
                            logger.info(f"  🗑️ 图片低分淘汰 ({score}): {reason}")
                    else:
                        logger.warning(f"  ⚠️ 无法解析图片评分: {content[:20]}")
                        scored_images.append((url, 5, "解析失败保守保留")) 
                else:
                    logger.error(f"  ⚠️ 图片审核API错误: {resp.status_code}")
                    scored_images.append((url, 5, "API错误保留"))
            except Exception as e:
                logger.error(f"  ⚠️ 图片处理异常: {e}")
                scored_images.append((url, 5, "异常保留"))

        # 按分数排序（可选，如果需要把最好的放前面）
        scored_images.sort(key=lambda x: x[1], reverse=True)
        return [x[0] for x in scored_images]

    def audit_text_and_comments(self, title: str, content: str, comments: List[Dict]) -> Dict:
        """
        文本审核：评估内容质量 + 评论合理性
        """
        comments_text = json.dumps([
            {"id": c['id'], "content": c['content']} 
            for c in comments
        ], ensure_ascii=False)

        prompt = f"""你是一名资深的美食社区主编。请评估以下帖子及其评论的质量。

        【帖子内容】
        标题：{title}
        正文：{content}

        【评论列表】
        {comments_text}

        请执行以下评估任务：
        1. **内容质量评分 (0-10分)**：
           - **信息量**：是否提供了有价值的信息（具体菜品点评、避雷指南、环境细节、服务体验）？
           - **真实感**：是否像真实用户的亲身体验？
           - **可读性**：逻辑是否通顺，排版是否舒适？
           - **拒绝标准**：
             - 0-4分：内容空洞、虚假营销、数据堆砌、图文不符。
        
        2. **标题审核**：
           - 检查当前标题"{title}"是否为明确的**餐厅名称**（例如"海底捞"、"外婆家"）。
           - 🚫 如果标题是"今天吃什么"、"推荐一家好店"、"避雷"、"真好吃"等非餐厅名，请标记为需要修改。
           - 尝试从正文或评论中提取正确的餐厅名称。如果没有找到，保持原样但标记为低质量。

        3. **评论清洗**：
           - 找出所有**低质量/垃圾**评论ID（广告、辱骂、无关刷屏）。

        请返回严格JSON格式：
        {{
            "quality_score": 5,      // 内容质量评分
            "is_recommended": false,
            "reason": "内容平淡...",
            "delete_comment_ids": [],
            "title_check": {
                "is_valid_restaurant_name": false, // 当前标题是否已经是餐厅名
                "suggested_title": "老四川火锅"      // 如果当前标题不是，且能从内容提取到，则提供建议；否则null
            }
        }}
        """

        try:
            payload = {
                "model": self.model, # Qwen-VL-Plus 能力很强，也可以处理纯文本
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.1
            }
            
            resp = requests.post(f"{self.api_base}/chat/completions", headers=self._get_headers(), json=payload, timeout=60)
            
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                return self._safe_json_load(content)
            else:
                logger.error(f"文本审核API错误: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"文本审核异常: {e}")
            return None

# ==================== 核心流程 ====================

def run_audit(
    api_base: str,
    api_key: str,
    model: str,
    limit: int = 10,
    offset: int = 0,
    dry_run: bool = False
):
    auditor = FullContentAuditor(api_base, api_key, model)
    
    # 1. 获取帖子
    sql = """
        SELECT id, tweets_title, tweets_content, tweets_img 
        FROM tweets 
        WHERE tweets_img IS NOT NULL AND tweets_img != '[]'
        ORDER BY id DESC
        LIMIT :limit OFFSET :offset
    """
    logger.info("正在获取待审核数据...")
    df_tweets = db.execute_query(sql, {'limit': limit, 'offset': offset})
    
    if df_tweets.empty:
        logger.info("没有数据需要审核")
        return

    stats = {'post_deleted': 0, 'img_deleted': 0, 'comment_deleted': 0}

    for idx, row in df_tweets.iterrows():
        tweet_id = row['id']
        title = row['tweets_title'] or ""
        content = row['tweets_content'] or ""
        img_json = row['tweets_img']
        
        logger.info(f"\n[{idx+1}/{len(df_tweets)}] 正在像人类一样审视帖子: {title} (ID:{tweet_id})")

        # --- 步骤 1: 准备数据 ---
        try:
            images = json.loads(img_json) if isinstance(img_json, str) else img_json
            if not isinstance(images, list): images = []
        except:
            images = []

        # 获取评论
        comments_df = db.execute_query(
            "SELECT id, evaluate_content as content FROM tweets_evaluate WHERE tweets_id = :tid", 
            {'tid': tweet_id}
        )
        comments = comments_df.to_dict('records')

        # --- 步骤 2: 视觉审核 (Visual Audit) ---
        # 只有当有图片时才审
        valid_images = []
        if images:
            logger.info(f"  👁️ 正在检查 {len(images)} 张图片...")
            context_data = {
                'title': title,
                'content': content
            }
            valid_images = auditor.audit_images(images, context_data)
            deleted_count = len(images) - len(valid_images)
            if deleted_count > 0:
                stats['img_deleted'] += deleted_count
                logger.info(f"  ✂️ 剔除了 {deleted_count} 张不合适的图片")
        
        # 如果图片全被删光了，且原贴本该有图，这帖子可能就废了
        if images and not valid_images:
            logger.warning("  ⚠️ 所有图片均不合格，标记该贴可能质量极低")
            # 策略：如果图片全挂，直接删贴？或者保留纯文？这里选择保留纯文但清空图片
            
        # --- 步骤 3: 文本与评论审核 (Semantic Audit) ---
        logger.info(f"  🧠 正在阅读正文和 {len(comments)} 条评论...")
        text_result = auditor.audit_text_and_comments(title, content, comments)
        
        should_delete_post = False
        delete_comment_ids = []
        
        if text_result:
            quality_score = text_result.get('quality_score', 5)
            if quality_score <= 4:
                should_delete_post = True
                stats['post_deleted'] += 1
                logger.warning(f"  ❌ 帖子内容违规/质量差 ({quality_score}分): {text_result.get('reason')}")
            
            delete_comment_ids = text_result.get('delete_comment_ids', [])
            if delete_comment_ids:
                logger.info(f"  🧹 发现 {len(delete_comment_ids)} 条垃圾评论")

        # --- 步骤 4: 执行数据库更新 (Action) ---
        if dry_run:
            logger.info("  [试运行] 不执行修改")
            if text_result and text_result.get('is_recommended'):
                logger.info(f"  🌟 [优质内容] 评分: {text_result.get('quality_score')} - {text_result.get('reason')}")
            continue

        # A. 标记优质内容 (如果需要)
        # 这里只是打印日志，如果数据库有 is_recommended 字段，可以更新
        if text_result and text_result.get('is_recommended'):
            quality_score = text_result.get('quality_score', 0)
            logger.info(f"  🌟 [发现优质内容] ID:{tweet_id} 评分:{quality_score} - {text_result.get('reason')}")
            # db.execute_update("UPDATE tweets SET is_recommended = 1, quality_score = :score WHERE id = :id", {'score': quality_score, 'id': tweet_id})

        # B. 更新图片
        if len(valid_images) != len(images):
            new_json = json.dumps(valid_images, ensure_ascii=False)
            db.execute_update(
                "UPDATE tweets SET tweets_img = :img WHERE id = :id",
                {'img': new_json, 'id': tweet_id}
            )
            logger.info("  💾 [操作] 图片列表已更新")

        # C. 删除垃圾评论
        if delete_comment_ids:
            if len(delete_comment_ids) > 0:
                id_str = ",".join(map(str, delete_comment_ids))
                # 使用 text() 处理 IN 查询
                db.execute_update(
                    f"DELETE FROM tweets_evaluate WHERE id IN ({id_str})"
                )
                stats['comment_deleted'] += len(delete_comment_ids)
                logger.info(f"  💾 [操作] 已删除 {len(delete_comment_ids)} 条评论")

        # D. 更新标题 (如果需要)
        if text_result:
            title_check = text_result.get('title_check', {})
            suggested_title = title_check.get('suggested_title')
            is_valid_name = title_check.get('is_valid_restaurant_name', True)
            
            if suggested_title and suggested_title != title:
                db.execute_update(
                    "UPDATE tweets SET tweets_title = :title WHERE id = :id",
                    {'title': suggested_title, 'id': tweet_id}
                )
                logger.info(f"  📝 [操作] 标题已修正: '{title}' -> '{suggested_title}'")
            elif not is_valid_name and not suggested_title:
                # 如果标题不是餐厅名，且AI无法提取，这可能是一个低质量贴
                logger.warning(f"  ⚠️ 标题非餐厅名且无法修复: '{title}'")
                # 可以选择在这里进一步降分或标记，目前仅记录日志


    logger.info("="*50)
    logger.info(f"审核完成。统计: 删图 {stats['img_deleted']} 张, 删评 {stats['comment_deleted']} 条, 标记烂贴 {stats['post_deleted']} 个")

def main():
    parser = argparse.ArgumentParser(description='全能内容审核员')
    parser.add_argument('--api-base', type=str, required=True, help='API地址 (如阿里云百炼)')
    parser.add_argument('--api-key', type=str, required=True, help='API Key')
    parser.add_argument('--model', type=str, default='qwen-vl-plus', help='模型名称')
    parser.add_argument('--limit', type=int, default=10, help='处理数量')
    parser.add_argument('--offset', type=int, default=0, help='偏移量')
    parser.add_argument('--dry-run', action='store_true', help='试运行')
    
    args = parser.parse_args()
    
    run_audit(
        api_base=args.api_base,
        api_key=args.api_key,
        model=args.model,
        limit=args.limit,
        offset=args.offset,
        dry_run=args.dry_run
    )

if __name__ == '__main__':
    main()
