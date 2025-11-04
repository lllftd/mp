#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI转述模块 - 使用Ollama本地模型进行内容转述和分类
"""
import json
import requests
import logging
from typing import Dict, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)


class AIParaphraser:
    """AI转述工具（使用Ollama本地模型）"""
    
    def __init__(self):
        self.api_base = Config.LLM_API_BASE
        self.model = Config.LLM_MODEL
        self.max_tokens = Config.LLM_MAX_TOKENS
        
    def check_ollama_connection(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            # 检查Ollama服务状态
            response = requests.get(
                self.api_base.replace('/v1', '/api/tags'),
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama连接检查失败: {e}")
            return False
    
    def check_model_exists(self) -> bool:
        """检查模型是否已下载"""
        try:
            response = requests.get(
                self.api_base.replace('/v1', '/api/tags'),
                timeout=10
            )
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name', '') for m in models]
                return self.model in model_names
            return False
        except Exception as e:
            logger.warning(f"检查模型失败: {e}")
            return False
    
    def get_type_cid_mapping(self) -> Dict[str, list]:
        """获取分类类型到子类型ID的映射"""
        return {
            # 菜系分类
            "川菜": [6],
            "淮扬菜": [8],
            "杭帮菜": [9],
            "潮汕菜": [10],
            "烧烤": [11],
            "粤菜": [12],
            "德国菜": [13],
            "日本料理": [14],
            "法国菜": [15],
            "韩国料理": [16],
            "新疆菜": [17],
            "湘菜": [18],
            "农家菜": [19],
            "火锅": [20],
            "咖啡厅": [21],
            "自助餐": [22],
            "鱼鲜": [23],
            "东北菜": [24],
            "私房菜": [25],
            "东南亚菜": [26],
            "特色菜": [27],
            "创意菜": [28],
            "北京菜": [29],
            "家常菜": [30],
            "茶餐厅": [31],
            "小龙虾": [32],
            "素食": [33],
            "小吃快餐": [34],
            "面包甜点": [35],
            "面馆": [36],
            "大排档": [37],
            "西餐": [38],
            "云南菜": [39],
            "西北菜": [40],
            # 价格区间（可以组合）
            "人均50至100": [41],
            "人均100至200": [42],
            "人均200至300": [43],
            "人均300以上": [44],
            "人均50元以内": [45],
        }
    
    def classify_to_type_cid(self, title: str, description: str) -> str:
        """
        根据内容分类，返回对应的子类型ID（逗号分隔）
        
        Args:
            title: 标题
            description: 描述
            
        Returns:
            子类型ID字符串，如 "10,42" 或 "12"
        """
        if not title and not description:
            return Config.DEFAULT_TYPE_CID if Config.DEFAULT_TYPE_CID else "10"  # 默认返回潮汕菜
        
        try:
            # 构建分类提示词
            prompt = f"""请分析以下美食内容，判断属于哪个菜系和价格区间。

标题：{title}
描述：{description[:500]}

可选菜系分类：
川菜、淮扬菜、杭帮菜、潮汕菜、烧烤、粤菜、德国菜、日本料理、法国菜、韩国料理、新疆菜、湘菜、农家菜、火锅、咖啡厅、自助餐、鱼鲜、东北菜、私房菜、东南亚菜、特色菜、创意菜、北京菜、家常菜、茶餐厅、小龙虾、素食、小吃快餐、面包甜点、面馆、大排档、西餐、云南菜、西北菜

可选价格区间：
人均50元以内、人均50至100、人均100至200、人均200至300、人均300以上

请以JSON格式返回结果：
{{
    "cuisine": "菜系名称（如：潮汕菜、粤菜等，只能选一个）",
    "price_range": "价格区间（如：人均100至200，可选）"
}}

如果无法确定，菜系默认返回"潮汕菜"，价格区间可以不返回。"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的美食分类专家，擅长根据内容判断菜系和价格区间。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.3,  # 降低温度，使分类更准确
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 解析JSON响应
                try:
                    if '```json' in content:
                        json_start = content.find('```json') + 7
                        json_end = content.find('```', json_start)
                        content = content[json_start:json_end].strip()
                    elif '```' in content:
                        json_start = content.find('```') + 3
                        json_end = content.find('```', json_start)
                        content = content[json_start:json_end].strip()
                    
                    parsed = json.loads(content)
                    cuisine = parsed.get('cuisine', '潮汕菜')
                    price_range = parsed.get('price_range', '')
                    
                    # 映射到子类型ID
                    mapping = self.get_type_cid_mapping()
                    cid_list = []
                    
                    # 添加菜系ID
                    if cuisine in mapping:
                        cid_list.extend(mapping[cuisine])
                    
                    # 添加价格区间ID
                    if price_range and price_range in mapping:
                        cid_list.extend(mapping[price_range])
                    
                    # 如果都没有匹配到，返回默认值
                    if not cid_list:
                        return Config.DEFAULT_TYPE_CID if Config.DEFAULT_TYPE_CID else "10"
                    
                    # 去重并排序
                    cid_list = sorted(list(set(cid_list)))
                    return ','.join(map(str, cid_list))
                    
                except json.JSONDecodeError:
                    logger.warning(f"无法解析AI分类结果，使用默认值")
                    return Config.DEFAULT_TYPE_CID if Config.DEFAULT_TYPE_CID else "10"
            else:
                logger.warning(f"AI分类API调用失败: {response.status_code}")
                return Config.DEFAULT_TYPE_CID if Config.DEFAULT_TYPE_CID else "10"
                
        except Exception as e:
            logger.warning(f"AI分类失败: {e}，使用默认值")
            return Config.DEFAULT_TYPE_CID if Config.DEFAULT_TYPE_CID else "10"
    
    def paraphrase_and_classify(self, title: str, description: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        使用AI转述标题和描述，并分类，返回子类型ID
        
        Args:
            title: 原标题
            description: 原描述
            
        Returns:
            (转述后的标题, 转述后的描述, 分类类型, 子类型ID) 或 (None, None, None, None) 如果失败
        """
        if not title and not description:
            return None, None, None, None
        
        try:
            # 构建提示词
            prompt = f"""请将以下小红书笔记内容改写为原创内容，并判断内容类型。

原标题：{title}
原描述：{description[:500]}  # 限制描述长度

要求：
1. 保持原意不变，但用不同的表达方式
2. 使内容更自然、流畅
3. 判断内容类型（如：美食、旅行、穿搭、美妆、生活等）

请以JSON格式返回结果：
{{
    "title": "改写后的标题",
    "description": "改写后的描述",
    "type": "内容类型"
}}"""

            # 调用Ollama API
            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的内容改写专家，擅长将小红书笔记改写为原创内容，同时保持原意。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": self.max_tokens,
                "temperature": getattr(Config, 'LLM_TEMPERATURE', 0.7),  # 使用配置的温度参数
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 尝试解析JSON响应
                try:
                    # 提取JSON部分（可能包含markdown代码块）
                    if '```json' in content:
                        json_start = content.find('```json') + 7
                        json_end = content.find('```', json_start)
                        content = content[json_start:json_end].strip()
                    elif '```' in content:
                        json_start = content.find('```') + 3
                        json_end = content.find('```', json_start)
                        content = content[json_start:json_end].strip()
                    
                    parsed = json.loads(content)
                    paraphrased_title = parsed.get('title', title)
                    paraphrased_desc = parsed.get('description', description)
                    content_type = parsed.get('type', '生活')
                    
                    # 根据内容分类获取子类型ID
                    type_cid = self.classify_to_type_cid(title, description)
                    
                    return paraphrased_title, paraphrased_desc, content_type, type_cid
                except json.JSONDecodeError:
                    # 如果无法解析JSON，尝试提取文本
                    lines = content.strip().split('\n')
                    paraphrased_title = title  # 使用原标题
                    paraphrased_desc = description  # 使用原描述
                    content_type = '生活'
                    
                    # 尝试从文本中提取信息
                    for line in lines:
                        if '标题' in line or 'title' in line.lower():
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                paraphrased_title = parts[1].strip().strip('"\'')
                        elif '描述' in line or 'description' in line.lower():
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                paraphrased_desc = parts[1].strip().strip('"\'')
                        elif '类型' in line or 'type' in line.lower():
                            parts = line.split(':', 1)
                            if len(parts) > 1:
                                content_type = parts[1].strip().strip('"\'')
                    
                    # 根据内容分类获取子类型ID
                    type_cid = self.classify_to_type_cid(title, description)
                    
                    return paraphrased_title, paraphrased_desc, content_type, type_cid
            else:
                logger.error(f"AI转述API调用失败: {response.status_code} - {response.text}")
                return None, None, None, None
                
        except requests.exceptions.Timeout:
            logger.error("AI转述请求超时")
            return None, None, None, None
        except Exception as e:
            logger.error(f"AI转述失败: {e}")
            return None, None, None, None
    
    def paraphrase_only(self, text: str) -> Optional[str]:
        """仅转述文本内容"""
        if not text:
            return None
        
        try:
            prompt = f"""请将以下文本改写为原创内容，保持原意不变但用不同的表达方式：

原文：{text[:500]}

改写后的内容："""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": self.max_tokens,
                "temperature": getattr(Config, 'LLM_TEMPERATURE', 0.7)
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                return content.strip() if content else None
            else:
                logger.error(f"AI转述失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"AI转述失败: {e}")
            return None


# 全局实例
_paraphraser = None

def get_ai_paraphraser() -> AIParaphraser:
    """获取AI转述器单例"""
    global _paraphraser
    if _paraphraser is None:
        _paraphraser = AIParaphraser()
    return _paraphraser

