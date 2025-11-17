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
import random
from typing import Dict, Optional, Tuple, List, Callable

from base.config import Config
from base.utils import get_random_username

logger = logging.getLogger(__name__)

# ==================== 常量配置 ====================

# 重试配置
MAX_RETRIES = 10
RETRY_DELAYS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
BASE_TIMEOUT_CLASSIFY = 90
BASE_TIMEOUT_EXTRACT = 240
BASE_TIMEOUT_PARAPHRASE = 120
BASE_TIMEOUT_COMMENTS = 180  # 评论生成需要更长时间，因为要生成多条
TIMEOUT_INCREMENT = 30

# 价格区间子类型ID
PRICE_RANGE_CIDS = [41, 42, 43, 44, 45]

# 模型检查缓存时间（秒）
MODEL_CHECK_CACHE_DURATION = 60


class AIParaphraser:
    """AI转述工具（使用Ollama本地模型）"""
    
    def __init__(self):
        self.api_base = Config.LLM_API_BASE
        self.model = Config.LLM_MODEL
        self.max_tokens = Config.LLM_MAX_TOKENS
        self._last_check_time = 0
        self._model_available_cache = None
        self._cache_duration = MODEL_CHECK_CACHE_DURATION
    
    def _update_cache(self, result: Tuple[bool, str]) -> None:
        """更新模型可用性缓存"""
        self._model_available_cache = result
        self._last_check_time = time.time()
        
    def check_model_available(self, force_check: bool = False) -> Tuple[bool, str]:
        """
        检查模型是否可用（更详细的检查，带缓存）
        
        Args:
            force_check: 是否强制检查（忽略缓存）
        
        Returns:
            (是否可用, 错误信息)
        """
        # 使用缓存，避免频繁检查
        current_time = time.time()
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
                    self._update_cache(result)
                    return result
            except requests.exceptions.ConnectionError:
                result = (False, "Ollama服务未运行或无法连接")
                self._update_cache(result)
                return result
            except requests.exceptions.Timeout:
                result = (False, "Ollama服务响应超时")
                self._update_cache(result)
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
                        self._update_cache(result)
                        return result
                else:
                    result = (False, f"无法获取模型列表 (HTTP {response.status_code})")
                    self._update_cache(result)
                    return result
            except Exception as e:
                result = (False, f"检查模型列表失败: {e}")
                self._update_cache(result)
                return result
            
            # 3. 尝试发送一个简单的测试请求
            try:
                test_url = f"{self.api_base}/chat/completions"
                test_payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "你好"}],
                    "max_tokens": 10,
                    "stream": False
                }
                test_response = requests.post(test_url, json=test_payload, timeout=30)
                
                if test_response.status_code == 200:
                    result = (True, "模型可用")
                    self._update_cache(result)
                    return result
                elif test_response.status_code == 500:
                    error_text = test_response.text[:200] if test_response.text else ""
                    if "process has terminated" in error_text:
                        result = (False, "模型进程崩溃 (exit status 2)，可能是内存不足")
                    else:
                        result = (False, f"模型测试失败: {error_text}")
                    self._update_cache(result)
                    return result
                else:
                    result = (False, f"模型测试失败 (HTTP {test_response.status_code})")
                    self._update_cache(result)
                    return result
            except requests.exceptions.Timeout:
                result = (False, "模型测试超时（30秒），可能是模型太大或内存不足")
                self._update_cache(result)
                return result
            except Exception as e:
                result = (False, f"模型测试异常: {e}")
                self._update_cache(result)
                return result
                
        except Exception as e:
            result = (False, f"检查模型时出错: {e}")
            self._update_cache(result)
            return result
    
    def check_ollama_connection(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
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
    
    def get_price_range_cid(self, price_range: str) -> Optional[int]:
        """
        根据人均价格字符串（如"96元"）返回对应的价格区间子类型ID
        
        Args:
            price_range: 人均价格字符串，如"96元"、"100-200"、"人均150元"等
            
        Returns:
            价格区间子类型ID，如果无法解析则返回None
        """
        if not price_range or not price_range.strip():
            return None
        
        # 提取数字（支持多种格式：96元、100-200、人均150元等）
        price_str = price_range.strip()
        price_str = price_str.replace('人均', '').replace('元', '').replace('¥', '').replace('RMB', '').replace('rmb', '').strip()
        
        # 提取数字（支持范围，如"100-200"）
        numbers = re.findall(r'\d+', price_str)
        
        if not numbers:
            return None
        
        try:
            # 如果有多个数字（范围），取平均值
            if len(numbers) >= 2:
                price = (int(numbers[0]) + int(numbers[1])) / 2
            else:
                price = int(numbers[0])
            
            # 映射到价格区间子类型ID
            if price < 50:
                return 45  # 人均50元以内
            elif price < 100:
                return 41  # 人均50至100
            elif price < 200:
                return 42  # 人均100至200
            elif price < 300:
                return 43  # 人均200至300
            else:
                return 44  # 人均300以上
                
        except (ValueError, IndexError):
            logger.warning(f"无法解析价格区间: {price_range}")
            return None
    
    def get_type_cid_mapping(self) -> Dict[str, list]:
        """获取分类类型到子类型ID的映射"""
        return {
            # 菜系分类
            "川菜": [6], "淮扬菜": [8], "杭帮菜": [9], "潮汕菜": [10], "烧烤": [11],
            "粤菜": [12], "德国菜": [13], "日本料理": [14], "法国菜": [15], "韩国料理": [16],
            "新疆菜": [17], "湘菜": [18], "农家菜": [19], "火锅": [20], "咖啡厅": [21],
            "自助餐": [22], "鱼鲜": [23], "东北菜": [24], "私房菜": [25], "东南亚菜": [26],
            "特色菜": [27], "创意菜": [28], "北京菜": [29], "家常菜": [30], "茶餐厅": [31],
            "小龙虾": [32], "素食": [33], "小吃快餐": [34], "面包甜点": [35], "面馆": [36],
            "大排档": [37], "西餐": [38], "云南菜": [39], "西北菜": [40],
            # 补充菜系
            "意大利菜": [46], "泰国菜": [47], "越南菜": [48], "印度菜": [49], "墨西哥菜": [50],
            "西班牙菜": [51], "土耳其菜": [52], "希腊菜": [53], "巴西菜": [54],
            "徽菜": [55], "鲁菜": [56], "闽菜": [57], "豫菜": [58], "赣菜": [59],
            "鄂菜": [60], "桂菜": [61], "琼菜": [62], "贵菜": [63], "藏菜": [64],
            # 价格区间（可以组合）
            "人均50至100": [41], "人均100至200": [42], "人均200至300": [43],
            "人均300以上": [44], "人均50元以内": [45],
            # 用餐场景
            "早餐": [65], "午餐": [66], "晚餐": [67], "夜宵": [68], "下午茶": [69],
            "商务宴请": [70], "情侣约会": [71], "家庭聚餐": [72], "朋友聚会": [73], "生日聚会": [74],
            # 餐厅特色
            "网红餐厅": [75], "老字号": [76], "米其林": [77], "黑珍珠": [78], "必吃榜": [79],
            "人气餐厅": [80], "新店开业": [81], "连锁品牌": [82], "独立小店": [83],
            # 服务类型
            "外卖": [84], "堂食": [85], "外带": [86], "自助": [87], "套餐": [88], "单点": [89],
            # 环境特色
            "露天": [90], "包间": [91], "景观": [92], "主题餐厅": [93], "音乐餐厅": [94],
            "酒吧": [95], "无烟": [96],
            # 特殊需求
            "清真": [97], "无糖": [98], "低卡": [99], "儿童友好": [100], "宠物友好": [101],
            "无障碍": [102], "停车方便": [103],
            # 时间特色
            "24小时": [104], "深夜食堂": [105], "早市": [106], "夜市": [107],
            # 其他分类
            "地方特色": [108], "国际美食": [109], "融合菜": [110], "健康餐": [111],
            "快餐": [112], "甜品店": [113], "饮品店": [114],
        }
    
    def _extract_json_from_content(self, content: str) -> Optional[str]:
        """
        从AI响应中提取JSON内容
        
        Args:
            content: AI返回的原始内容
            
        Returns:
            提取的JSON字符串，如果提取失败返回None
        """
        if not content or not content.strip():
            return None
        
        # 检查是否只是代码块标记（没有实际内容）
        if content.strip() in ['```json', '```', '```json\n', '```\n']:
            return None
        
        content_clean = content.strip()
        
        # 提取JSON部分（可能在```json```代码块中）
        if '```json' in content_clean:
            json_start = content_clean.find('```json') + 7
            json_end = content_clean.find('```', json_start)
            if json_end > json_start:
                content_clean = content_clean[json_start:json_end].strip()
            else:
                logger.warning(f"JSON代码块未闭合，可能是响应被截断: {content_clean[:100]}")
                return None
        elif '```' in content_clean:
            json_start = content_clean.find('```') + 3
            json_end = content_clean.find('```', json_start)
            if json_end > json_start:
                content_clean = content_clean[json_start:json_end].strip()
            else:
                logger.warning(f"代码块未闭合，可能是响应被截断: {content_clean[:100]}")
                return None
        
        # 如果清理后仍然是空的或只有标记，说明响应被截断
        if not content_clean or content_clean in ['```json', '```']:
            return None
        
        # 尝试找到JSON对象的开始和结束
        if '{' in content_clean and '}' in content_clean:
            json_start_idx = content_clean.find('{')
            json_end_idx = content_clean.rfind('}')
            if json_end_idx > json_start_idx:
                content_clean = content_clean[json_start_idx:json_end_idx+1]
        elif '[' in content_clean and ']' in content_clean:
            # 处理JSON数组
            json_start_idx = content_clean.find('[')
            json_end_idx = content_clean.rfind(']')
            if json_end_idx > json_start_idx:
                content_clean = content_clean[json_start_idx:json_end_idx+1]
        elif '{' not in content_clean and '[' not in content_clean:
            # 如果没有找到JSON对象或数组，说明响应可能不完整
            logger.warning(f"未找到JSON对象或数组，内容: {content_clean[:200]}")
            return None
        
        return content_clean
    
    def _fix_json_format(self, json_str: str) -> str:
        """
        修复常见的JSON格式错误
        
        Args:
            json_str: 需要修复的JSON字符串
            
        Returns:
            修复后的JSON字符串
        """
        # 1. 移除注释
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 2. 修复缺失的引号（如果键名没有引号）
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        # 3. 修复单引号为双引号
        json_str = json_str.replace("'", '"')
        
        # 4. 修复缺失的逗号
        json_str = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', json_str)
        json_str = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', json_str)
        
        return json_str
    
    def _parse_json_response(self, content: str, is_array: bool = False) -> Optional[dict]:
        """
        解析AI返回的JSON响应
        
        Args:
            content: AI返回的原始内容
            is_array: 是否为数组格式
            
        Returns:
            解析后的JSON对象或数组，如果解析失败返回None
        """
        json_content = self._extract_json_from_content(content)
        if not json_content:
            return None
        
        try:
            # 尝试修复JSON格式
            json_content = self._fix_json_format(json_content)
            parsed = json.loads(json_content)
            return parsed
        except json.JSONDecodeError as parse_error:
            error_msg = str(parse_error)
            
            # 处理"Extra data"错误：尝试只解析第一个JSON对象
            if "Extra data" in error_msg:
                try:
                    # 使用JSONDecoder的raw_decode方法只解析第一个对象
                    decoder = json.JSONDecoder()
                    parsed, idx = decoder.raw_decode(json_content)
                    logger.debug(f"通过提取第一个JSON对象成功解析（位置: {idx}）")
                    return parsed
                except json.JSONDecodeError:
                    # 如果raw_decode也失败，尝试手动提取第一个完整的JSON对象
                    try:
                        # 找到第一个{的位置
                        start_idx = json_content.find('{')
                        if start_idx == -1:
                            start_idx = json_content.find('[')
                        if start_idx == -1:
                            return None
                        
                        # 从第一个{或[开始，找到匹配的结束位置
                        brace_count = 0
                        bracket_count = 0
                        in_string = False
                        escape_next = False
                        
                        for i in range(start_idx, len(json_content)):
                            char = json_content[i]
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                            
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                elif char == '[':
                                    bracket_count += 1
                                elif char == ']':
                                    bracket_count -= 1
                                
                                if brace_count == 0 and bracket_count == 0:
                                    # 找到完整的JSON对象
                                    first_json = json_content[start_idx:i+1]
                                    parsed = json.loads(first_json)
                                    logger.debug("通过手动提取第一个JSON对象成功解析")
                                    return parsed
                        
                        return None
                    except Exception as e:
                        logger.debug(f"手动提取JSON对象失败: {e}")
            
            # 如果解析失败，尝试手动修复缺失的逗号
            if "Expecting ','" in error_msg or "delimiter" in error_msg.lower():
                # 更激进的逗号修复
                fixed_content = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', json_content)
                fixed_content = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', fixed_content)
                try:
                    parsed = json.loads(fixed_content)
                    logger.debug("通过修复缺失逗号成功解析JSON")
                    return parsed
                except:
                    pass
            
            logger.warning(f"无法解析JSON响应: {parse_error}")
            logger.debug(f"原始内容: {content[:500]}")
            logger.debug(f"清理后的内容: {json_content[:500]}")
            return None
    
    def _retry_request(self, request_func: Callable, base_timeout: int, operation_name: str) -> Optional[requests.Response]:
        """
        带重试机制的请求执行
        
        Args:
            request_func: 请求函数，接受timeout参数
            base_timeout: 基础超时时间（秒）
            operation_name: 操作名称（用于日志）
            
        Returns:
            响应对象，如果失败返回None
        """
        for attempt in range(MAX_RETRIES):
            try:
                timeout_val = base_timeout + (attempt * TIMEOUT_INCREMENT)
                logger.info(f"{operation_name} - 尝试 {attempt + 1}/{MAX_RETRIES}，超时: {timeout_val}秒")
                
                response = request_func(timeout_val)
                
                if response.status_code == 200:
                    return response
                elif attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                    logger.warning(f"{operation_name}失败 (HTTP {response.status_code})，{delay}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"{operation_name}最终失败: HTTP {response.status_code}")
                    return None
            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                    logger.warning(f"{operation_name}超时，{delay}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"{operation_name}最终超时")
                    return None
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                    logger.warning(f"{operation_name}异常: {e}，{delay}秒后重试...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"{operation_name}最终失败: {e}")
                    return None
        
        return None
    
    def _map_to_type_cids(
        self, 
        cuisine: str, 
        price_range: Optional[str] = None,
        scenes: Optional[list] = None,
        features: Optional[list] = None,
        service_types: Optional[list] = None,
        environment: Optional[list] = None,
        special_needs: Optional[list] = None,
        time_features: Optional[list] = None
    ) -> Optional[str]:
        """
        将多个分类维度映射到子类型ID
        
        Args:
            cuisine: 菜系名称（必需）
            price_range: 价格区间（可选）
            scenes: 用餐场景列表（可选）
            features: 餐厅特色列表（可选）
            service_types: 服务类型列表（可选）
            environment: 环境特色列表（可选）
            special_needs: 特殊需求列表（可选）
            time_features: 时间特色列表（可选）
            
        Returns:
            子类型ID字符串（逗号分隔），如果映射失败返回None
        """
        if not cuisine or not cuisine.strip():
            return None
        
        cuisine = cuisine.strip()
        mapping = self.get_type_cid_mapping()
        cid_list = []
        
        # 添加菜系ID（必需）
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
        
        # 添加用餐场景ID（可选，可多选）
        if scenes:
            for scene in scenes:
                if isinstance(scene, str) and scene.strip():
                    scene = scene.strip()
                    if scene in mapping:
                        cid_list.extend(mapping[scene])
                    else:
                        logger.debug(f"用餐场景 '{scene}' 不在映射表中，将忽略")
        
        # 添加餐厅特色ID（可选，可多选）
        if features:
            for feature in features:
                if isinstance(feature, str) and feature.strip():
                    feature = feature.strip()
                    if feature in mapping:
                        cid_list.extend(mapping[feature])
                    else:
                        logger.debug(f"餐厅特色 '{feature}' 不在映射表中，将忽略")
        
        # 添加服务类型ID（可选，可多选）
        if service_types:
            for service in service_types:
                if isinstance(service, str) and service.strip():
                    service = service.strip()
                    if service in mapping:
                        cid_list.extend(mapping[service])
                    else:
                        logger.debug(f"服务类型 '{service}' 不在映射表中，将忽略")
        
        # 添加环境特色ID（可选，可多选）
        if environment:
            for env in environment:
                if isinstance(env, str) and env.strip():
                    env = env.strip()
                    if env in mapping:
                        cid_list.extend(mapping[env])
                    else:
                        logger.debug(f"环境特色 '{env}' 不在映射表中，将忽略")
        
        # 添加特殊需求ID（可选，可多选）
        if special_needs:
            for need in special_needs:
                if isinstance(need, str) and need.strip():
                    need = need.strip()
                    if need in mapping:
                        cid_list.extend(mapping[need])
                    else:
                        logger.debug(f"特殊需求 '{need}' 不在映射表中，将忽略")
        
        # 添加时间特色ID（可选，可多选）
        if time_features:
            for time_feat in time_features:
                if isinstance(time_feat, str) and time_feat.strip():
                    time_feat = time_feat.strip()
                    if time_feat in mapping:
                        cid_list.extend(mapping[time_feat])
                    else:
                        logger.debug(f"时间特色 '{time_feat}' 不在映射表中，将忽略")
        
        if not cid_list:
            logger.warning(f"无法映射到任何子类型ID，菜系: {cuisine}")
            return None
        
        # 去重并排序
        cid_list = sorted(list(set(cid_list)))
        return ','.join(map(str, cid_list))
                    
    def _supplement_price_cid(self, type_cid: Optional[str], price_range: Optional[str]) -> Optional[str]:
        """
        补充价格区间ID（如果AI分类没有包含）
        
        Args:
            type_cid: 现有的子类型ID字符串（逗号分隔）
            price_range: 价格区间字符串
            
        Returns:
            更新后的子类型ID字符串
        """
        if not price_range:
            return type_cid
        
        if type_cid:
            cid_list = [int(cid.strip()) for cid in type_cid.split(',') if cid.strip()]
            has_price_cid = any(cid in PRICE_RANGE_CIDS for cid in cid_list)
            
            if not has_price_cid:
                price_cid = self.get_price_range_cid(price_range)
                if price_cid:
                    cid_list.append(price_cid)
                    logger.info(f"根据人均价格 {price_range} 补充价格区间子类型ID: {price_cid}")
                    cid_list = sorted(list(set(cid_list)))
                    return ','.join(map(str, cid_list))
        else:
            # 如果AI分类失败，但提供了price_range，至少返回价格区间ID
            price_cid = self.get_price_range_cid(price_range)
            if price_cid:
                logger.warning(f"AI分类失败，但根据人均价格 {price_range} 返回价格区间子类型ID: {price_cid}")
                return str(price_cid)
        
        return type_cid
    
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
            # 构建分类提示词（包含所有114个类型）
            prompt = f"""请分析以下美食内容，判断属于哪个菜系、价格区间、用餐场景、餐厅特色等。

标题：{title}
描述：{description[:500]}

可选菜系分类（必须选择其中一个）：
川菜、淮扬菜、杭帮菜、潮汕菜、烧烤、粤菜、德国菜、日本料理、法国菜、韩国料理、新疆菜、湘菜、农家菜、火锅、咖啡厅、自助餐、鱼鲜、东北菜、私房菜、东南亚菜、特色菜、创意菜、北京菜、家常菜、茶餐厅、小龙虾、素食、小吃快餐、面包甜点、面馆、大排档、西餐、云南菜、西北菜、意大利菜、泰国菜、越南菜、印度菜、墨西哥菜、西班牙菜、土耳其菜、希腊菜、巴西菜、徽菜、鲁菜、闽菜、豫菜、赣菜、鄂菜、桂菜、琼菜、贵菜、藏菜、地方特色、国际美食、融合菜、健康餐、快餐、甜品店、饮品店

可选价格区间（可选，如果内容中没有价格信息可以不填）：
人均50元以内、人均50至100、人均100至200、人均200至300、人均300以上

可选用餐场景（可选，可多选）：
早餐、午餐、晚餐、夜宵、下午茶、商务宴请、情侣约会、家庭聚餐、朋友聚会、生日聚会

可选餐厅特色（可选，可多选）：
网红餐厅、老字号、米其林、黑珍珠、必吃榜、人气餐厅、新店开业、连锁品牌、独立小店

可选服务类型（可选，可多选）：
外卖、堂食、外带、自助、套餐、单点

可选环境特色（可选，可多选）：
露天、包间、景观、主题餐厅、音乐餐厅、酒吧、无烟

可选特殊需求（可选，可多选）：
清真、无糖、低卡、儿童友好、宠物友好、无障碍、停车方便

可选时间特色（可选，可多选）：
24小时、深夜食堂、早市、夜市

请以JSON格式返回结果：
{{
    "cuisine": "菜系名称（必须从菜系列表中精确选择一个）",
    "price_range": "价格区间（如果无法确定可以不填）",
    "scenes": ["用餐场景1", "用餐场景2"]（可选，数组格式，可多选）,
    "features": ["餐厅特色1", "餐厅特色2"]（可选，数组格式，可多选）,
    "service_types": ["服务类型1"]（可选，数组格式，可多选）,
    "environment": ["环境特色1"]（可选，数组格式，可多选）,
    "special_needs": ["特殊需求1"]（可选，数组格式，可多选）,
    "time_features": ["时间特色1"]（可选，数组格式，可多选）
}}"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的美食分类专家，擅长根据内容判断菜系、价格区间、用餐场景、餐厅特色等多个维度。必须严格按照给定的分类列表进行选择。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 800,  # 增加token数量以支持多维度分类
                "temperature": 0.3,
                "stream": False
            }
            
            # 使用重试机制
            def make_request(timeout):
                return requests.post(url, json=payload, timeout=timeout)
            
            response = self._retry_request(make_request, BASE_TIMEOUT_CLASSIFY, "AI分类")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 解析JSON响应
                parsed = self._parse_json_response(content)
                if not parsed:
                    return None
                
                # 提取所有分类字段（支持多种字段名）
                cuisine = parsed.get('cuisine', '') or parsed.get('菜系', '') or parsed.get('cuisine_type', '')
                price_range = parsed.get('price_range', '') or parsed.get('价格区间', '') or parsed.get('price', '')
                scenes = parsed.get('scenes', []) or parsed.get('用餐场景', []) or parsed.get('scene', [])
                features = parsed.get('features', []) or parsed.get('餐厅特色', []) or parsed.get('feature', [])
                service_types = parsed.get('service_types', []) or parsed.get('服务类型', []) or parsed.get('service', [])
                environment = parsed.get('environment', []) or parsed.get('环境特色', []) or parsed.get('env', [])
                special_needs = parsed.get('special_needs', []) or parsed.get('特殊需求', []) or parsed.get('special', [])
                time_features = parsed.get('time_features', []) or parsed.get('时间特色', []) or parsed.get('time', [])
                
                # 映射到子类型ID（支持多维度分类）
                return self._map_to_type_cids(
                    cuisine, price_range, scenes, features, service_types, 
                    environment, special_needs, time_features
                )
            else:
                if response:
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
                "temperature": getattr(Config, 'LLM_TEMPERATURE', 0.7),
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 尝试解析JSON响应
                parsed = self._parse_json_response(content)
                if parsed:
                    paraphrased_title = parsed.get('title', title)
                    paraphrased_desc = parsed.get('description', description)
                    content_type = parsed.get('type', '生活')
                else:
                    # 如果无法解析JSON，尝试提取文本
                    paraphrased_title = title
                    paraphrased_desc = description
                    content_type = '生活'
                    
                    # 尝试从文本中提取信息
                    lines = content.strip().split('\n')
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
    
    def _is_restaurant(self, restaurant: dict) -> bool:
        """
        判断一个商家是否是餐厅
        
        Args:
            restaurant: 商家信息字典
            
        Returns:
            True表示是餐厅，False表示不是餐厅
        """
        name = restaurant.get('name', '').lower()
        description = restaurant.get('description', '').lower()
        
        # 非餐厅关键词列表
        non_restaurant_keywords = [
            '珠宝', '首饰', '金店', '银店', '钻石', '周大福', '周生生', '六福', '老凤祥',
            '服装', '服饰', '时装', '衣服', '鞋子', '包包', '配饰',
            '书店', '图书馆', '电影院', '影城', '影院',
            'ktv', '卡拉ok', '唱歌', '酒店', '宾馆', '旅馆', '民宿', '住宿',
            '商场', '购物中心', '百货', 'mall', '超市', '便利店', '小卖部',
            '药店', '药房', '美发', '理发', '美容', '美甲', 'spa',
            '银行', 'atm', '健身房', '运动', '健身',
            '医院', '诊所', '学校', '教育', '培训',
            '汽车', '4s店', '修车', '加油站', '博物馆', '展览馆',
            '游乐场', '公园', '网吧', '网咖'
        ]
        
        # 检查名称和描述中是否包含非餐厅关键词
        full_text = f"{name} {description}"
        for keyword in non_restaurant_keywords:
            if keyword in full_text:
                logger.debug(f"检测到非餐厅关键词 '{keyword}'，过滤商家: {name}")
                return False
        
        # 餐厅相关关键词
        restaurant_keywords = [
            '餐厅', '饭店', '餐馆', '酒家', '酒楼', '食府', '食肆',
            '美食', '小吃', '料理', '菜', '菜馆', '菜系',
            '火锅', '烧烤', '烤肉', '串串', '麻辣烫',
            '咖啡', '奶茶', '饮品', '茶', '甜品', '蛋糕', '面包',
            '早餐', '午餐', '晚餐', '夜宵',
            '川菜', '粤菜', '湘菜', '鲁菜', '苏菜', '浙菜', '徽菜', '闽菜',
            '日料', '韩料', '西餐', '中餐', '快餐', '简餐'
        ]
        
        # 如果包含餐厅关键词，则认为是餐厅
        for keyword in restaurant_keywords:
            if keyword in full_text:
                return True
        
        # 如果没有明确的餐厅关键词，但也没有非餐厅关键词，默认保留
        # 但如果没有明确的餐厅标识，且名称很短，可能不是餐厅
        if len(name) < 3:
            return False
        
        return True
    
    def _filter_non_restaurants(self, restaurants: list) -> list:
        """
        过滤掉非餐厅商家
        
        Args:
            restaurants: 商家列表
            
        Returns:
            过滤后的餐厅列表
        """
        filtered = []
        for restaurant in restaurants:
            # 确保restaurant是字典类型
            if not isinstance(restaurant, dict):
                logger.warning(f"跳过非字典类型的元素: {type(restaurant)}")
                continue
            
            if self._is_restaurant(restaurant):
                filtered.append(restaurant)
            else:
                logger.warning(f"过滤非餐厅商家: {restaurant.get('name', '未知')}")
        return filtered
    
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
            desc_limit = 3000
            desc_truncated = description[:desc_limit] if description else ""
            if description and len(description) > desc_limit:
                logger.info(f"描述过长（{len(description)}字符），截取前{desc_limit}字符进行提取")
            
            prompt = f"""请从以下小红书笔记中提取所有餐厅信息。

标题：{title}
描述：{desc_truncated}

要求：
1. **只提取餐厅、美食店、小吃店、饮品店、甜品店等提供食物和饮品的商家**
2. **严格排除以下非餐厅商家：珠宝店、服装店、书店、电影院、KTV、酒店（除非是酒店内的餐厅）、商场、超市、便利店、药店、美发店、美容院等**
3. 提取每个餐厅的名称、地址、人均价格、描述
4. 如果一个笔记只提到一个餐厅，也要提取出来
5. 如果笔记是美食攻略包含多个餐厅，要分别提取每个餐厅
6. 如果笔记中提到的商家不是餐厅（如购物、娱乐场所），请忽略，不要提取

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

如果笔记中没有明确的餐厅信息，**必须返回空数组 []**。不要返回任何说明文字，只返回JSON数组。"""

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
                "max_tokens": 4000,
                "temperature": 0.3,
                "stream": False
            }
            
            # 使用重试机制
            def make_request(timeout):
                return requests.post(url, json=payload, timeout=timeout)
            
            response = self._retry_request(make_request, BASE_TIMEOUT_EXTRACT, "AI提取餐厅信息")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                logger.debug(f"AI提取餐厅原始响应（前500字符）: {content[:500]}")
                
                # 检查是否包含说明性文字（表示没有餐厅信息）
                no_restaurant_indicators = [
                    '没有明确提到', '无法提取', '没有找到', '未找到', '无法找到',
                    '没有餐厅', '没有符合条件的', '无法提取符合条件的',
                    '笔记内容中没有', '内容中没有明确提到'
                ]
                
                content_lower = content.lower()
                has_no_restaurant_text = any(indicator in content_lower for indicator in no_restaurant_indicators)
                has_json_array = '[' in content and ']' in content
                
                if has_no_restaurant_text and not has_json_array:
                    logger.info("AI返回说明性文字，表示没有餐厅信息，返回空数组")
                    return []
                
                # 解析JSON响应
                parsed = self._parse_json_response(content, is_array=True)
                if not parsed:
                    return []
                
                # 确保parsed是列表或字典
                if isinstance(parsed, list):
                    # 过滤掉非字典元素和非餐厅商家
                    valid_restaurants = []
                    for item in parsed:
                        if isinstance(item, dict):
                            valid_restaurants.append(item)
                        else:
                            logger.warning(f"跳过非字典类型的元素: {type(item)}")
                    
                    # 过滤掉非餐厅商家
                    restaurants = self._filter_non_restaurants(valid_restaurants)
                    logger.info(f"成功提取到 {len(restaurants)} 个餐厅（过滤后）")
                    return restaurants
                elif isinstance(parsed, dict):
                    # 单个餐厅也需要过滤
                    if self._is_restaurant(parsed):
                        logger.info(f"成功提取到1个餐厅（单个对象格式）")
                        return [parsed]
                    else:
                        logger.warning(f"提取的商家不是餐厅，已过滤: {parsed.get('name', '未知')}")
                        return []
                else:
                    logger.warning(f"AI返回了非预期的数据类型: {type(parsed)}")
                    return []
            else:
                error_msg = f"AI提取餐厅API调用失败: {response.status_code if response else '无响应'}"
                if response:
                    try:
                        error_detail = response.text[:300] if response.text else "无错误详情"
                        error_msg += f" - {error_detail}"
                    except:
                        pass
                logger.warning(error_msg)
                return []
                
        except Exception as e:
            logger.warning(f"AI提取餐厅失败: {e}")
            return []
    
    def search_restaurant_online(self, restaurant_name: str, context: str = "") -> Dict[str, str]:
        """
        联网搜索餐厅信息（如果AI提取失败或信息不完整）
        
        Args:
            restaurant_name: 餐厅名称
            context: 上下文信息（原笔记标题或描述）
            
        Returns:
            餐厅信息字典，包含 name, address, price_range, description
        """
        if not restaurant_name or restaurant_name.strip() == "":
            return {}
        
        logger.info(f"🔍 联网搜索餐厅信息: {restaurant_name}")
        
        try:
            search_query = f"{restaurant_name} 餐厅"
            if context:
                search_query += f" {context[:100]}"
            
            prompt = f"""请联网搜索以下餐厅的详细信息：

餐厅名称：{restaurant_name}
搜索关键词：{search_query}

请搜索并返回该餐厅的以下信息：
1. 餐厅全名（如果有多个名称，使用最常用的）
2. 详细地址（包括城市、区、街道、门牌号）
3. 人均价格范围（如果有）
4. 餐厅特色和描述（如果有）

请以JSON格式返回结果：
{{
    "name": "餐厅名称",
    "address": "详细地址",
    "price_range": "人均价格（如果有）",
    "description": "餐厅特色和描述"
}}

如果搜索不到相关信息，返回空JSON对象 {{}}。"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的美食信息搜索专家，能够通过联网搜索获取餐厅的详细信息。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 800,
                "temperature": 0.3,
                "stream": False
            }
            
            try:
                response = requests.post(url, json=payload, timeout=120)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    
                    # 解析JSON响应
                    parsed = self._parse_json_response(content)
                    if isinstance(parsed, dict) and parsed.get('name'):
                        logger.info(f"✅ 联网搜索成功获取餐厅信息: {parsed.get('name')}")
                        return parsed
                    else:
                        logger.warning(f"⚠️ 联网搜索返回的信息不完整")
                        return {}
                else:
                    logger.warning(f"⚠️ 联网搜索API调用失败: {response.status_code}")
                    return {}
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ 联网搜索超时")
                return {}
            except Exception as e:
                logger.warning(f"⚠️ 联网搜索异常: {e}")
                return {}
                
        except Exception as e:
            logger.warning(f"⚠️ 联网搜索餐厅信息失败: {e}")
            return {}
    
    def _clean_description(self, description: str, restaurant_address: str = "", restaurant_price: str = "") -> str:
        """
        清理描述中的地址和价格信息
        
        Args:
            description: 原始描述
            restaurant_address: 餐厅地址（用于移除）
            restaurant_price: 餐厅价格（用于移除）
            
        Returns:
            清理后的描述
        """
        if not description:
            return description
        
        # 移除地址相关的内容
        if restaurant_address:
            address_patterns = [
                f"📍地址：{restaurant_address}",
                f"地址：{restaurant_address}",
                f"📍{restaurant_address}",
                restaurant_address
            ]
            for pattern in address_patterns:
                description = description.replace(pattern, "").strip()
        
        # 移除价格相关的内容
        if restaurant_price:
            price_patterns = [
                f"💰人均：{restaurant_price}",
                f"人均：{restaurant_price}",
                f"💰{restaurant_price}",
                f"人均{restaurant_price}"
            ]
            for pattern in price_patterns:
                description = description.replace(pattern, "").strip()
        
        # 清理多余的换行和空格
        description = "\n".join(line.strip() for line in description.split("\n") if line.strip())
        
        return description
    
    def generate_comments(self, restaurant_name: str, restaurant_content: str, comment_count: int = None) -> List[str]:
        """
        为餐厅生成评论内容列表
        
        Args:
            restaurant_name: 餐厅名称
            restaurant_content: 餐厅内容描述
            comment_count: 评论数量（如果为None，则随机生成35-75条）
            
        Returns:
            评论内容列表（字符串列表）
        """
        if comment_count is None:
            comment_count = random.randint(35, 75)
        
        logger.info(f"为餐厅 {restaurant_name} 生成 {comment_count} 条评论...")
        
        # 生成评论提示词
        prompt = f"""请为以下餐厅/美食内容生成{comment_count}条真实、自然的大众点评风格评论。

餐厅名称：{restaurant_name}
内容：{restaurant_content[:500]}

要求：
1. 评论要真实自然，符合大众点评的风格
2. 评论内容要多样化，包括：口味评价、环境评价、服务评价、价格评价、推荐理由等
3. 每条评论长度控制在20-100字之间
4. 评论要有真实感，不要过于夸张
5. 返回JSON格式，格式如下：
{{
    "comments": [
        {{"content": "评论内容1"}},
        {{"content": "评论内容2"}},
        ...
    ]
}}

只返回JSON，不要其他内容。"""
        
        try:
            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的美食评论生成专家，擅长生成真实自然的大众点评风格评论。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
                "stream": False
            }
            
            # 使用重试机制
            def make_request(timeout):
                return requests.post(url, json=payload, timeout=timeout)
            
            response = self._retry_request(make_request, BASE_TIMEOUT_COMMENTS, "生成评论")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 解析JSON响应
                parsed = self._parse_json_response(content)
                if not parsed:
                    logger.warning("无法解析评论生成响应")
                    return []
                
                # 提取评论列表
                comment_list = []
                if isinstance(parsed, dict) and 'comments' in parsed:
                    comment_list = parsed['comments']
                elif isinstance(parsed, list):
                    comment_list = parsed
                else:
                    logger.warning(f"评论响应格式不正确: {type(parsed)}")
                    return []
                
                # 提取评论内容
                comments = []
                for comment_item in comment_list:
                    if isinstance(comment_item, dict):
                        content = comment_item.get('content', '')
                    elif isinstance(comment_item, str):
                        content = comment_item
                    else:
                        continue
                    
                    if content and len(content.strip()) >= 5:
                        comments.append(content.strip())
                
                logger.info(f"成功生成 {len(comments)} 条评论")
                return comments
            else:
                logger.warning(f"生成评论API调用失败: {response.status_code if response else '无响应'}")
                return []
                
        except Exception as e:
            logger.warning(f"生成评论失败: {e}")
            return []
    
    def insert_comments_to_db(self, tweet_id: int, comments: List[str]) -> int:
        """
        将评论插入到数据库
        
        Args:
            tweet_id: 推文ID
            comments: 评论内容列表（字符串列表）
            
        Returns:
            成功插入的数量
        """
        if not comments:
            return 0
        
        try:
            from base.database import db
            from sqlalchemy import text
            
            success_count = 0
            for comment_content in comments:
                try:
                    # 生成随机用户名
                    username = get_random_username()
                    
                    sql = """
                        INSERT INTO tweets_evaluate (tweets_id, evaluate_user, evaluate_content)
                        VALUES (:tweets_id, :evaluate_user, :evaluate_content)
                    """
                    params = {
                        'tweets_id': tweet_id,
                        'evaluate_user': username,
                        'evaluate_content': comment_content
                    }
                    
                    with db.engine.connect() as conn:
                        conn.execute(text(sql), params)
                        conn.commit()
                    
                    success_count += 1
                except Exception as e:
                    logger.error(f"插入评论失败: {str(e)}")
                    logger.debug(f"评论内容: {comment_content}")
            
            logger.info(f"成功插入 {success_count}/{len(comments)} 条评论到数据库")
            return success_count
            
        except Exception as e:
            logger.error(f"批量插入评论失败: {str(e)}", exc_info=True)
            return 0
    
    def paraphrase_restaurant(self, restaurant_info: dict, original_title: str = "", original_description: str = "", comments: list = None, tweet_id: int = None, auto_generate_comments: bool = True) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
        """
        对单个餐厅进行转述和分类，结合小红书内容和大众点评评论
        
        Args:
            restaurant_info: 餐厅信息字典，包含 name, address, price_range, description
            original_title: 原始笔记标题（可选）
            original_description: 原始笔记完整描述（可选）
            comments: 大众点评评论列表（可选，如果为None且auto_generate_comments=True，则自动生成）
            tweet_id: 推文ID（如果提供且auto_generate_comments=True，评论会自动插入数据库）
            auto_generate_comments: 是否自动生成评论（默认True）
            
        Returns:
            (转述后的标题, 转述后的描述, 子类型ID, 生成的评论列表)
        """
        restaurant_name = restaurant_info.get('name', '')
        restaurant_address = restaurant_info.get('address', '')
        restaurant_price = restaurant_info.get('price_range', '')
        restaurant_desc = restaurant_info.get('description', '')
        
        if not restaurant_name:
            return None, None, None, []
        
        # 在请求前检查模型是否可用
        is_available, error_msg = self.check_model_available()
        if not is_available:
            logger.error(f"模型不可用: {error_msg}")
            logger.error("程序终止：AI模型不可用")
            raise Exception(f"AI模型不可用: {error_msg}")
        
        # 如果没有传入评论且需要自动生成，则生成评论
        generated_comments = []
        if comments is None and auto_generate_comments:
            # 生成评论时，优先使用原始笔记描述，其次使用餐厅描述，最后使用标题
            comment_content = original_description or restaurant_desc or original_title
            # 生成评论
            generated_comments = self.generate_comments(
                restaurant_name=restaurant_name,
                restaurant_content=comment_content
            )
            # 如果提供了tweet_id，将评论插入数据库
            if generated_comments and tweet_id:
                self.insert_comments_to_db(tweet_id, generated_comments)
            # 使用生成的评论
            comments = generated_comments
        elif comments is None:
            comments = []
        
        try:
            # 构建评论部分（如果有）
            comments_text = ""
            if comments and len(comments) > 0:
                comments_text = "\n\n大众点评用户评论：\n"
                for i, comment in enumerate(comments[:5], 1):  # 最多使用前5条评论
                    comments_text += f"{i}. {comment}\n"
            
            # 构建转述提示词
            prompt = f"""请将以下餐厅信息改写为原创的小红书风格推荐文案。

餐厅名称：{restaurant_name}
餐厅描述：{restaurant_desc[:300] if restaurant_desc else '无'}
{comments_text if comments_text else ''}

小红书原始标题：{original_title[:100] if original_title else '无'}
小红书原始内容：{original_description[:500] if original_description else '无'}

要求：
1. 生成一个吸引人的标题（不超过50字）
2. 生成详细的推荐描述（300-500字），只描述餐厅的特色、菜品、口味、环境等，不要包含地址和价格信息
3. 保持原意但用不同的表达方式
4. 使用小红书风格的文案（自然、生动、有吸引力）
5. 如果提供了原始笔记内容，请结合原始内容、餐厅描述和大众点评评论，生成更丰富、更真实的推荐文案
6. 评论内容可以作为参考，但不要直接复制，要转述成自己的语言
7. 保持小红书笔记的原创性和真实性
8. 重要：描述中不要包含地址和价格信息，这些信息会单独存储

请以JSON格式返回结果：
{{
    "title": "改写后的标题",
    "description": "改写后的详细描述（300-500字，不包含地址和价格）"
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
                "max_tokens": 1200,  # 增加到1200以支持300-500字的完整内容
                "temperature": 0.7,
                "stream": False
            }
            
            # 使用重试机制
            def make_request(timeout):
                return requests.post(url, json=payload, timeout=timeout)
            
            response = self._retry_request(make_request, BASE_TIMEOUT_PARAPHRASE, "AI转述餐厅")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 解析JSON响应
                parsed = self._parse_json_response(content)
                if parsed:
                    paraphrased_title = parsed.get('title', '') or parsed.get('标题', '') or parsed.get('title_text', '') or restaurant_name
                    paraphrased_desc = parsed.get('description', '') or parsed.get('描述', '') or parsed.get('desc', '') or parsed.get('content', '') or restaurant_desc
                    
                    # 如果仍然为空，使用原始值
                    if not paraphrased_title:
                        paraphrased_title = restaurant_name
                    if not paraphrased_desc:
                        paraphrased_desc = restaurant_desc
                    
                    # 清理转述描述中的地址和价格信息
                    paraphrased_desc = self._clean_description(paraphrased_desc, restaurant_address, restaurant_price)
                    
                    # 分类并获取子类型ID
                    type_cid = self.classify_to_type_cid(paraphrased_title, paraphrased_desc)
                    
                    # 补充价格区间ID
                    type_cid = self._supplement_price_cid(type_cid, restaurant_price)
                    
                    return paraphrased_title, paraphrased_desc, type_cid, generated_comments
                else:
                    # JSON解析失败，尝试从文本中提取信息
                    logger.warning(f"无法解析AI转述结果（JSON格式错误）")
                    logger.debug(f"原始内容前500字符: {content[:500]}")
                    
                    # 尝试从文本中提取标题和描述
                    final_title = restaurant_name
                    final_desc = restaurant_desc
                    
                    # 尝试查找标题标记
                    title_markers = ['标题', 'title', 'Title']
                    desc_markers = ['描述', 'description', 'Description', '内容', 'content']
                    
                    for marker in title_markers:
                        if marker in content:
                            marker_idx = content.find(marker)
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
                            marker_idx = content.find(marker)
                            if ':' in content[marker_idx:marker_idx+50]:
                                desc_start = content.find(':', marker_idx) + 1
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
                    
                    # 清理描述
                    final_desc = self._clean_description(final_desc, restaurant_address, restaurant_price)
                    
                    # 分类并获取子类型ID
                    type_cid = self.classify_to_type_cid(final_title, final_desc)
                    type_cid = self._supplement_price_cid(type_cid, restaurant_price)
                    
                    return final_title, final_desc, type_cid, generated_comments
            else:
                error_msg = f"AI转述餐厅API调用失败: {response.status_code if response else '无响应'}"
                if response:
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
                
                return None, None, None, generated_comments
                
        except requests.exceptions.Timeout:
            logger.error("AI转述餐厅请求超时")
            logger.error("建议：检查Ollama服务状态，或使用更小的模型")
            return None, None, None, generated_comments
        except Exception as e:
            logger.warning(f"AI转述餐厅失败: {e}")
            return None, None, None, generated_comments


# 全局实例
_paraphraser = None

def get_ai_paraphraser() -> AIParaphraser:
    """获取AI转述器单例"""
    global _paraphraser
    if _paraphraser is None:
        _paraphraser = AIParaphraser()
    return _paraphraser
