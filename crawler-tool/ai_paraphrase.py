#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI转述模块 - 使用Ollama本地模型进行内容转述和分类
"""
import json
import re
import requests
import logging
import time
from typing import Dict, Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)


class AIParaphraser:
    """AI转述工具（使用Ollama本地模型）"""
    
    def __init__(self):
        self.api_base = Config.LLM_API_BASE
        self.model = Config.LLM_MODEL
        self.max_tokens = Config.LLM_MAX_TOKENS
        self._last_check_time = 0
        self._model_available_cache = None
        self._cache_duration = 60  # 缓存60秒
        
    def check_model_available(self, force_check: bool = False) -> Tuple[bool, str]:
        """
        检查模型是否可用（更详细的检查，带缓存）
        
        Args:
            force_check: 是否强制检查（忽略缓存）
        
        Returns:
            (是否可用, 错误信息)
        """
        import time as time_module
        
        # 使用缓存，避免频繁检查
        current_time = time_module.time()
        if not force_check and self._model_available_cache is not None:
            if current_time - self._last_check_time < self._cache_duration:
                return self._model_available_cache
        
        try:
            # 1. 检查Ollama服务是否运行
            try:
                response = requests.get(
                    self.api_base.replace('/v1', '/api/tags'),
                    timeout=5
                )
                if response.status_code != 200:
                    result = (False, f"Ollama服务不可用 (HTTP {response.status_code})")
                    self._model_available_cache = result
                    self._last_check_time = current_time
                    return result
            except requests.exceptions.ConnectionError:
                result = (False, "Ollama服务未运行或无法连接")
                self._model_available_cache = result
                self._last_check_time = current_time
                return result
            except requests.exceptions.Timeout:
                result = (False, "Ollama服务响应超时")
                self._model_available_cache = result
                self._last_check_time = current_time
                return result
            
            # 2. 检查模型是否已下载
            try:
                response = requests.get(
                    self.api_base.replace('/v1', '/api/tags'),
                    timeout=10
                )
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    model_names = [m.get('name', '') for m in models]
                    if self.model not in model_names:
                        result = (False, f"模型 {self.model} 未下载。已下载的模型: {', '.join(model_names) if model_names else '无'}")
                        self._model_available_cache = result
                        self._last_check_time = current_time
                        return result
                else:
                    result = (False, f"无法获取模型列表 (HTTP {response.status_code})")
                    self._model_available_cache = result
                    self._last_check_time = current_time
                    return result
            except Exception as e:
                result = (False, f"检查模型列表失败: {e}")
                self._model_available_cache = result
                self._last_check_time = current_time
                return result
            
            # 3. 尝试发送一个简单的测试请求
            try:
                test_url = f"{self.api_base}/chat/completions"
                test_payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": "你好"}
                    ],
                    "max_tokens": 10,
                    "stream": False
                }
                test_response = requests.post(test_url, json=test_payload, timeout=30)
                
                if test_response.status_code == 200:
                    result = (True, "模型可用")
                    self._model_available_cache = result
                    self._last_check_time = current_time
                    return result
                elif test_response.status_code == 500:
                    error_text = test_response.text[:200] if test_response.text else ""
                    if "process has terminated" in error_text:
                        result = (False, f"模型进程崩溃 (exit status 2)，可能是内存不足")
                    else:
                        result = (False, f"模型测试失败: {error_text}")
                    self._model_available_cache = result
                    self._last_check_time = current_time
                    return result
                else:
                    result = (False, f"模型测试失败 (HTTP {test_response.status_code})")
                    self._model_available_cache = result
                    self._last_check_time = current_time
                    return result
            except requests.exceptions.Timeout:
                result = (False, "模型测试超时（30秒），可能是模型太大或内存不足")
                self._model_available_cache = result
                self._last_check_time = current_time
                return result
            except Exception as e:
                result = (False, f"模型测试异常: {e}")
                self._model_available_cache = result
                self._last_check_time = current_time
                return result
                
        except Exception as e:
            result = (False, f"检查模型时出错: {e}")
            self._model_available_cache = result
            self._last_check_time = current_time
            return result
    
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
    
    def classify_to_type_cid(self, title: str, description: str) -> Optional[str]:
        """
        根据内容分类，返回对应的子类型ID（逗号分隔）
        
        Args:
            title: 标题
            description: 描述
            
        Returns:
            子类型ID字符串，如 "10,42" 或 "12"，如果分析失败返回None
        """
        if not title and not description:
            return None
        
        try:
            # 构建分类提示词
            prompt = f"""请分析以下美食内容，判断属于哪个菜系和价格区间。

标题：{title}
描述：{description[:500]}

可选菜系分类（必须选择其中一个）：
川菜、淮扬菜、杭帮菜、潮汕菜、烧烤、粤菜、德国菜、日本料理、法国菜、韩国料理、新疆菜、湘菜、农家菜、火锅、咖啡厅、自助餐、鱼鲜、东北菜、私房菜、东南亚菜、特色菜、创意菜、北京菜、家常菜、茶餐厅、小龙虾、素食、小吃快餐、面包甜点、面馆、大排档、西餐、云南菜、西北菜

可选价格区间（可选，如果内容中没有价格信息可以不填）：
人均50元以内、人均50至100、人均100至200、人均200至300、人均300以上

请以JSON格式返回结果：
{{
    "cuisine": "菜系名称（必须从上述列表中精确选择一个）",
    "price_range": "价格区间（如果无法确定可以不填）"
}}"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的美食分类专家，擅长根据内容判断菜系和价格区间。必须严格按照给定的分类列表进行选择。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 500,  # 进一步增加token限制，确保返回完整内容
                "temperature": 0.3,  # 降低温度，使分类更准确
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=90)  # 进一步增加超时时间
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 检查内容是否为空
                if not content or not content.strip():
                    logger.warning(f"AI分类API返回空内容，尝试重试...")
                    logger.warning(f"完整响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    logger.warning(f"请求参数: title={title[:50]}, description={description[:100] if description else 'None'}")
                    
                    # 重试一次（可能是模型响应慢）
                    try:
                        retry_response = requests.post(url, json=payload, timeout=60)
                        if retry_response.status_code == 200:
                            retry_result = retry_response.json()
                            retry_content = retry_result.get('choices', [{}])[0].get('message', {}).get('content', '')
                            if retry_content and retry_content.strip():
                                content = retry_content
                                logger.info("重试成功，获取到AI响应")
                            else:
                                logger.warning("重试后仍返回空内容，可能是模型无法识别该餐厅")
                                return None
                        else:
                            logger.warning(f"重试请求失败: {retry_response.status_code}")
                            return None
                    except Exception as retry_error:
                        logger.warning(f"重试请求异常: {retry_error}")
                        return None
                
                # 检查内容是否只是代码块标记（没有实际内容）
                if content.strip() in ['```json', '```', '```json\n', '```\n']:
                    logger.warning(f"AI分类API只返回了代码块标记，没有实际内容，尝试重试...")
                    logger.warning(f"请求参数: title={title[:50]}, description={description[:100] if description else 'None'}")
                    
                    # 重试一次（可能是模型响应被截断）
                    try:
                        time.sleep(5) 
                        retry_response = requests.post(url, json=payload, timeout=60)
                        if retry_response.status_code == 200:
                            retry_result = retry_response.json()
                            retry_content = retry_result.get('choices', [{}])[0].get('message', {}).get('content', '')
                            if retry_content and retry_content.strip() and retry_content.strip() not in ['```json', '```', '```json\n', '```\n']:
                                content = retry_content
                                logger.info("重试成功，获取到完整AI响应")
                            else:
                                logger.warning("重试后仍只返回代码块标记，可能是模型响应被截断")
                                return None
                        else:
                            logger.warning(f"重试请求失败: {retry_response.status_code}")
                            return None
                    except Exception as retry_error:
                        logger.warning(f"重试请求异常: {retry_error}")
                        return None
                
                # 解析JSON响应
                try:
                    # 清理内容
                    content_clean = content.strip()
                    
                    # 提取JSON部分（可能在```json```代码块中）
                    if '```json' in content_clean:
                        json_start = content_clean.find('```json') + 7
                        json_end = content_clean.find('```', json_start)
                        if json_end > json_start:
                            content_clean = content_clean[json_start:json_end].strip()
                        else:
                            # 如果只有开始标记没有结束标记，说明响应被截断
                            logger.warning(f"JSON代码块未闭合，可能是响应被截断: {content_clean[:100]}")
                            return None
                    elif '```' in content_clean:
                        json_start = content_clean.find('```') + 3
                        json_end = content_clean.find('```', json_start)
                        if json_end > json_start:
                            content_clean = content_clean[json_start:json_end].strip()
                        else:
                            # 如果只有开始标记没有结束标记，说明响应被截断
                            logger.warning(f"代码块未闭合，可能是响应被截断: {content_clean[:100]}")
                            return None
                    
                    # 如果清理后仍然是空的或只有标记，说明响应被截断
                    if not content_clean or content_clean in ['```json', '```']:
                        logger.warning(f"提取后内容为空，可能是响应被截断")
                        return None
                    
                    # 尝试找到JSON对象的开始和结束
                    if '{' in content_clean and '}' in content_clean:
                        json_start_idx = content_clean.find('{')
                        json_end_idx = content_clean.rfind('}')
                        if json_end_idx > json_start_idx:
                            content_clean = content_clean[json_start_idx:json_end_idx+1]
                    elif '{' not in content_clean:
                        # 如果没有找到JSON对象，说明响应可能不完整
                        logger.warning(f"未找到JSON对象，内容: {content_clean[:200]}")
                        return None
                    
                    # 尝试修复常见的JSON格式错误（分类结果）
                    # 1. 移除注释
                    content_clean = re.sub(r'//.*?$', '', content_clean, flags=re.MULTILINE)
                    content_clean = re.sub(r'/\*.*?\*/', '', content_clean, flags=re.DOTALL)
                    
                    # 2. 修复缺失的引号
                    content_clean = re.sub(r'(\w+):', r'"\1":', content_clean)
                    
                    # 3. 修复单引号为双引号
                    content_clean = content_clean.replace("'", '"')
                    
                    # 4. 修复缺失的逗号
                    content_clean = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', content_clean)
                    content_clean = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', content_clean)
                    
                    # 尝试解析JSON
                    try:
                        parsed = json.loads(content_clean)
                    except json.JSONDecodeError as parse_error:
                        # 如果解析失败，尝试手动修复缺失的逗号
                        error_msg = str(parse_error)
                        if "Expecting ','" in error_msg or "delimiter" in error_msg.lower():
                            # 更激进的逗号修复
                            fixed_content = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', content_clean)
                            fixed_content = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', fixed_content)
                            try:
                                parsed = json.loads(fixed_content)
                                logger.info("通过修复缺失逗号成功解析分类JSON")
                            except:
                                raise parse_error
                        else:
                            raise parse_error
                    
                    # 提取菜系和价格区间（支持多种字段名）
                    cuisine = parsed.get('cuisine', '') or parsed.get('菜系', '') or parsed.get('cuisine_type', '')
                    price_range = parsed.get('price_range', '') or parsed.get('价格区间', '') or parsed.get('price', '')
                    
                    # 如果没有找到菜系，返回None（取消兜底）
                    if not cuisine or not cuisine.strip():
                        logger.warning(f"AI未返回菜系分类，内容: {content[:200]}")
                        return None
                    
                    cuisine = cuisine.strip()
                    
                    # 映射到子类型ID
                    mapping = self.get_type_cid_mapping()
                    cid_list = []
                    
                    # 添加菜系ID
                    if cuisine in mapping:
                        cid_list.extend(mapping[cuisine])
                    else:
                        logger.warning(f"菜系 '{cuisine}' 不在映射表中，无法映射到子类型ID")
                        return None
                    
                    # 添加价格区间ID（可选）
                    if price_range and price_range.strip():
                        price_range = price_range.strip()
                        if price_range in mapping:
                            cid_list.extend(mapping[price_range])
                        else:
                            logger.warning(f"价格区间 '{price_range}' 不在映射表中，将忽略")
                    
                    # 如果都没有匹配到，返回None（取消兜底）
                    if not cid_list:
                        logger.warning(f"无法映射到任何子类型ID，菜系: {cuisine}, 价格区间: {price_range}")
                        return None
                    
                    # 去重并排序
                    cid_list = sorted(list(set(cid_list)))
                    return ','.join(map(str, cid_list))
                    
                except json.JSONDecodeError as je:
                    # JSON解析失败，返回None（取消兜底）
                    logger.warning(f"无法解析AI分类结果（JSON格式错误）: {je}")
                    logger.warning(f"错误位置: line {je.lineno if hasattr(je, 'lineno') else '?'}, column {je.colno if hasattr(je, 'colno') else '?'}")
                    logger.warning(f"原始内容: {content[:500] if content else '(空内容)'}")
                    logger.warning(f"清理后的内容: {content_clean[:500] if 'content_clean' in locals() else 'N/A'}")
                    logger.warning(f"请求参数 - 标题: {title[:100]}, 描述: {description[:200] if description else 'None'}")
                    return None
            else:
                logger.warning(f"AI分类API调用失败: {response.status_code}")
                logger.warning(f"响应内容: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.warning(f"AI分类失败: {e}")
            return None
    
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
    
    def extract_restaurants(self, title: str, description: str) -> list:
        """
        从笔记内容中提取餐厅信息，返回餐厅列表
        
        Args:
            title: 标题
            description: 描述
            
        Returns:
            餐厅列表，每个餐厅包含：name, address, price_range, description, images
        """
        if not title and not description:
            return []
        
        # 在请求前检查模型是否可用
        is_available, error_msg = self.check_model_available()
        if not is_available:
            logger.error(f"模型不可用: {error_msg}")
            logger.error("程序终止：AI模型不可用")
            raise Exception(f"AI模型不可用: {error_msg}")
        
        try:
            # 构建提取餐厅的提示词
            prompt = f"""请从以下小红书笔记中提取所有餐厅信息。

标题：{title}
描述：{description[:1500]}  # 限制长度

要求：
1. 识别笔记中提到的所有餐厅
2. 提取每个餐厅的名称、地址、人均价格、描述
3. 如果一个笔记只提到一个餐厅，也要提取出来
4. 如果笔记是美食攻略包含多个餐厅，要分别提取每个餐厅

请以JSON数组格式返回结果：
[
    {{
        "name": "餐厅名称",
        "address": "餐厅地址（如果有）",
        "price_range": "人均价格（如果有，如：96元、人均100至200）",
        "description": "该餐厅的描述和推荐理由"
    }},
    ...
]

如果笔记中没有明确的餐厅信息，返回空数组 []。"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的美食信息提取专家，擅长从小红书笔记中提取餐厅信息。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.3,  # 降低温度，使提取更准确
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
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
                    
                    restaurants = json.loads(content)
                    if isinstance(restaurants, list):
                        return restaurants
                    elif isinstance(restaurants, dict):
                        return [restaurants]  # 单个餐厅也转为列表
                    else:
                        return []
                    
                except json.JSONDecodeError:
                    logger.warning(f"无法解析AI提取的餐厅信息，尝试文本解析")
                    return []
            else:
                error_msg = f"AI提取餐厅API调用失败: {response.status_code}"
                try:
                    error_detail = response.text[:300] if response.text else "无错误详情"
                    error_msg += f" - {error_detail}"
                except:
                    pass
                logger.warning(error_msg)
                
                # 500错误时尝试重试
                if response.status_code == 500:
                    logger.info("检测到500错误，尝试重试提取餐厅...")
                    try:
                        time.sleep(2)
                        retry_response = requests.post(url, json=payload, timeout=60)
                        if retry_response.status_code == 200:
                            result = retry_response.json()
                            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                            if '```json' in content:
                                json_start = content.find('```json') + 7
                                json_end = content.find('```', json_start)
                                content = content[json_start:json_end].strip()
                            elif '```' in content:
                                json_start = content.find('```') + 3
                                json_end = content.find('```', json_start)
                                content = content[json_start:json_end].strip()
                            
                            restaurants = json.loads(content)
                            if isinstance(restaurants, list):
                                logger.info("重试成功，已提取餐厅信息")
                                return restaurants
                            elif isinstance(restaurants, dict):
                                return [restaurants]
                        else:
                            logger.warning(f"重试失败: {retry_response.status_code}")
                    except Exception as retry_e:
                        logger.warning(f"重试提取餐厅时出错: {retry_e}")
                
                return []
                
        except Exception as e:
            logger.warning(f"AI提取餐厅失败: {e}")
            return []
    
    def paraphrase_restaurant(self, restaurant_info: dict, original_title: str = "") -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        对单个餐厅进行转述和分类
        
        Args:
            restaurant_info: 餐厅信息字典，包含 name, address, price_range, description
            original_title: 原始笔记标题（可选）
            
        Returns:
            (转述后的标题, 转述后的描述, 子类型ID)
        """
        restaurant_name = restaurant_info.get('name', '')
        restaurant_address = restaurant_info.get('address', '')
        restaurant_price = restaurant_info.get('price_range', '')
        restaurant_desc = restaurant_info.get('description', '')
        
        if not restaurant_name:
            return None, None, None
        
        # 在请求前检查模型是否可用
        is_available, error_msg = self.check_model_available()
        if not is_available:
            logger.error(f"模型不可用: {error_msg}")
            logger.error("程序终止：AI模型不可用")
            raise Exception(f"AI模型不可用: {error_msg}")
        
        try:
            # 构建转述提示词（简化版本，减少token消耗）
            prompt = f"""请将以下餐厅信息改写为原创的小红书风格推荐文案。

餐厅名称：{restaurant_name}
餐厅地址：{restaurant_address if restaurant_address else '未知'}
人均价格：{restaurant_price if restaurant_price else '未知'}
餐厅描述：{restaurant_desc[:300]}  # 限制描述长度，减少token消耗

要求：
1. 生成一个吸引人的标题（不超过50字）
2. 生成详细的推荐描述（300-500字）
3. 保持原意但用不同的表达方式
4. 使用小红书风格的文案（自然、生动、有吸引力）

请以JSON格式返回结果：
{{
    "title": "改写后的标题",
    "description": "改写后的详细描述（300-500字）"
}}"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的小红书文案创作专家，擅长创作吸引人的美食推荐文案。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 600,  # 减少最大token数，降低内存压力
                "temperature": 0.7,
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 解析JSON响应 - 增强的解析逻辑
                try:
                    # 清理内容，移除可能的markdown格式
                    content_clean = content.strip()
                    
                    # 提取JSON部分（可能在```json```代码块中）
                    if '```json' in content_clean:
                        json_start = content_clean.find('```json') + 7
                        json_end = content_clean.find('```', json_start)
                        if json_end > json_start:
                            content_clean = content_clean[json_start:json_end].strip()
                    elif '```' in content_clean:
                        json_start = content_clean.find('```') + 3
                        json_end = content_clean.find('```', json_start)
                        if json_end > json_start:
                            content_clean = content_clean[json_start:json_end].strip()
                    
                    # 尝试找到JSON对象的开始和结束
                    if '{' in content_clean and '}' in content_clean:
                        json_start_idx = content_clean.find('{')
                        json_end_idx = content_clean.rfind('}')
                        if json_end_idx > json_start_idx:
                            content_clean = content_clean[json_start_idx:json_end_idx+1]
                    
                    # 尝试修复常见的JSON格式错误
                    # 1. 移除注释（// 或 /* */）
                    content_clean = re.sub(r'//.*?$', '', content_clean, flags=re.MULTILINE)
                    content_clean = re.sub(r'/\*.*?\*/', '', content_clean, flags=re.DOTALL)
                    
                    # 2. 修复缺失的引号（如果键名没有引号）
                    content_clean = re.sub(r'(\w+):', r'"\1":', content_clean)
                    
                    # 3. 修复单引号为双引号
                    content_clean = content_clean.replace("'", '"')
                    
                    # 4. 修复缺失的逗号（在字符串值后面，如果下一行是另一个键）
                    # 匹配模式1: "value"\n    "key2":  -> "value",\n    "key2":
                    content_clean = re.sub(r'"\s*\n\s*"([^"]+)"\s*:', r'",\n    "\1":', content_clean)
                    # 匹配模式2: "value"\n    "key2"  -> "value",\n    "key2"
                    content_clean = re.sub(r'"\s*\n\s*"([^"]+)"\s*:', r'",\n    "\1":', content_clean)
                    # 匹配模式3: 引号结束 -> 换行 -> 空白 -> 引号开始（新的键）
                    content_clean = re.sub(r'"\s*\n\s*"', '",\n    "', content_clean)
                    
                    # 尝试解析JSON
                    try:
                        parsed = json.loads(content_clean)
                    except json.JSONDecodeError as parse_error:
                        # 如果解析失败，尝试手动修复缺失的逗号
                        # 检查是否是逗号相关的错误
                        error_msg = str(parse_error)
                        if "Expecting ','" in error_msg or "delimiter" in error_msg.lower():
                            # 尝试更激进的逗号修复
                            # 模式：引号结束 -> 换行 -> 空白 -> 引号键名
                            fixed_content = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', content_clean)
                            # 模式：引号结束 -> 换行 -> 空白 -> 引号开始
                            fixed_content = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', fixed_content)
                            try:
                                parsed = json.loads(fixed_content)
                                logger.info("通过修复缺失逗号成功解析JSON")
                            except:
                                raise parse_error  # 如果修复后还是失败，抛出原始错误
                        else:
                            raise parse_error
                    except json.JSONDecodeError:
                        # 如果还是失败，尝试逐行解析，找到有效的JSON部分
                        lines = content_clean.split('\n')
                        json_lines = []
                        in_json = False
                        brace_count = 0
                        
                        for line in lines:
                            stripped = line.strip()
                            if '{' in stripped:
                                in_json = True
                                brace_count = stripped.count('{') - stripped.count('}')
                            if in_json:
                                json_lines.append(stripped)
                                brace_count += stripped.count('{') - stripped.count('}')
                                if brace_count <= 0 and '}' in stripped:
                                    break
                        
                        if json_lines:
                            content_clean = ' '.join(json_lines)
                            parsed = json.loads(content_clean)
                        else:
                            raise
                    
                    # 提取标题和描述
                    paraphrased_title = parsed.get('title', '')
                    paraphrased_desc = parsed.get('description', '')
                    
                    # 如果没有获取到标题，尝试从其他字段获取
                    if not paraphrased_title:
                        paraphrased_title = parsed.get('标题', '') or parsed.get('title_text', '') or restaurant_name
                    
                    # 如果没有获取到描述，尝试从其他字段获取
                    if not paraphrased_desc:
                        paraphrased_desc = parsed.get('描述', '') or parsed.get('desc', '') or parsed.get('content', '') or restaurant_desc
                    
                    # 如果仍然为空，使用原始值
                    if not paraphrased_title:
                        paraphrased_title = restaurant_name
                    if not paraphrased_desc:
                        paraphrased_desc = restaurant_desc
                    
                    # 如果描述中包含了地址和价格信息，补充进去
                    if restaurant_address and restaurant_address not in paraphrased_desc:
                        paraphrased_desc += f"\n📍地址：{restaurant_address}"
                    if restaurant_price and restaurant_price not in paraphrased_desc:
                        paraphrased_desc += f"\n💰人均：{restaurant_price}"
                    
                    # 分类并获取子类型ID
                    type_cid = self.classify_to_type_cid(paraphrased_title, paraphrased_desc)
                    
                    return paraphrased_title, paraphrased_desc, type_cid
                    
                except json.JSONDecodeError as je:
                    # JSON解析失败，尝试从文本中提取信息
                    logger.warning(f"无法解析AI转述结果（JSON格式错误）: {je}")
                    error_msg = str(je)
                    logger.warning(f"错误位置: line {je.lineno if hasattr(je, 'lineno') else '?'}, column {je.colno if hasattr(je, 'colno') else '?'}")
                    logger.warning(f"原始内容前500字符: {content[:500]}")
                    logger.debug(f"清理后的内容: {content_clean[:500] if 'content_clean' in locals() else 'N/A'}")
                    
                    # 如果是逗号相关的错误，尝试再次修复
                    if 'content_clean' in locals() and ("Expecting ','" in error_msg or "delimiter" in error_msg.lower()):
                        try:
                            # 更激进的逗号修复
                            fixed_content = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', content_clean)
                            fixed_content = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', fixed_content)
                            parsed = json.loads(fixed_content)
                            logger.info("通过手动修复逗号成功解析转述JSON")
                            
                            # 继续后续处理
                            paraphrased_title = parsed.get('title', '')
                            paraphrased_desc = parsed.get('description', '')
                            
                            if not paraphrased_title:
                                paraphrased_title = parsed.get('标题', '') or parsed.get('title_text', '') or restaurant_name
                            if not paraphrased_desc:
                                paraphrased_desc = parsed.get('描述', '') or parsed.get('desc', '') or parsed.get('content', '') or restaurant_desc
                            
                            if not paraphrased_title:
                                paraphrased_title = restaurant_name
                            if not paraphrased_desc:
                                paraphrased_desc = restaurant_desc
                            
                            if restaurant_address and restaurant_address not in paraphrased_desc:
                                paraphrased_desc += f"\n📍地址：{restaurant_address}"
                            if restaurant_price and restaurant_price not in paraphrased_desc:
                                paraphrased_desc += f"\n💰人均：{restaurant_price}"
                            
                            type_cid = self.classify_to_type_cid(paraphrased_title, paraphrased_desc)
                            return paraphrased_title, paraphrased_desc, type_cid
                        except Exception as fix_error:
                            logger.debug(f"手动修复逗号失败: {fix_error}")
                            # 继续使用文本提取
                    
                    # 尝试从文本中提取标题和描述
                    final_title = restaurant_name
                    final_desc = restaurant_desc
                    
                    # 尝试查找标题标记
                    title_markers = ['标题', 'title', 'Title']
                    desc_markers = ['描述', 'description', 'Description', '内容', 'content']
                    
                    for marker in title_markers:
                        if marker in content:
                            # 尝试提取标题
                            marker_idx = content.find(marker)
                            # 查找冒号或换行后的内容
                            if ':' in content[marker_idx:marker_idx+50]:
                                title_start = content.find(':', marker_idx) + 1
                                title_end = content.find('\n', title_start)
                                if title_end > title_start:
                                    extracted_title = content[title_start:title_end].strip().strip('"').strip("'")
                                    if extracted_title and len(extracted_title) > 5:
                                        final_title = extracted_title
                                        break
                    
                    for marker in desc_markers:
                        if marker in content:
                            # 尝试提取描述
                            marker_idx = content.find(marker)
                            if ':' in content[marker_idx:marker_idx+50]:
                                desc_start = content.find(':', marker_idx) + 1
                                # 查找下一个字段或结束
                                desc_end = len(content)
                                for next_marker in title_markers + desc_markers:
                                    next_idx = content.find(next_marker, desc_start + 50)
                                    if next_idx > desc_start and next_idx < desc_end:
                                        desc_end = next_idx
                                if desc_end > desc_start:
                                    extracted_desc = content[desc_start:desc_end].strip().strip('"').strip("'")
                                    if extracted_desc and len(extracted_desc) > 10:
                                        final_desc = extracted_desc
                                        break
                    
                    # 如果描述中包含了地址和价格信息，补充进去
                    if restaurant_address and restaurant_address not in final_desc:
                        final_desc += f"\n📍地址：{restaurant_address}"
                    if restaurant_price and restaurant_price not in final_desc:
                        final_desc += f"\n💰人均：{restaurant_price}"
                    
                    type_cid = self.classify_to_type_cid(final_title, final_desc)
                    return final_title, final_desc, type_cid
            else:
                error_msg = f"AI转述餐厅API调用失败: {response.status_code}"
                try:
                    error_detail = response.text[:500] if response.text else "无错误详情"
                    error_msg += f" - {error_detail}"
                    
                    # 检查是否是进程崩溃错误
                    if "process has terminated" in error_detail or "exit status" in error_detail:
                        logger.error("Ollama进程崩溃！可能原因：")
                        logger.error("1. 内存不足（deepseek-r1:32b需要大量内存）")
                        logger.error("2. 模型文件损坏或未完全下载")
                        logger.error("3. 请求过长导致超时")
                        logger.error("建议：检查系统内存，或使用更小的模型")
                        # 清除缓存，强制下次重新检查
                        self._model_available_cache = None
                except:
                    pass
                logger.warning(error_msg)
                
                # 如果是500错误，可能是模型处理问题，尝试重试一次
                if response.status_code == 500:
                    logger.info("检测到500错误，等待5秒后重试...")
                    try:
                        time.sleep(5)  # 等待更长时间，让Ollama恢复
                        retry_response = requests.post(url, json=payload, timeout=60)
                        if retry_response.status_code == 200:
                            result = retry_response.json()
                            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                            # 解析逻辑与上面相同（增强版）
                            try:
                                content_clean = content.strip()
                                
                                # 提取JSON部分
                                if '```json' in content_clean:
                                    json_start = content_clean.find('```json') + 7
                                    json_end = content_clean.find('```', json_start)
                                    if json_end > json_start:
                                        content_clean = content_clean[json_start:json_end].strip()
                                elif '```' in content_clean:
                                    json_start = content_clean.find('```') + 3
                                    json_end = content_clean.find('```', json_start)
                                    if json_end > json_start:
                                        content_clean = content_clean[json_start:json_end].strip()
                                
                                # 找到JSON对象
                                if '{' in content_clean and '}' in content_clean:
                                    json_start_idx = content_clean.find('{')
                                    json_end_idx = content_clean.rfind('}')
                                    if json_end_idx > json_start_idx:
                                        content_clean = content_clean[json_start_idx:json_end_idx+1]
                                
                                parsed = json.loads(content_clean)
                                
                                paraphrased_title = parsed.get('title', '') or parsed.get('标题', '') or parsed.get('title_text', '') or restaurant_name
                                paraphrased_desc = parsed.get('description', '') or parsed.get('描述', '') or parsed.get('desc', '') or parsed.get('content', '') or restaurant_desc
                                
                                if not paraphrased_title:
                                    paraphrased_title = restaurant_name
                                if not paraphrased_desc:
                                    paraphrased_desc = restaurant_desc
                                
                                if restaurant_address and restaurant_address not in paraphrased_desc:
                                    paraphrased_desc += f"\n📍地址：{restaurant_address}"
                                if restaurant_price and restaurant_price not in paraphrased_desc:
                                    paraphrased_desc += f"\n💰人均：{restaurant_price}"
                                
                                type_cid = self.classify_to_type_cid(paraphrased_title, paraphrased_desc)
                                logger.info("重试成功，已获取转述结果")
                                return paraphrased_title, paraphrased_desc, type_cid
                            except json.JSONDecodeError:
                                # 重试失败，使用基本信息
                                final_title = restaurant_name
                                final_desc = restaurant_desc
                                if restaurant_address:
                                    final_desc += f"\n📍地址：{restaurant_address}"
                                if restaurant_price:
                                    final_desc += f"\n💰人均：{restaurant_price}"
                                type_cid = self.classify_to_type_cid(final_title, final_desc)
                                logger.info("重试解析失败，使用基本信息")
                                return final_title, final_desc, type_cid
                        else:
                            logger.warning(f"重试失败: {retry_response.status_code}")
                            if "process has terminated" in str(retry_response.text):
                                logger.error("Ollama进程持续崩溃，请检查系统资源")
                                # 清除缓存，强制下次重新检查
                                self._model_available_cache = None
                    except Exception as retry_e:
                        logger.warning(f"重试时出错: {retry_e}")
                
                return None, None, None
                
        except requests.exceptions.Timeout:
            logger.error("AI转述餐厅请求超时（60秒）")
            logger.error("建议：检查Ollama服务状态，或使用更小的模型")
            return None, None, None
        except Exception as e:
            logger.warning(f"AI转述餐厅失败: {e}")
            return None, None, None


# 全局实例
_paraphraser = None

def get_ai_paraphraser() -> AIParaphraser:
    """获取AI转述器单例"""
    global _paraphraser
    if _paraphraser is None:
        _paraphraser = AIParaphraser()
    return _paraphraser

