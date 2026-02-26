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
import os
from typing import Dict, Optional, Tuple, List, Callable
from urllib.parse import quote

from base.config import Config
from base.utils import get_random_username

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    HAS_DRISSION = True
except ImportError:
    HAS_DRISSION = False

logger = logging.getLogger(__name__)

# ==================== 常量配置 ====================

# 重试配置
MAX_RETRIES = 10
RETRY_DELAYS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
BASE_TIMEOUT_CLASSIFY = 90
BASE_TIMEOUT_EXTRACT = 240
BASE_TIMEOUT_PARAPHRASE = 180  # 增加超时时间以支持联网搜索
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
        self.api_key = Config.LLM_API_KEY
        self.model = Config.LLM_MODEL
        self.max_tokens = Config.LLM_MAX_TOKENS
        self._last_check_time = 0
        self._model_available_cache = None
        self._cache_duration = MODEL_CHECK_CACHE_DURATION
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
            # 如果配置了API Key，假设是远程API，跳过Ollama特定检查
            if self.api_key:
                try:
                    test_url = f"{self.api_base}/chat/completions"
                    test_payload = {
                        "model": self.model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 5,
                        "stream": False
                    }
                    # 32b 模型首次加载需要更长时间，增加超时时间
                    timeout_val = 60
                    test_response = requests.post(test_url, json=test_payload, headers=self._get_headers(), timeout=timeout_val)
                    
                    if test_response.status_code == 200:
                        result = (True, "模型可用")
                        self._update_cache(result)
                        return result
                    else:
                        result = (False, f"模型测试失败 (HTTP {test_response.status_code}): {test_response.text[:200]}")
                        self._update_cache(result)
                        return result
                except Exception as e:
                    result = (False, f"模型测试异常: {e}")
                    self._update_cache(result)
                    return result

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
                    logger.info(f"当前配置使用的模型: {self.model}") # 打印当前配置的模型
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
                # 32b 模型首次加载需要更长时间，增加超时时间
                timeout_val = 120 if '32b' in self.model.lower() else 30
                test_response = requests.post(test_url, json=test_payload, timeout=timeout_val)
                
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
            "粤菜": [12], "德国菜": [13], "日本料理": [14], "日式料理": [14], "法国菜": [15], "韩国料理": [16],
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
        # 注意：绝不能在字符串值内部做这种替换（例如 "11:00" 会被破坏）。
        # 因此仅对对象的“键”进行处理：出现在 { 或 , 之后的未加引号 key:
        json_str = re.sub(r'(?<=\{)\s*([A-Za-z_]\w*)\s*:', r'"\1":', json_str)
        json_str = re.sub(r'(?<=,)\s*([A-Za-z_]\w*)\s*:', r'"\1":', json_str)
        
        # 3. 修复单引号为双引号
        json_str = json_str.replace("'", '"')
        
        # 4. 修复末尾多余的逗号（在数组或对象中）
        # 移除数组末尾的逗号：], }] 或 ], ]]
        json_str = re.sub(r',\s*\]', ']', json_str)
        json_str = re.sub(r',\s*\}', '}', json_str)
        
        # 5. 修复缺失的逗号（在对象属性之间）
        # 修复 "key": value 后面缺少逗号的情况
        json_str = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', json_str)
        json_str = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', json_str)
        
        # 6. 修复值后面缺少逗号的情况（更精确的匹配）
        # 匹配 "key": "value" 后面缺少逗号，但后面还有另一个键的情况
        json_str = re.sub(r'("\s*")\s*\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', json_str)
        
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
            
            # 如果解析失败，尝试手动修复缺失的逗号或多余的逗号
            if "Expecting ','" in error_msg or "delimiter" in error_msg.lower() or "trailing comma" in error_msg.lower():
                # 更激进的修复
                fixed_content = json_content
                
                # 修复末尾多余的逗号
                fixed_content = re.sub(r',\s*\]', ']', fixed_content)
                fixed_content = re.sub(r',\s*\}', '}', fixed_content)
                
                # 修复缺失的逗号（在对象属性之间）
                fixed_content = re.sub(r'("\s*)\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', fixed_content)
                fixed_content = re.sub(r'("\s*)\n\s*"', r'\1,\n    "', fixed_content)
                
                # 修复值后面缺少逗号的情况
                # 匹配 "key": "value" 后面缺少逗号，但后面还有另一个键
                fixed_content = re.sub(r'("\s*")\s*\n\s*"([^"]+)"\s*:', r'\1,\n    "\2":', fixed_content)
                
                # 尝试在错误位置附近插入逗号（更智能的修复）
                if "line" in error_msg and "column" in error_msg:
                    try:
                        # 提取行号和列号
                        line_match = re.search(r'line (\d+)', error_msg)
                        col_match = re.search(r'column (\d+)', error_msg)
                        if line_match and col_match:
                            line_num = int(line_match.group(1))
                            col_num = int(col_match.group(1))
                            lines = fixed_content.split('\n')
                            if line_num <= len(lines):
                                line = lines[line_num - 1]
                                # 在指定列位置尝试插入逗号（如果缺失）
                                if col_num < len(line) and line[col_num-1] not in [',', ':', '{', '[', '}', ']']:
                                    # 尝试在当前位置前插入逗号
                                    if col_num > 1 and line[col_num-2] not in [',', ':', '{', '[']:
                                        new_line = line[:col_num-1] + ',' + line[col_num-1:]
                                        lines[line_num - 1] = new_line
                                        fixed_content = '\n'.join(lines)
                    except Exception:
                        pass
                
                try:
                    parsed = json.loads(fixed_content)
                    logger.info("通过修复JSON格式成功解析（修复了逗号问题）")
                    return parsed
                except json.JSONDecodeError as e2:
                    logger.debug(f"修复后仍然无法解析: {e2}")
                    # 如果还是失败，尝试使用json5库（如果可用）
                    try:
                        import json5
                        parsed = json5.loads(fixed_content)
                        logger.info("通过json5库成功解析JSON")
                        return parsed
                    except ImportError:
                        pass
                    except Exception:
                        pass
            
            # 最后尝试：使用更宽松的JSON解析库
            try:
                import json5
                parsed = json5.loads(json_content)
                logger.info("通过json5库成功解析JSON（容错模式）")
                return parsed
            except ImportError:
                pass
            except Exception:
                pass
            
            logger.warning(f"无法解析JSON响应: {parse_error}")
            logger.info(f"原始内容前500字符: {content[:500]}")
            logger.info(f"清理后的内容前500字符: {json_content[:500]}")
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
                    # 尝试打印错误详情
                    try:
                        logger.warning(f"错误详情: {response.text[:500]}")
                    except:
                        pass
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"{operation_name}最终失败: HTTP {response.status_code}")
                    try:
                        logger.error(f"最终错误详情: {response.text[:500]}")
                    except:
                        pass
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
            logger.warning(f"菜系 '{cuisine}' 不在映射表中，尝试使用fallback机制")
            # Fallback: 尝试模糊匹配或使用通用分类
            # 1. 尝试匹配包含关键词的菜系
            matched = False
            for key in mapping.keys():
                if cuisine in key or key in cuisine:
                    logger.info(f"通过模糊匹配找到相似菜系: '{key}' -> {mapping[key]}")
                    cid_list.extend(mapping[key])
                    matched = True
                    break
            
            # 2. 如果还是没匹配到，使用通用分类（特色菜或国际美食）
            if not matched:
                logger.warning(f"无法匹配菜系 '{cuisine}'，使用通用分类作为fallback")
                # 使用"特色菜"作为fallback（ID: 27）
                if "特色菜" in mapping:
                    cid_list.extend(mapping["特色菜"])
                else:
                    # 如果连特色菜都没有，使用第一个可用的菜系ID
                    logger.error(f"无法找到任何可用的菜系映射，菜系: {cuisine}")
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
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
            
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
            
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=60)
            
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
    
    def get_parent_type_id(self, restaurant_info: dict) -> int:
        """
        根据场所信息动态选择父类型ID
        
        Args:
            restaurant_info: 场所信息字典，包含 name, description 等
            
        Returns:
            父类型ID（默认返回5-美食）
        """
        name = (restaurant_info.get('name', '') or '').lower()
        description = (restaurant_info.get('description', '') or '').lower()
        full_text = f"{name} {description}"
        
        # 酒吧/夜生活场所关键词
        bar_keywords = ['酒吧', 'bar', 'pub', '夜店', 'club', 'lounge', '精酿', '威士忌', '鸡尾酒', '啤酒屋', 'livehouse']
        # 咖啡厅关键词
        cafe_keywords = ['咖啡', '咖啡厅', 'cafe', 'coffee', '星巴克', '瑞幸']
        # 甜品店关键词
        dessert_keywords = ['甜品', '蛋糕', '面包', '甜点', 'dessert', 'bakery', '烘焙']
        # 饮品店关键词
        drink_keywords = ['奶茶', '饮品', '茶饮', '果汁', 'bubble tea', 'tea']
        
        # 检查场所类型并返回对应的父类型ID
        # 优先使用配置中的默认父类型ID
        from base.config import Config
        config = Config()
        default_type_pid = config.DEFAULT_TYPE_PID or 5
        
        # 根据场所类型选择父类型ID
        # 如果数据库中有其他父类型（如酒吧、咖啡厅等），可以在这里扩展
        # 目前所有餐饮相关场所都使用同一个父类型（美食）
        # 如果需要区分，可以在数据库中创建新的父类型，然后在这里返回对应的ID
        
        # 示例：如果数据库中有酒吧类型（假设ID=6），可以这样判断：
        # for keyword in bar_keywords:
        #     if keyword in full_text:
        #         return 6  # 酒吧类型
        
        # 目前统一返回默认类型（通常是5-美食）
        return default_type_pid
    
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
        
        # 餐饮及夜生活场所关键词
        restaurant_keywords = [
            '餐厅', '饭店', '餐馆', '酒家', '酒楼', '食府', '食肆',
            '美食', '小吃', '料理', '菜', '菜馆', '菜系',
            '火锅', '烧烤', '烤肉', '串串', '麻辣烫',
            '咖啡', '奶茶', '饮品', '茶', '甜品', '蛋糕', '面包',
            '早餐', '午餐', '晚餐', '夜宵',
            '川菜', '粤菜', '湘菜', '鲁菜', '苏菜', '浙菜', '徽菜', '闽菜',
            '日料', '韩料', '西餐', '中餐', '快餐', '简餐',
            '酒吧', 'bar', 'pub', '夜店', '夜生活', 'club', 'lounge',
            '精酿', '威士忌', '鸡尾酒', '啤酒屋', 'livehouse', 'Live House'
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
    
    def _extract_partial_comments(self, content: str) -> List[str]:
        """
        从被截断的JSON中提取部分评论
        
        Args:
            content: AI返回的内容（可能被截断）
            
        Returns:
            提取到的评论列表
        """
        comments = []
        try:
            logger.debug(f"开始提取部分评论，内容长度: {len(content)}")
            
            # 尝试找到 "comments" 数组的开始位置
            comments_start = content.find('"comments"')
            if comments_start == -1:
                comments_start = content.find("'comments'")
            if comments_start == -1:
                # 如果没有找到 "comments"，尝试直接找数组
                logger.debug("未找到 'comments' 键，尝试直接查找数组")
                array_start = content.find('[')
                if array_start != -1:
                    # 直接尝试解析数组
                    try:
                        import json
                        # 尝试找到最后一个完整的对象
                        last_brace = content.rfind('}')
                        if last_brace > array_start:
                            partial_array = content[array_start:last_brace + 1] + ']'
                            parsed_array = json.loads(partial_array)
                            if isinstance(parsed_array, list):
                                for item in parsed_array:
                                    if isinstance(item, dict) and 'content' in item:
                                        comment_text = item['content'].strip()
                                        if comment_text and len(comment_text) >= 5:
                                            comments.append(comment_text)
                                    elif isinstance(item, str) and len(item.strip()) >= 5:
                                        comments.append(item.strip())
                        if comments:
                            logger.info(f"通过直接解析数组提取到 {len(comments)} 条评论")
                            return comments
                    except Exception as e:
                        logger.debug(f"直接解析数组失败: {e}")
                return []
            
            # 找到数组开始标记 [
            array_start = content.find('[', comments_start)
            if array_start == -1:
                logger.debug("未找到数组开始标记 [")
                return []
            
            # 从数组开始位置提取所有完整的评论对象
            # 使用正则表达式匹配 {"content": "..."} 模式，支持转义字符
            import re
            # 改进的正则表达式，能处理包含转义字符的字符串
            pattern = r'\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"\}'
            matches = re.findall(pattern, content[array_start:])
            
            for match in matches:
                comment_text = match.strip()
                # 处理转义字符
                comment_text = comment_text.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                if comment_text and len(comment_text) >= 5:
                    comments.append(comment_text)
            
            # 如果正则没匹配到，尝试更宽松的模式
            if not comments:
                # 手动查找所有 "content": "..." 模式，支持多行和转义
                content_pattern = r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"'
                content_matches = re.findall(content_pattern, content)
                for match in content_matches:
                    comment_text = match.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
                    if comment_text and len(comment_text) >= 5:
                        comments.append(comment_text)
            
            # 如果还是没找到，尝试逐字符解析（处理被截断的情况）
            if not comments:
                # 找到所有 {"content": 的位置，然后尝试提取到下一个 "} 或截断位置
                import json
                try:
                    # 尝试修复被截断的JSON
                    # 找到最后一个完整的评论对象
                    last_complete = content.rfind('"}')
                    if last_complete > array_start:
                        # 尝试解析到最后一个完整对象
                        partial_json = content[array_start:last_complete + 2] + ']'
                        # 尝试补全JSON结构
                        if not partial_json.strip().endswith(']'):
                            partial_json = partial_json.rstrip(',') + ']'
                        # 尝试解析
                        try:
                            parsed = json.loads('{"comments":' + partial_json + '}')
                            if isinstance(parsed, dict) and 'comments' in parsed:
                                for item in parsed['comments']:
                                    if isinstance(item, dict) and 'content' in item:
                                        comment_text = item['content'].strip()
                                        if comment_text and len(comment_text) >= 5:
                                            comments.append(comment_text)
                        except:
                            pass
                except:
                    pass
            
        except Exception as e:
            logger.debug(f"提取部分评论失败: {e}")
        
        return comments
    
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
        从笔记内容中提取餐饮/酒吧/夜生活场所信息，返回列表
        
        Args:
            title: 标题
            description: 描述
            
        Returns:
            场所列表，每个场所包含：name, address, price_range, description, images
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
            # 构建提取场所的提示词
            # 增加描述长度限制，确保能提取到所有餐厅
            desc_limit = 5000  # 从3000增加到5000，减少截断导致遗漏
            desc_truncated = description[:desc_limit] if description else ""
            if description and len(description) > desc_limit:
                logger.warning(f"⚠️  描述过长（{len(description)}字符），截取前{desc_limit}字符进行提取，可能遗漏部分餐厅信息")
            
            prompt = f"""请从以下小红书笔记中提取**所有**真实的线下消费场所（餐厅、酒吧、夜生活/娱乐、咖啡厅、甜品店等）信息。

标题：{title}
描述：{desc_truncated}

**重要要求：**
1. **必须提取笔记中提到的所有消费场所，不要遗漏任何一个**
2. **如果笔记是攻略类、榜单类、合集类内容，必须将每个提到的餐厅/酒吧/咖啡厅都单独提取出来**
3. **重点提取餐饮、酒吧、夜生活、咖啡厅、甜品店、饮品店等真实消费场所**
4. **严格排除以下非消费场所：珠宝店、服装/鞋包、书店、电影院、KTV（纯娱乐场所）、酒店住宿（除非笔记强调酒店内的餐饮或酒吧）、商场、超市、便利店、药店、美发店、美容院等**
5. 提取每个场所的名称、地址、人均价格/消费水平、描述
6. **即使笔记提到多个场所，也必须全部提取，不要只提取第一个或前几个**
7. 如果笔记中提到的地点不是消费场所（如景点/广场/纯活动），请忽略

**示例场景：**
- 如果笔记说"推荐3家餐厅：A餐厅、B餐厅、C餐厅"，必须提取3个
- 如果笔记是"上海酒吧红黑榜"，必须提取红榜和黑榜中的所有酒吧
- 如果笔记是"探店合集"，必须提取所有提到的餐厅

请以JSON数组格式返回结果：
[
    {{
        "name": "场所名称",
        "address": "场所地址（如果有）",
        "price_range": "人均价格（如果有，如：96元、人均100至200）",
        "description": "该场所的描述和推荐理由"
    }},
    ...
]

**重要：必须返回所有找到的场所，不要遗漏。如果笔记中没有明确的消费场所信息，返回空数组 []**。不要返回任何说明文字，只返回JSON数组。"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的本地生活信息提取专家，擅长从小红书笔记中提取餐饮、酒吧和夜生活场所的信息。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 8000,  # 增加token限制，确保能返回所有餐厅
                "temperature": 0.3,
                "stream": False
            }
            
            # 使用重试机制
            def make_request(timeout):
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
            
            response = self._retry_request(make_request, BASE_TIMEOUT_EXTRACT, "AI提取场所信息")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                logger.debug(f"AI提取场所原始响应（前500字符）: {content[:500]}")
                
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
                    logger.info("AI返回说明性文字，表示没有场所信息，返回空数组")
                    return []
                
                # 解析JSON响应
                parsed = self._parse_json_response(content, is_array=True)
                if not parsed:
                    return []
                
                # 确保parsed是列表或字典
                if isinstance(parsed, list):
                    # 过滤掉非字典元素和非目标商家
                    valid_restaurants = []
                    for item in parsed:
                        if isinstance(item, dict):
                            valid_restaurants.append(item)
                        else:
                            logger.warning(f"跳过非字典类型的元素: {type(item)}")
                    
                    # 过滤掉非餐饮/夜生活场所
                    restaurants = self._filter_non_restaurants(valid_restaurants)
                    logger.info(f"✅ 成功提取到 {len(restaurants)} 个场所（过滤后）")
                    if restaurants:
                        logger.info(f"提取到的场所列表：")
                        for idx, r in enumerate(restaurants, 1):
                            logger.info(f"  {idx}. {r.get('name', '未知')}")
                    return restaurants
                elif isinstance(parsed, dict):
                    # 单个场所也需要过滤
                    if self._is_restaurant(parsed):
                        logger.info(f"✅ 成功提取到1个场所（单个对象格式）: {parsed.get('name', '未知')}")
                        return [parsed]
                    else:
                        logger.warning(f"提取的商家不是目标场所，已过滤: {parsed.get('name', '未知')}")
                        return []
                else:
                    logger.warning(f"AI返回了非预期的数据类型: {type(parsed)}")
                    return []
            else:
                error_msg = f"AI提取场所API调用失败: {response.status_code if response else '无响应'}"
                if response:
                    try:
                        error_detail = response.text[:300] if response.text else "无错误详情"
                        error_msg += f" - {error_detail}"
                    except:
                        pass
                logger.warning(error_msg)
                return []
                
        except Exception as e:
            logger.warning(f"AI提取场所失败: {e}")
            return []
    
    def _search_online_real(self, keyword: str, context: str = "") -> Optional[Dict[str, str]]:
        """
        使用 DrissionPage (如果可用) 进行真实的联网搜索
        
        Args:
            keyword: 搜索关键词
            context: 上下文（辅助搜索）
            
        Returns:
            包含描述信息的字典，如果失败返回None
        """
        if not HAS_DRISSION:
            logger.warning("未安装 DrissionPage，无法进行真实联网搜索")
            return None
            
        page = None
        try:
            co = ChromiumOptions()
            co.headless(True)  # 无头模式
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-dev-shm-usage')
            
            # 尝试自动查找浏览器路径
            try:
                chrome_paths = [
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
                    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
                ]
                for chrome_path in chrome_paths:
                    if os.path.exists(chrome_path):
                        co.set_browser_path(chrome_path)
                        break
            except:
                pass
            
            page = ChromiumPage(co)
            
            # 搜索查询
            search_query = f"{keyword} 餐厅 评价 口碑"
            if context:
                # 仅仅使用关键字作为上下文，不包含地址信息，如果context包含地址则不添加
                # 这里简单地不使用context，因为用户要求不包含地址
                # 或者如果context不是地址才添加
                pass
                
            # 使用 Google 搜索
            url = f"https://www.google.com/search?q={quote(search_query)}"
            logger.info(f"正在进行联网搜索(Google): {search_query} ({url})")
            
            page.get(url)
            page.wait.load_start()
            time.sleep(random.uniform(2, 4))
            
            # 提取搜索结果
            results = []
            
            # 尝试提取主要内容
            # Google 的结果项通常在 div.g
            items = page.eles('css:div.g')
            for item in items: # 遍历结果
                try:
                    title_ele = item.ele('tag:h3')
                    if not title_ele:
                        continue
                    title = title_ele.text
                    
                    # 尝试获取摘要，Google摘要结构经常变，直接获取整个文本并清理
                    full_text = item.text
                    snippet = full_text.replace(title, "").replace("\n", " ").strip()
                    # 简单的截断
                    if len(snippet) > 200:
                        snippet = snippet[:200] + "..."
                    
                    if title and len(snippet) > 10:
                        results.append(f"标题: {title}\n摘要: {snippet}")
                        if len(results) >= 3: # 取前3个有效结果
                            break
                except:
                    continue
            
            if results:
                combined_desc = "\n\n".join(results)
                logger.info(f"✅ 联网搜索成功，提取到 {len(results)} 条结果")
                return {
                    "description": combined_desc,
                    "source": "Google Search"
                }
            
            logger.warning("联网搜索未找到有效结果")
            return None
            
        except Exception as e:
            logger.warning(f"联网搜索失败: {e}")
            return None
        finally:
            if page:
                try:
                    page.quit()
                except:
                    pass

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
        
        # 1. 优先尝试真实联网搜索
        real_search_result = self._search_online_real(restaurant_name, context)
        if real_search_result:
            return real_search_result
            
        # 2. 如果真实搜索不可用或失败，回退到 LLM 模拟 (不推荐，但为了兼容)
        # 注意：如果本地模型没有联网能力，这一步其实是"幻觉"，但如果模型够强（如GPT-4）可能有知识库
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
                response = requests.post(url, json=payload, headers=self._get_headers(), timeout=120)
                
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
    
    def extract_location_info(self, address: str, city: str = "") -> Dict[str, str]:
        """
        使用AI从地址中提取行政区划信息（区县名和adcode）
        
        Args:
            address: 地址字符串
            city: 城市名称（可选上下文）
            
        Returns:
            包含 'district', 'adcode', 'city' 的字典
        """
        if not address:
            return {}
            
        try:
            prompt = f"""请分析以下中国地址，提取其所属的行政区（区/县）和对应的6位行政区划代码（Adcode）。
            
            城市（参考）：{city}
            地址：{address}
            
            要求：
            1. 准确识别该地址位于哪个区或县（如：朝阳区、海淀区）
            2. 提供该区/县的6位行政区划代码（如：110105）
            3. 必须返回标准的6位数字代码，不要猜测不确定的代码
            4. 即使地址不完整，也请根据地标或路名进行推断
            
            请以JSON格式返回结果：
            {{
                "district": "区县名称（如：朝阳区）",
                "adcode": "6位行政区划代码",
                "city": "城市名称"
            }}
            """

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的中国地理信息专家，熟悉全国各地的行政区划和代码。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2000,  # 增加token限制以防止截断
                "temperature": 0.1,  # 使用低温度以获得确定的答案
                "stream": False
            }
            
            def make_request(timeout):
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
            
            response = self._retry_request(make_request, 60, "AI提取行政区划")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                parsed = self._parse_json_response(content)
                
                if parsed and parsed.get('adcode'):
                    # 验证adcode格式
                    adcode = str(parsed.get('adcode', '')).strip()
                    if adcode.isdigit() and len(adcode) == 6:
                        return parsed
                    else:
                        logger.warning(f"AI返回的adcode格式不正确: {adcode}")
                
                return parsed or {}
            
            return {}
            
        except Exception as e:
            logger.warning(f"AI提取行政区划失败: {e}")
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
5. 返回严格的JSON格式，格式如下：
{{
    "comments": [
        {{"content": "评论内容1"}},
        {{"content": "评论内容2"}},
        {{"content": "评论内容3"}}
    ]
}}

重要提示：
- 必须返回有效的JSON格式
- 数组中的最后一个元素后面不要加逗号
- 对象中的最后一个属性后面不要加逗号
- 确保所有字符串都用双引号包裹
- 只返回JSON对象，不要添加任何其他文字、说明或代码块标记
- 不要使用```json```代码块包裹，直接返回JSON对象"""
        
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
                "max_tokens": 8000,  # 增加token限制，确保能返回所有评论（57条评论需要更多tokens）
                "temperature": 0.7,
                "stream": False
            }
            
            # 使用重试机制
            def make_request(timeout):
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
            
            response = self._retry_request(make_request, BASE_TIMEOUT_COMMENTS, "生成评论")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 记录原始响应内容（用于调试）
                logger.debug(f"评论生成原始响应（前500字符）: {content[:500]}")
                
                # 解析JSON响应
                parsed = self._parse_json_response(content)
                if not parsed:
                    # 如果解析失败，尝试处理被截断的JSON（提取已解析的部分）
                    logger.warning("无法解析评论生成响应，尝试提取部分评论...")
                    logger.debug(f"原始内容（前1000字符）: {content[:1000]}")
                    partial_comments = self._extract_partial_comments(content)
                    if partial_comments:
                        logger.info(f"成功提取到 {len(partial_comments)} 条部分评论（JSON可能被截断）")
                        return partial_comments
                    logger.warning("无法解析评论生成响应，且无法提取部分评论")
                    logger.info(f"原始响应内容（完整）: {content}")
                    return []
                
                # 提取评论列表
                comment_list = []
                if isinstance(parsed, dict) and 'comments' in parsed:
                    comment_list = parsed['comments']
                    logger.debug(f"从字典中提取到评论列表，长度: {len(comment_list)}")
                elif isinstance(parsed, list):
                    comment_list = parsed
                    logger.debug(f"解析结果为列表，长度: {len(comment_list)}")
                else:
                    logger.warning(f"评论响应格式不正确: {type(parsed)}, 内容: {str(parsed)[:200]}")
                    # 尝试从解析结果中提取评论
                    if isinstance(parsed, dict):
                        # 尝试查找其他可能的键
                        for key in ['comment', 'comment_list', 'items', 'data']:
                            if key in parsed and isinstance(parsed[key], list):
                                comment_list = parsed[key]
                                logger.info(f"从键 '{key}' 中找到评论列表")
                                break
                    if not comment_list:
                        return []
                
                # 提取评论内容
                comments = []
                for idx, comment_item in enumerate(comment_list):
                    if isinstance(comment_item, dict):
                        content_text = comment_item.get('content', '') or comment_item.get('text', '') or comment_item.get('comment', '')
                    elif isinstance(comment_item, str):
                        content_text = comment_item
                    else:
                        logger.debug(f"跳过非字符串/字典类型的评论项 {idx}: {type(comment_item)}")
                        continue
                    
                    if content_text and len(content_text.strip()) >= 5:
                        comments.append(content_text.strip())
                    else:
                        logger.debug(f"跳过过短的评论项 {idx}: {content_text[:50] if content_text else 'None'}")
                
                logger.info(f"成功生成 {len(comments)} 条评论")
                if len(comments) == 0 and len(comment_list) > 0:
                    logger.warning(f"⚠️  解析到 {len(comment_list)} 个评论项，但提取后为0条，请检查评论格式")
                    logger.debug(f"评论项示例: {comment_list[0] if comment_list else 'None'}")
                return comments
            else:
                logger.warning(f"生成评论API调用失败: {response.status_code if response else '无响应'}")
                return []
                
        except Exception as e:
            logger.warning(f"生成评论失败: {e}")
            return []
    
    def generate_usernames(self, count: int = 50) -> List[str]:
        """
        生成随机用户名列表
        
        Args:
            count: 生成数量
            
        Returns:
            用户名列表
        """
        logger.info(f"正在生成 {count} 个随机用户名...")
        
        prompt = f"""请生成{count}个真实、自然的小红书/大众点评风格的用户名。

要求：
1. 风格多样化，包括：
   - 英文名+数字（如：Coco123, Amy_09）
   - 中文昵称（如：吃货小王, 旅行日记, 也就是个废柴）
   - 诗意/文艺类（如：晚风, 浅夏, 听风）
   - 可爱/搞怪类（如：小猪佩奇, 芋泥波波）
   - 纯英文或拼音（如：Summer, Lisi）
2. 不要包含“测试”、“用户”、“User”、“微信用户”等明显机器生成或默认的词汇
3. 不要包含违规词汇
4. 每个用户名长度在2-12个字符之间
5. 必须返回{count}个不同的用户名

请以JSON格式返回结果：
{{
    "usernames": [
        "用户名1",
        "用户名2",
        ...
    ]
}}"""

        try:
            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的社交媒体用户名生成专家，擅长生成真实、有趣、多样的用户昵称。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2048,
                "temperature": 0.8,  # 高创造性
                "stream": False
            }
            
            def make_request(timeout):
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
            
            response = self._retry_request(make_request, 60, "生成用户名")
            
            if response and response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                parsed = self._parse_json_response(content)
                if not parsed:
                    # 尝试从文本列表提取
                    import re
                    usernames = []
                    lines = content.split('\n')
                    for line in lines:
                        # 匹配 "1. 用户名" 或 "- 用户名" 格式
                        match = re.search(r'^\s*[-*\d]+\.?\s*["\']?([^"\']+)["\']?\s*$', line)
                        if match:
                            name = match.group(1).strip()
                            if len(name) > 1 and len(name) < 20:
                                usernames.append(name)
                    if usernames:
                        return usernames[:count]
                    return []
                
                usernames = []
                if isinstance(parsed, dict) and 'usernames' in parsed:
                    usernames = parsed['usernames']
                elif isinstance(parsed, list):
                    usernames = parsed
                
                # 过滤和清理
                valid_usernames = []
                for name in usernames:
                    if isinstance(name, str):
                        name = name.strip()
                        if 2 <= len(name) <= 20:
                            valid_usernames.append(name)
                            
                return valid_usernames
            else:
                logger.warning(f"生成用户名API调用失败")
                return []
                
        except Exception as e:
            logger.warning(f"生成用户名失败: {e}")
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
            # 获取一个存在的用户ID（优先查询，如果没有则使用默认值1）
            default_user_id = 1  # 默认用户ID
            try:
                # 尝试查询一个存在的用户ID
                query_sql = "SELECT id FROM client_user LIMIT 1"
                with db.engine.connect() as conn:
                    result = conn.execute(text(query_sql))
                    row = result.fetchone()
                    if row:
                        default_user_id = row[0]
                        logger.debug(f"使用用户ID: {default_user_id}")
            except Exception as e:
                logger.debug(f"查询用户ID失败，使用默认值1: {e}")
            
            for comment_content in comments:
                try:
                    sql = """
                        INSERT INTO tweets_evaluate (client_user_id, tweets_id, evaluate_content)
                        VALUES (:client_user_id, :tweets_id, :evaluate_content)
                    """
                    params = {
                        'client_user_id': default_user_id,
                        'tweets_id': tweet_id,
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
            
        # --- 修改：不再尝试联网搜索补充信息 ---
        # try:
        #     logger.info(f"尝试联网搜索以补充餐厅信息: {restaurant_name}")
        #     search_result = self.search_restaurant_online(restaurant_name, "")
        #     if search_result and search_result.get('description'):
        #         search_desc = search_result.get('description', '')
        #         if len(search_desc) > 10:
        #             logger.info(f"✅ 已获取联网搜索信息，长度: {len(search_desc)}")
        #             if not restaurant_desc:
        #                 restaurant_desc = f"【网络搜索信息】：\n{search_desc}"
        #             else:
        #                 restaurant_desc = f"{restaurant_desc}\n\n【网络搜索补充信息】：\n{search_desc}"
        # except Exception as e:
        #     logger.warning(f"联网搜索补充信息失败: {e}")
        # --------------------------------
        
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
餐厅描述（作为背景信息）：{restaurant_desc[:1500] if restaurant_desc else '无'}
{comments_text if comments_text else ''}

小红书原始标题：{original_title[:100] if original_title else '无'}
小红书原始内容：{original_description[:500] if original_description else '无'}

要求：
1. 【不需要生成标题】，只需要生成正文内容（description）
2. 生成详细的推荐描述（300-500字）
3. 重点基于【用户评论】进行创作，突出真实体验（口味、服务、避雷点等）
4. 不要特意去搜集或强调地址、价格、营业时间等硬信息（除非评论里自然提到了性价比）
5. 使用小红书风格的文案（自然、生动、有吸引力，多用emoji）
6. 如果提供了原始笔记内容，请结合原始内容和评论生成
7. 评论内容可以作为参考，但不要直接复制，要转述成自己的语言

请以JSON格式返回结果：
{{
    "description": "改写后的详细描述（300-500字，侧重评论体验）"
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
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
            
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

    def paraphrase_tripcom_restaurant_note(
        self,
        restaurant_name: str,
        restaurant_desc: str = "",
        tripcom_rating: Optional[float] = None,
        tripcom_review_count: Optional[int] = None,
        tripcom_reviews: Optional[List[str]] = None,
        include_score_line: bool = True,
        include_address_line: bool = False,
        address_text: str = ""
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        基于 Trip.com 的评分/评价摘录，把“字段型信息”改写成小红书风格探店文案。

        重要：只允许基于输入信息总结，不要编造菜品/价格/营业时间等未提供信息。

        Returns:
            (title, description)；失败返回 (None, None)
        """
        if not restaurant_name:
            return None, None

        # 在请求前检查模型是否可用
        is_available, error_msg = self.check_model_available()
        if not is_available:
            logger.warning(f"Trip.com改写跳过：模型不可用: {error_msg}")
            return None, None

        try:
            reviews = tripcom_reviews or []
            # 只取少量高信息密度评价，避免prompt过长
            reviews = [r.strip() for r in reviews if isinstance(r, str) and r.strip()]
            reviews = reviews[:10]

            rating_str = f"{tripcom_rating:.1f}/5" if isinstance(tripcom_rating, (int, float)) else "未知"
            review_count_str = str(tripcom_review_count) if isinstance(tripcom_review_count, int) else "未知"

            reviews_block = ""
            if reviews:
                lines = []
                for i, r in enumerate(reviews, 1):
                    # 每条截断，防止过长
                    rr = r.replace("\r", " ").replace("\n", " ").strip()
                    if len(rr) > 140:
                        rr = rr[:140] + "…"
                    lines.append(f"{i}. {rr}")
                reviews_block = "\n".join(lines)
            else:
                reviews_block = "（无可用评价摘录）"

            # 如果既没有简介也没有评价摘录，直接走模板（避免模型“编造菜品/营业时间”等）
            if not (restaurant_desc or "").strip() and not reviews:
                title = restaurant_name
                desc = (
                    "我目前拿到的公开信息主要是Trip.com的评分和评价数，缺少可用的评价内容摘录。"
                    "先把基础信息整理出来，等补齐评价内容后再做更像探店的总结。\\n\\n"
                    "#美食探店 #探店记录"
                )
                desc = desc.replace("\\n", "\n")
                suffix_lines = []
                if include_score_line:
                    suffix_lines.append(f"- Trip.com：{rating_str}（{review_count_str}条评价）")
                if include_address_line and address_text:
                    suffix_lines.append(f"- 地址：{address_text}")
                if suffix_lines:
                    desc = desc.rstrip() + "\n\n" + "\n".join(suffix_lines)
                return title, desc

            prompt = f"""你需要把一条“评分/评价数/简介/评价摘录”这种字段型信息，改写成小红书风格的探店笔记。

餐厅名称：{restaurant_name}
Trip.com评分：{rating_str}
Trip.com评价数：{review_count_str}条
Trip.com餐厅简介（可能为空）：{(restaurant_desc or '').strip()[:800]}

Trip.com用户评价摘录（只能基于这些内容总结，不要照抄原句）：
{reviews_block}

写作要求：
1. 只允许基于我提供的信息进行总结与改写；不要编造没提供的菜品名、价格、营业时间、排队情况、交通信息等
2. 语气要像真实用户在小红书写探店：口语化、清晰、有细节，但不浮夸
3. 正文 180-320 字，分段清楚；建议包含：总体印象 + 亮点/槽点(如有) + 适合人群/建议
4. 不要输出任何 #话题 标签、也不要输出任何“评分/评价数/地址/Trip.com”等字段行
5. JSON字符串中不要输出任何“真实换行符”，如果需要分段，请用字面量 \\n 表示换行

请严格以JSON格式返回，不要添加任何解释文字：
{{
  "title": "标题（20字内，可带店名或关键词）",
  "description": "正文"
}}"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的小红书美食探店文案创作者，擅长把平台评价总结成真实、克制、有帮助的探店笔记。你绝不编造未提供的信息。"
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 900,
                "temperature": getattr(Config, 'LLM_TEMPERATURE', 0.7),
                "stream": False
            }

            def make_request(timeout):
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)

            response = self._retry_request(make_request, BASE_TIMEOUT_PARAPHRASE, "Trip.com改写")
            if not response or response.status_code != 200:
                logger.warning(f"Trip.com改写失败: {response.status_code if response else '无响应'}")
                return None, None

            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            parsed = self._parse_json_response(content)
            if not parsed:
                # 容错：即便JSON不严格（夹了#话题等），也尽量从字符串值里抽取
                def _extract_quoted_value(raw: str, key: str) -> str:
                    m = re.search(rf'"{re.escape(key)}"\s*:\s*"', raw)
                    if not m:
                        return ""
                    i = m.end()
                    out = []
                    escape = False
                    while i < len(raw):
                        ch = raw[i]
                        if escape:
                            out.append(ch)
                            escape = False
                        else:
                            if ch == "\\":
                                out.append(ch)
                                escape = True
                            elif ch == '"':
                                break
                            else:
                                out.append(ch)
                        i += 1
                    return "".join(out).strip()

                try:
                    extracted_desc = _extract_quoted_value(content, "description")
                    if extracted_desc:
                        extracted_desc = extracted_desc.replace("\\n", "\n").replace('\\"', '"')
                        final_title = restaurant_name
                        final_desc = extracted_desc
                        suffix_lines = []
                        if include_score_line:
                            suffix_lines.append(f"- Trip.com：{rating_str}（{review_count_str}条评价）")
                        if include_address_line and address_text:
                            suffix_lines.append(f"- 地址：{address_text}")
                        if suffix_lines:
                            final_desc = final_desc.rstrip() + "\n\n" + "\n".join(suffix_lines)
                        return final_title, final_desc
                except Exception:
                    pass
                return None, None

            # 标题强制保持为餐厅名（用户要求标题不变）
            title = restaurant_name
            desc = (parsed.get('description') or '').strip()
            if not desc:
                return None, None
            # 将字面量 \n 还原成换行（模型被要求不要输出真实换行符）
            desc = desc.replace("\\n", "\n")

            # 安全清理：移除模型误输出的“#话题/字段尾巴”
            try:
                cleaned_lines = []
                for ln in desc.splitlines():
                    s = ln.strip()
                    if not s:
                        cleaned_lines.append(ln)
                        continue
                    # 去掉话题标签行
                    if s.startswith("#") or "话题" in s:
                        continue
                    # 去掉字段行
                    if s.startswith(("- Trip.com", "Trip.com", "- 地址", "地址：", "评分：", "评价数：")):
                        continue
                    cleaned_lines.append(ln)
                desc = "\n".join([l.rstrip() for l in cleaned_lines]).strip()
            except Exception:
                pass

            return title, desc

        except Exception as e:
            logger.warning(f"Trip.com改写异常: {e}")
            # 兜底模板
            try:
                rating_str = f"{tripcom_rating:.1f}/5" if isinstance(tripcom_rating, (int, float)) else "未知"
                review_count_str = str(tripcom_review_count) if isinstance(tripcom_review_count, int) else "未知"
                title = restaurant_name
                desc = (
                    "我目前拿到的信息比较有限（评价内容摘录不足），先做一版克制的整理；等补齐更多真实评价后再更新更完整的探店体验。"
                ).replace("\\n", "\n")
                return title, desc
            except Exception:
                return None, None

    def check_note_complete(self, title: str, content: str) -> Tuple[bool, str]:
        """
        使用AI判断一条贴文内容是否“完整可发布”（小红书风格）。

        返回:
            (complete, reason)
        """
        title = (title or "").strip()
        content = (content or "").strip()
        if not title and not content:
            return False, "标题和正文都为空"
        if not content or len(content) < 30:
            return False, "正文过短"

        is_available, error_msg = self.check_model_available()
        if not is_available:
            # AI不可用时回退到简单规则
            return (len(content) >= 120 and not re.search(r'[，,：:]$', content)), f"AI不可用，规则判定: {error_msg}"

        try:
            prompt = f"""请判断下面这条小红书贴文正文是否“完整可发布”。

标题：{title[:80]}
正文：{content[:800]}

判定标准（满足多数即可判为完整）：
1) 正文不是半句/截断/结尾悬空（不要以逗号、冒号、顿号等结尾）
2) 内容不是纯字段堆砌（例如“评分/评价数/地址/菜系”这种列表）
3) 有清晰的表达（至少2-3句），读起来像一段正常笔记
4) 正文长度至少120字（非常短通常不算完整）

请严格返回JSON，不要输出任何额外文字：
{{
  "complete": true/false,
  "reason": "一句话原因"
}}"""

            url = f"{self.api_base}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是内容质检助手，只做完整性判定，不改写内容。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200,
                "temperature": 0.1,
                "stream": False
            }

            def make_request(timeout):
                return requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)

            response = self._retry_request(make_request, 60, "AI判定内容完整性")
            if not response or response.status_code != 200:
                return False, "AI判定失败（无响应或非200）"

            result = response.json()
            content_out = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            parsed = self._parse_json_response(content_out)
            if not isinstance(parsed, dict):
                return False, "AI判定失败（解析JSON失败）"

            complete_val = bool(parsed.get("complete"))
            reason = str(parsed.get("reason") or "").strip() or ("完整" if complete_val else "不完整")
            return complete_val, reason

        except Exception as e:
            return False, f"AI判定异常: {e}"


# 全局实例
_paraphraser = None

def get_ai_paraphraser() -> AIParaphraser:
    """获取AI转述器单例"""
    global _paraphraser
    if _paraphraser is None:
        _paraphraser = AIParaphraser()
    return _paraphraser
