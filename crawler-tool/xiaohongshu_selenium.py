#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书爬虫 - Selenium版本（模拟浏览器操作）
使用Selenium模拟真实用户操作，绕过反爬机制

用法:
    python3 xiaohongshu_selenium.py --keyword "深圳美食" --pages 5
    python3 xiaohongshu_selenium.py --keyword "潮汕菜" --city "深圳" --upload
"""
import sys
import os
import json
import time
import random
import re
import logging
from typing import List, Dict, Optional, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from performance_monitor import CrawlerPerformanceTimer, get_crawler_performance_monitor
from realtime_performance import get_real_time_display

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIParaphraser:
    """AI转述工具（使用Ollama）- 同时完成转述和类型分类"""
    
    def __init__(self):
        self.api_base = Config.LLM_API_BASE
        self.model = Config.LLM_MODEL
        self.max_tokens = Config.LLM_MAX_TOKENS
        
        # 可用的餐厅类型列表（用于AI分类）- 完整列表
        self.restaurant_types = {
            "川菜": 6, "淮扬菜": 8, "杭帮菜": 9, "潮汕菜": 10, "烧烤": 11,
            "粤菜": 12, "德国菜": 13, "日本料理": 14, "法国菜": 15, "韩国料理": 16,
            "新疆菜": 17, "湘菜": 18, "农家菜": 19, "火锅": 20, "咖啡厅": 21,
            "自助餐": 22, "鱼鲜": 23, "东北菜": 24, "私房菜": 25, "东南亚菜": 26,
            "特色菜": 27, "创意菜": 28, "北京菜": 29, "家常菜": 30, "茶餐厅": 31,
            "小龙虾": 32, "素食": 33, "小吃快餐": 34, "面包甜点": 35, "面馆": 36,
            "大排档": 37, "西餐": 38, "云南菜": 39, "西北菜": 40,
            "人均50至100": 41, "人均100至200": 42, "人均200至300": 43,
            "人均300以上": 44, "人均50元以内": 45
        }
        
        # 检查模型是否可用（如果已有模型则使用已有模型，仅使用Ollama）
        try:
            self._check_model_available()
        except Exception as e:
            # 如果检查失败，记录警告但不立即退出（允许在运行时失败）
            logger.warning(f"模型检查失败: {str(e)}，将在使用时再次尝试")
    
    def _check_model_available(self):
        """检查模型是否可用，如果已有模型则使用已有模型"""
        try:
            import requests
            
            # 检查Ollama服务是否运行
            try:
                response = requests.get(f"{self.api_base.replace('/v1', '')}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    if models:
                        # 如果已有模型，检查是否有指定的模型
                        model_names = [m.get('name', '') for m in models]
                        if any(self.model in name for name in model_names):
                            logger.info(f"✓ 使用模型: {self.model}")
                            return
                        else:
                            # 使用第一个可用模型
                            available_model = model_names[0].split(':')[0] if model_names else None
                            if available_model:
                                logger.info(f"✓ 使用已有模型: {available_model}（未找到配置的模型 {self.model}）")
                                self.model = available_model
                                return
                        
                        logger.info(f"已有模型列表: {model_names}")
                    else:
                        # 没有模型，提示用户下载
                        logger.warning(f"Ollama服务中没有可用模型")
                        logger.info(f"请手动下载模型: ollama pull {self.model}")
                else:
                    logger.warning(f"无法连接到Ollama服务 (状态码: {response.status_code})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"无法连接到Ollama服务 ({self.api_base})，请确保服务已启动")
                logger.info("提示: brew services start ollama")
                
        except Exception as e:
            logger.warning(f"检查模型时出错: {str(e)}")
    
    def paraphrase_and_classify(self, text: str, restaurant_name: str = "") -> Dict[str, Any]:
        """使用AI同时完成转述和类型分类（带重试机制）"""
        if not text or len(text.strip()) < 10:
            return {
                'paraphrased': text,
                'parent_id': 5,
                'child_ids': [10, 42]  # 默认：潮汕菜 + 人均100至200
            }
        
        import requests
        import time
        from performance_monitor import get_crawler_performance_monitor
        
        monitor = get_crawler_performance_monitor()
        
        # 构建类型列表字符串
        type_list = "、".join(self.restaurant_types.keys())
        
        prompt = f"""请分析以下餐厅信息，完成两个任务：

1. 将内容转述成新的表达方式（保持原意，但用不同的表达）
2. 判断餐厅类型（从以下类型中选择1-3个最匹配的，用逗号分隔）

可用类型：{type_list}

餐厅名称：{restaurant_name}
原文内容：{text}

请以JSON格式返回结果：
{{
    "paraphrased": "转述后的内容（去掉小红书标记符号，200-500字）",
    "types": ["类型1", "类型2", "类型3"]
}}

只返回JSON，不要其他文字。"""
        
        # 重试机制：最多5次，每次间隔递增，超时时间逐步增加
        max_retries = 5
        retry_delays = [3, 5, 10, 15, 20]  # 重试延迟（秒）
        timeout_values = [120, 150, 180, 200, 240]  # 逐步增加超时时间（秒）
        
        for attempt in range(max_retries):
            # 记录每次API调用的性能
            with CrawlerPerformanceTimer(f"ai.api_call.attempt_{attempt + 1}"):
                try:
                    current_timeout = timeout_values[min(attempt, len(timeout_values) - 1)]
                    logger.debug(f"AI请求尝试 {attempt + 1}/{max_retries}，超时设置: {current_timeout}秒")
                    
                    api_start_time = time.time()
                    response = requests.post(
                        f"{self.api_base}/chat/completions",
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "max_tokens": self.max_tokens,
                            "temperature": 0.7
                        },
                        timeout=current_timeout  # 动态超时时间
                    )
                    api_duration = time.time() - api_start_time
                    monitor.record_metric("ai.api_call.duration", api_duration, {
                        'attempt': attempt + 1,
                        'status_code': response.status_code,
                        'restaurant_name': restaurant_name[:30]
                    })
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                        
                        # 清理可能的markdown代码块标记
                        ai_response = re.sub(r'```json\s*', '', ai_response)
                        ai_response = re.sub(r'```\s*', '', ai_response)
                        ai_response = ai_response.strip()
                        
                        try:
                            # 尝试解析JSON
                            parsed = json.loads(ai_response)
                            
                            paraphrased = parsed.get('paraphrased', text)
                            type_names = parsed.get('types', [])
                            
                            # 转换为类型ID
                            child_ids = []
                            for type_name in type_names:
                                if type_name in self.restaurant_types:
                                    type_id = self.restaurant_types[type_name]
                                    if type_id not in child_ids:
                                        child_ids.append(type_id)
                            
                            # 如果没有匹配到类型，抛出异常
                            if not child_ids:
                                error_msg = f"AI返回的类型无法匹配到数据库类型: {type_names}。餐厅: {restaurant_name}"
                                logger.error(error_msg)
                                monitor.record_metric("ai.error", 1.0, {
                                    'attempt': attempt + 1,
                                    'error_type': 'type_mismatch',
                                    'restaurant_name': restaurant_name[:30],
                                    'ai_types': type_names
                                })
                                raise ValueError(error_msg)
                            
                            logger.info(f"✓ AI转述和分类成功: {restaurant_name} -> 类型: {type_names}")
                            
                            # 记录成功信息
                            monitor.record_metric("ai.success", 1.0, {
                                'attempt': attempt + 1,
                                'restaurant_name': restaurant_name[:30],
                                'types_count': len(type_names)
                            })
                            
                            return {
                                'paraphrased': paraphrased,
                                'parent_id': 5,
                                'child_ids': sorted(child_ids)
                            }
                            
                        except json.JSONDecodeError:
                            # 如果AI返回的不是JSON，抛出异常
                            error_msg = f"AI返回格式不正确，无法解析JSON。响应内容: {ai_response[:200]}"
                            logger.error(error_msg)
                            monitor.record_metric("ai.error", 1.0, {
                                'attempt': attempt + 1,
                                'error_type': 'json_decode_error',
                                'restaurant_name': restaurant_name[:30]
                            })
                            raise ValueError(error_msg)
                    else:
                        # HTTP错误处理
                        error_message = ""
                        try:
                            error_data = response.json()
                            error_message = error_data.get('error', {}).get('message', '')
                        except:
                            # 如果JSON解析失败，尝试从响应文本中提取
                            response_text = response.text[:500]  # 增加长度以获取完整错误信息
                            if "model runner has unexpectedly stopped" in response_text.lower():
                                error_message = "model runner has unexpectedly stopped, this may be due to resource limitations or an internal error"
                            else:
                                error_message = response_text
                        
                        # 记录错误信息
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': f'http_{response.status_code}',
                            'status_code': response.status_code,
                            'restaurant_name': restaurant_name[:30],
                            'error_message': error_message[:100]
                        })
                        
                        # 特殊处理500错误（模型资源不足）
                        if response.status_code == 500:
                            if "model runner has unexpectedly stopped" in error_message.lower() or "model runner has unexpectedly stopped" in response.text.lower():
                                if attempt < max_retries - 1:
                                    wait_time = retry_delays[min(attempt, len(retry_delays) - 1)]
                                    logger.warning(f"模型运行异常（可能是资源不足），{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                                    logger.info("提示：如果持续失败，请检查：")
                                    logger.info("  1. Ollama服务状态: brew services list | grep ollama")
                                    logger.info("  2. 系统内存是否充足: top 或 htop")
                                    logger.info("  3. 尝试重启Ollama: brew services restart ollama")
                                    time.sleep(wait_time)
                                    continue
                                else:
                                    error_msg = f"AI请求失败: HTTP 500 - 模型运行异常（可能是资源不足）。\n" \
                                               f"错误详情: {error_message[:200]}\n" \
                                               f"建议：\n" \
                                               f"  1. 检查系统内存: top 或 htop\n" \
                                               f"  2. 重启Ollama服务: brew services restart ollama\n" \
                                               f"  3. 尝试使用更小的模型: ollama pull tinyllama\n" \
                                               f"  4. 检查Ollama日志: tail -f ~/.ollama/logs/server.log"
                                    logger.error(error_msg)
                                    raise ConnectionError(error_msg)
                        
                        # 其他HTTP错误
                        if attempt < max_retries - 1:
                            wait_time = retry_delays[attempt]
                            logger.warning(f"AI请求失败: HTTP {response.status_code}，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                            logger.debug(f"错误详情: {error_message[:200] if error_message else response.text[:200]}")
                            time.sleep(wait_time)
                            continue
                        else:
                            error_msg = f"AI请求失败: HTTP {response.status_code}。响应: {error_message[:200] if error_message else response.text[:200]}"
                            logger.error(error_msg)
                            raise ConnectionError(error_msg)
                            
                except requests.exceptions.ConnectionError as e:
                    if attempt < max_retries - 1:
                        wait_time = retry_delays[attempt]
                        logger.warning(f"无法连接到AI服务 ({self.api_base})，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                        logger.info("请确保Ollama服务已启动: brew services start ollama")
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': 'connection_error',
                            'restaurant_name': restaurant_name[:30]
                        })
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = f"无法连接到AI服务 ({self.api_base})。请确保Ollama服务已启动: brew services start ollama"
                        logger.error(error_msg)
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': 'connection_error_final',
                            'restaurant_name': restaurant_name[:30]
                        })
                        raise ConnectionError(error_msg) from e
                except requests.exceptions.Timeout as e:
                    current_timeout = timeout_values[min(attempt, len(timeout_values) - 1)]
                    if attempt < max_retries - 1:
                        wait_time = retry_delays[min(attempt, len(retry_delays) - 1)]
                        next_timeout = timeout_values[min(attempt + 1, len(timeout_values) - 1)]
                        logger.warning(f"AI请求超时（{current_timeout}秒），{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                        logger.info(f"下次尝试将使用更长的超时时间: {next_timeout}秒")
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': 'timeout',
                            'timeout_used': current_timeout,
                            'restaurant_name': restaurant_name[:30]
                        })
                        time.sleep(wait_time)
                        continue
                    else:
                        final_timeout = timeout_values[-1]
                        error_msg = f"AI请求超时（已尝试{max_retries}次，最后一次超时设置: {final_timeout}秒）。\n" \
                                   f"可能是模型响应过慢或资源不足。\n" \
                                   f"建议：\n" \
                                   f"  1. 检查系统资源: top（系统自带）或 htop（需安装: brew install htop）\n" \
                                   f"  2. 检查Ollama服务: brew services list | grep ollama\n" \
                                   f"  3. 重启Ollama服务: brew services restart ollama\n" \
                                   f"  4. 尝试使用更小的模型: ollama pull phi\n" \
                                   f"  5. 检查Ollama日志: tail -f ~/.ollama/logs/server.log\n" \
                                   f"  6. 查看Ollama进程: ps aux | grep ollama"
                        logger.error(error_msg)
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': 'timeout_final',
                            'timeout_used': final_timeout,
                            'restaurant_name': restaurant_name[:30]
                        })
                        raise ConnectionError(error_msg) from e
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = retry_delays[attempt]
                        logger.warning(f"AI转述和分类失败: {str(e)}，{wait_time}秒后重试 ({attempt + 1}/{max_retries})...")
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': 'unknown_error',
                            'restaurant_name': restaurant_name[:30],
                            'error_message': str(e)[:100]
                        })
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"AI转述和分类失败: {str(e)}")
                        monitor.record_metric("ai.error", 1.0, {
                            'attempt': attempt + 1,
                            'error_type': 'unknown_error_final',
                            'restaurant_name': restaurant_name[:30],
                            'error_message': str(e)[:100]
                        })
                        raise
    
    def paraphrase(self, text: str) -> str:
        """使用AI转述文本（兼容旧接口）"""
        with CrawlerPerformanceTimer("ai.paraphrase_only"):
            result = self.paraphrase_and_classify(text)
            return result['paraphrased']


class WatermarkRemover:
    """图片水印去除工具"""
    
    def __init__(self):
        self.enabled = Config.REMOVE_WATERMARK
    
    def remove_watermark(self, image_path: str) -> str:
        """去除图片水印"""
        if not self.enabled:
            return image_path
        
        try:
            import cv2
            import numpy as np
            
            # 读取图片
            img = cv2.imread(image_path)
            if img is None:
                logger.warning(f"无法读取图片: {image_path}")
                return image_path
            
            h, w = img.shape[:2]
            
            # 检测并去除常见的小红书水印位置（右下角）
            # 小红书水印通常在右下角，约占图片的15%高度和30%宽度
            watermark_region_h = int(h * 0.15)  # 底部15%
            watermark_region_w = int(w * 0.3)   # 右侧30%
            
            # 创建mask（标记需要去除的区域）
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[h - watermark_region_h:, w - watermark_region_w:] = 255
            
            # 使用图像修复算法（inpainting）去除水印
            # Telea算法适合处理小区域
            result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
            
            # 保存处理后的图片（覆盖原图或创建新文件）
            output_path = image_path.replace('.jpg', '_nowatermark.jpg').replace('.png', '_nowatermark.png')
            if not any(output_path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                # 如果路径不包含扩展名，添加.jpg
                output_path = image_path.rsplit('.', 1)[0] + '_nowatermark.jpg'
            
            cv2.imwrite(output_path, result)
            logger.info(f"✓ 水印去除完成: {image_path} -> {output_path}")
            
            return output_path
            
        except ImportError as e:
            logger.warning(f"OpenCV未安装，跳过水印去除: {str(e)}")
            return image_path
        except Exception as e:
            logger.error(f"去除水印失败 {image_path}: {str(e)}")
            return image_path
    
    def remove_watermark_from_url(self, image_url: str, download_dir: str = None) -> str:
        """从URL下载图片并去除水印"""
        if not self.enabled:
            return image_url
        
        try:
            # 先下载图片
            downloader = ImageDownloader(download_dir)
            local_path = downloader.download_image(image_url)
            
            if local_path:
                # 去除水印
                return self.remove_watermark(local_path)
            else:
                return image_url
                
        except Exception as e:
            logger.error(f"处理图片URL失败 {image_url}: {str(e)}")
            return image_url


# 全局实例
ai_paraphraser = AIParaphraser()
watermark_remover = WatermarkRemover()

# 用户名列表：中药名 + 星宿名 + 星体名
USER_NAMES = [
    # 中药名
    '人参', '黄芪', '当归', '白术', '茯苓', '甘草', '陈皮', '半夏',
    '黄连', '黄芩', '黄柏', '知母', '生地', '熟地', '白芍', '赤芍',
    '川芎', '丹参', '红花', '桃仁', '益母草', '鸡血藤', '牛膝', '杜仲',
    '枸杞', '菟丝子', '女贞子', '五味子', '山茱萸', '补骨脂', '巴戟天', '肉苁蓉',
    '麦冬', '天冬', '沙参', '玉竹', '石斛', '百合', '桔梗', '贝母',
    '杏仁', '紫苏', '薄荷', '桑叶', '菊花', '金银花', '连翘', '蒲公英',
    '防风', '荆芥', '白芷', '细辛', '桂枝', '麻黄', '柴胡', '升麻',
    '葛根', '知母', '石膏', '栀子', '淡竹叶', '木通', '车前子', '滑石',
    '大黄', '芒硝', '番泻叶', '火麻仁', '郁李仁', '牵牛子', '甘遂', '大戟',
    '独活', '威灵仙', '秦艽', '防己', '桑寄生', '五加皮', '千年健', '络石藤',
    '陈皮', '青皮', '枳实', '枳壳', '木香', '香附', '乌药', '沉香',
    '山楂', '神曲', '麦芽', '谷芽', '鸡内金', '莱菔子', '槟榔', '使君子',
    '三七', '白及', '仙鹤草', '侧柏叶', '地榆', '槐花', '茜草', '蒲黄',
    '延胡索', '川楝子', '乳香', '没药', '五灵脂', '降香', '苏木', '自然铜',
    '天麻', '钩藤', '石决明', '珍珠母', '牡蛎', '龙骨', '酸枣仁', '远志',
    '朱砂', '磁石', '琥珀', '柏子仁', '合欢皮', '夜交藤', '灵芝', '首乌藤',
    '麝香', '冰片', '苏合香', '石菖蒲', '安息香', '樟脑', '蟾酥', '牛黄',
    '党参', '太子参', '西洋参', '山药', '大枣', '蜂蜜', '饴糖', '阿胶',
    '鹿茸', '鹿角', '海狗肾', '海马', '蛤蚧', '紫河车', '冬虫夏草', '锁阳',
    '淫羊藿', '仙茅', '续断', '骨碎补', '狗脊', '桑螵蛸', '海螵蛸', '金樱子',
    
    # 二十八星宿（东方青龙）
    '角宿', '亢宿', '氐宿', '房宿', '心宿', '尾宿', '箕宿',
    # 二十八星宿（北方玄武）
    '斗宿', '牛宿', '女宿', '虚宿', '危宿', '室宿', '壁宿',
    # 二十八星宿（西方白虎）
    '奎宿', '娄宿', '胃宿', '昴宿', '毕宿', '觜宿', '参宿',
    # 二十八星宿（南方朱雀）
    '井宿', '鬼宿', '柳宿', '星宿', '张宿', '翼宿', '轸宿',
    
    # 北斗七星
    '天枢', '天璇', '天玑', '天权', '玉衡', '开阳', '摇光',
    
    # 三垣
    '紫微垣', '太微垣', '天市垣',
    
    # 五大行星/五行星
    '水星', '金星', '火星', '木星', '土星',
    
    # 其他星体名
    '北极星', '南斗', '北斗', '天狼', '织女', '牛郎', '大熊', '小熊',
    '天琴', '天鹰', '天鹅', '仙后', '仙王', '英仙', '武仙', '猎户',
    '御夫', '双子', '巨蟹', '狮子', '室女', '天秤', '天蝎', '人马',
    '摩羯', '宝瓶', '双鱼', '白羊', '金牛', '天枰', '半人马', '长蛇',
    '凤凰', '天鹤', '天燕', '天鸽', '乌鸦', '麒麟', '豺狼', '狐狸',
    '孔雀', '杜鹃', '飞马', '仙女', '天鹰', '天鹅', '蛇夫', '巨蛇',
    '天箭', '海豚', '小马', '蝎虎', '天箭', '天箭座', '天箭星', '天箭星宿',
    
    # 带"三"的星体名
    '三星', '三垣', '三台', '三才', '三光', '三曜', '三清', '三宝',
    '三生', '三界', '三才星', '三台星', '三光星', '三曜星',
    
    # JOJO替身名
    '白金之星', '世界', '疯狂钻石', '杀手皇后', '黄金体验', '石之自由',
    '天气预报', '白蛇', '绿之法皇', '愚者', '银色战车', '紫色隐者',
    '红色魔术师', '黄色节制', '倒吊男', '皇帝', '女教皇', '命运之轮',
    '正义', '恋人之牌', '太阳', '月亮', '恶魔', '死神', '审判', '女帝',
    '星尘十字军', '白金之星世界', '蓝色忧郁', '回音', '高速之星', '沙丘',
    '天堂之门', '黄金体验镇魂曲', '钢链手指', '紫烟', '性感手枪', '航空史密斯',
    '铁塔', '白银战车', '滚石', '黑檀木恶魔', '极恶中队', '沙滩男孩',
    '艾比斯神', '梅杜莎', '婴儿面孔', '诅咒', '纳粹之魂', '大总统',
    '歪男', '左手', '右手', '隐者之紫', '灰色之塔', '绿色婴儿',
    '圣母像', '20世纪男孩', '波西米亚狂想曲', '长发公主', '恶行易施', '无重力',
    '超级飞人', '绿色时光', '多佩什', '纸月之王', '拉链人', '蓝调布鲁斯',
    '潜行者', '监狱', '偏执狂', '娃娃脸', '克里姆王', '月之少年', '飞碟',
    '夏威夷', '生存者', '卡纳', '龙之梦', '跳跃闪电杰克', '地铁',
    '超越天堂', '软湿机器', '重金属', 'D4C', '奇库乔', '十一月之雨', '珍珠果酱',
    '完美先生', 'D4C爱的火车', '奇迹之人', '亲吻', '燃烧的雨', '加州旅馆',
    '诺里斯', '超级杀手', '巧克力迪斯科', '佩西', '杰瑞', '汤姆', '神秘列车',
    '工作坊', '成长', '请安眠', '甜心', '糖果', '绿洲', '滚石', '蓝调',
    '红热辣椒', '数位', '黑色安息日', '恶魔', '娃娃脸', '绿洲', '滚石',
    '金属制品', '绿日', '脚趾', '嘴', '手指', '脸部', '身体',
    
    # 战锤40K角色名
    # 原体（Primarchs）
    '莱昂', '费鲁斯', '费拉克斯', '康拉德', '安格隆', '罗嘉', '马格努斯',
    '佩图拉博', '罗格', '荷鲁斯', '洛嘉', '莫塔里安', '阿尔法瑞斯', '基里曼',
    '多恩', '山阵', '可汗', '科尔法伦', '狼王', '圣吉列斯', '瓦坎德',
    '莱昂艾尔庄森', '费鲁斯马努斯', '费拉克斯', '康拉德科兹', '安格隆', '罗嘉奥瑞利安',
    '马格努斯红魔', '佩图拉博', '罗格多恩', '荷鲁斯', '洛嘉', '莫塔里安', '阿尔法瑞斯',
    '基里曼', '圣吉列斯', '瓦坎德', '可汗', '狼王', '科尔法伦', '山阵',
    
    # 星际战士/阿斯塔特
    '卡托西卡留斯', '马尔萨拉斯', '卡尔加', '泰图斯', '但丁', '米诺陶', '拉格纳',
    '乌列尔', '阿斯莫代', '阿兹瑞尔', '贝利萨留', '比约恩', '卢修斯', '阿巴顿',
    '西格蒙德', '兰多', '塔库斯', '加百列', '卡西乌斯', '马库斯', '提图斯',
    '泰瑞斯', '瑞文', '西多纽斯', '索拉法', '卢修斯', '法比乌斯', '阿赫曼',
    '萨拉菲斯', '埃泽凯尔', '阿斯塔特', '极限战士', '暗黑天使', '圣血天使',
    '太空野狼', '钢铁之手', '白色疤痕', '帝国之拳', '火蜥蜴', '乌鸦守卫',
    '铁勇士', '午夜领主', '吞世者', '怀言者', '千子', '死亡守卫', '钢铁战士',
    '阿尔法军团', '红魔', '帝皇之子', '黑军团', '混沌星际战士', '审判官',
    
    # 审判官和帝国角色
    '格雷法克斯', '艾森霍恩', '拉文诺', '斯特恩', '瓦尔普', '卡尔德', '凯恩',
    '雅瑞克', '高文', '兰斯洛特', '莫德雷德', '加拉哈德', '贝德维尔', '特里斯坦',
    '帕西瓦尔', '珀西瓦尔', '戈万', '艾森霍恩', '拉文诺', '斯特恩', '瓦尔普',
    
    # 异形和混沌角色
    '阿巴顿', '艾泽凯尔', '卢修斯', '法比乌斯', '阿赫曼', '卡恩', '西格蒙德',
    '虫族', '欧克', '灵族', '死灵', '钛族', '混沌', '恐虐', '奸奇',
    '纳垢', '色孽', '混沌之神', '混沌星际战士', '黑暗灵族', '灵族', '死灵',
    
    # 其他重要角色
    '帝皇', '基里曼', '莱昂', '多恩', '佩图拉博', '安格隆', '罗嘉', '马格努斯',
    '荷鲁斯', '洛嘉', '莫塔里安', '阿尔法瑞斯', '康拉德', '费鲁斯', '山阵',
    '可汗', '科尔法伦', '狼王', '圣吉列斯', '瓦坎德', '费拉克斯', '贝利萨留',
    '卡托西卡留斯', '马尔萨拉斯', '卡尔加', '泰图斯', '但丁', '米诺陶', '拉格纳',
    '乌列尔', '阿斯莫代', '阿兹瑞尔', '比约恩', '西格蒙德', '兰多', '塔库斯',
    '加百列', '卡西乌斯', '马库斯', '提图斯', '泰瑞斯', '瑞文', '西多纽斯',
    '索拉法', '法比乌斯', '阿赫曼', '萨拉菲斯', '埃泽凯尔', '格雷法克斯',
    '艾森霍恩', '拉文诺', '斯特恩', '瓦尔普', '卡尔德', '凯恩', '雅瑞克',
]


def get_random_username() -> str:
    """随机获取一个用户名（中药名、星宿名、星体名、JOJO替身名或战锤40K角色名）"""
    return random.choice(USER_NAMES)


class ImageDownloader:
    """图片下载器"""
    
    def __init__(self, download_dir: str = None):
        from pathlib import Path
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.download_dir = Path(download_dir or Config.DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def download_image(self, url: str, restaurant_id: str = None) -> Optional[str]:
        """下载图片并返回本地路径"""
        import requests
        from pathlib import Path
        
        try:
            if not url or not url.startswith(('http://', 'https://')):
                return None
            
            from urllib.parse import urlparse
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or '.jpg'
            
            if restaurant_id:
                filename = f"{restaurant_id}_{int(time.time())}{ext}"
            else:
                filename = f"img_{int(time.time())}_{random.randint(1000, 9999)}{ext}"
            
            filepath = self.download_dir / filename
            
            response = self.session.get(url, timeout=Config.CRAWLER_TIMEOUT, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"图片下载成功: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"下载图片失败 {url}: {str(e)}")
            return None
    
    def download_images(self, urls: List[str], restaurant_id: str = None) -> List[str]:
        """批量下载图片"""
        local_paths = []
        for url in urls:
            path = self.download_image(url, restaurant_id)
            if path:
                local_paths.append(path)
            time.sleep(Config.CRAWLER_DELAY)
        return local_paths


class XiaohongshuSeleniumCrawler:
    """小红书Selenium爬虫（模拟浏览器操作）"""
    
    def __init__(self):
        self.driver = None
        self.image_downloader = ImageDownloader()
        self.watermark_remover = WatermarkRemover()
        self.ai_paraphraser = AIParaphraser()
        
        # 初始化保存目录（逐条保存）
        from pathlib import Path
        from datetime import datetime
        self.save_dir = Path(Config.SAVE_DIR)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建时间戳目录（每次爬取会话使用同一个时间戳）
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.timestamp_dir = self.save_dir / self.timestamp
        self.timestamp_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建分类文件夹
        self.original_texts_dir = self.timestamp_dir / "原始文本"
        self.paraphrased_texts_dir = self.timestamp_dir / "转述文本"
        self.images_info_dir = self.timestamp_dir / "图片信息"
        self.json_dir = self.timestamp_dir / "JSON数据"
        
        self.original_texts_dir.mkdir(parents=True, exist_ok=True)
        self.paraphrased_texts_dir.mkdir(parents=True, exist_ok=True)
        self.images_info_dir.mkdir(parents=True, exist_ok=True)
        self.json_dir.mkdir(parents=True, exist_ok=True)
        
        # 计数器（用于文件名序号）
        self.restaurant_counter = 0
        
        # 数据库连接（延迟初始化）
        self._db = None
        self._db_initialized = False
        
        logger.info(f"初始化保存目录: {self.timestamp_dir}")
    
    def init_driver(self, headless: bool = False):
        """初始化浏览器驱动"""
        from pathlib import Path
        
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')  # 无头模式
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 设置User-Agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 窗口大小
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 保存用户数据目录（保持登录状态）
        user_data_dir = Path(__file__).parent / 'chrome_user_data'
        user_data_dir.mkdir(exist_ok=True)
        chrome_options.add_argument(f'--user-data-dir={user_data_dir.absolute()}')
        
        # 禁用密码保存提示
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 执行脚本隐藏webdriver特征
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            logger.info("浏览器驱动初始化成功")
            logger.info(f"用户数据目录: {user_data_dir.absolute()}")
            logger.info("提示: 如果首次运行，请手动登录小红书，登录状态会被保存")
        except Exception as e:
            logger.error(f"浏览器驱动初始化失败: {str(e)}")
            raise
    
    def close_driver(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def crawl_by_keyword(self, keyword: str, city: str = None, pages: int = 5, 
                        headless: bool = False, keep_browser_open: bool = True) -> List[Dict]:
        """
        使用Selenium爬取小红书
        
        Args:
            keyword: 搜索关键词
            city: 城市名称（可选）
            pages: 爬取页数
            headless: 是否无头模式
            keep_browser_open: 爬取完成后是否保持浏览器打开（默认True）
        """
        with CrawlerPerformanceTimer(f"crawl.{keyword}"):
            restaurants = []
            
            try:
                self.init_driver(headless=headless)
            
                # 构建搜索关键词
                search_keyword = keyword
                if city:
                    search_keyword = f"{city} {keyword}"
                
                logger.info(f"开始爬取小红书：关键词={search_keyword}")
                
                # 访问小红书
                self.driver.get("https://www.xiaohongshu.com")
                time.sleep(2 + random.uniform(0, 1))
                
                # 检查是否需要登录
                if not self._check_logged_in():
                    logger.warning("检测到未登录状态")
                    if not headless:
                        logger.info("="*60)
                        logger.info("请在小红书页面完成登录（扫码或密码登录）")
                        logger.info("登录完成后，程序将自动继续...")
                        logger.info("="*60)
                        # 等待用户登录（最多等待5分钟）
                        max_wait_time = 300  # 5分钟
                        wait_interval = 5  # 每5秒检查一次
                        waited_time = 0
                        while not self._check_logged_in() and waited_time < max_wait_time:
                            time.sleep(wait_interval)
                            waited_time += wait_interval
                            if waited_time % 30 == 0:  # 每30秒提示一次
                                logger.info(f"等待登录中... ({waited_time}/{max_wait_time}秒)")
                        
                        if not self._check_logged_in():
                            logger.error("登录超时，请重新运行程序")
                            raise Exception("登录超时")
                        else:
                            logger.info("登录成功！")
                    else:
                        logger.error("无头模式无法登录，请使用非无头模式首次登录")
                        raise Exception("无头模式需要先完成登录")
                
                # 模拟人类操作：随机滚动
                self._random_scroll()
                
                # 搜索
                with CrawlerPerformanceTimer("crawl.search"):
                    self._search_keyword(search_keyword)
                
                # 爬取多页
                for page in range(1, pages + 1):
                    logger.info(f"爬取第 {page} 页...")
                    
                    if page > 1:
                        # 滚动到底部加载更多
                        with CrawlerPerformanceTimer("crawl.scroll"):
                            self._scroll_to_bottom()
                        time.sleep(2)
                    
                    # 解析当前页面的笔记
                    with CrawlerPerformanceTimer("parse.page"):
                        notes = self._parse_notes_on_page()
                    logger.info(f"本页解析到 {len(notes)} 个笔记")
                    
                    parsed_count = 0
                    failed_count = 0
                    for note in notes:
                        try:
                            # 如果有URL，点击进入详情页获取完整内容
                            note_url = note.get('url', '')
                            if note_url:
                                logger.info(f"点击进入帖子详情页: {note_url[:50]}")
                                with CrawlerPerformanceTimer("parse.note_detail"):
                                    detail = self._get_note_detail(note_url)
                                    if detail:
                                        # 用详情页的完整内容替换列表页的预览内容
                                        note['title'] = detail.get('title', note.get('title', ''))
                                        note['content'] = detail.get('content', note.get('content', ''))
                                        # 合并图片（优先使用详情页的高清图）
                                        if detail.get('images'):
                                            note['images'] = detail['images']
                                        logger.info(f"✓ 获取到完整内容，长度: {len(note.get('content', ''))} 字符")
                                    else:
                                        logger.warning(f"⚠ 无法获取详情页内容，使用列表页预览内容")
                            else:
                                logger.warning(f"⚠ 笔记没有URL，使用列表页预览内容")
                            
                            # 解析笔记为餐厅信息
                            with CrawlerPerformanceTimer("parse.note"):
                                restaurant = self._parse_note(note, city)
                            if restaurant:
                                restaurants.append(restaurant)
                                parsed_count += 1
                                logger.debug(f"解析餐厅: {restaurant.get('name', 'Unknown')}")
                        except Exception as e:
                            failed_count += 1
                            logger.error(f"解析笔记失败，跳过该条数据: {str(e)}")
                            continue  # 跳过该条数据，继续处理下一条
                            
                        # 每个帖子处理完后稍作延迟，避免请求过快
                        time.sleep(random.uniform(0.5, 1.0))
                    
                    logger.info(f"本页成功解析 {parsed_count}/{len(notes)} 个餐厅，失败 {failed_count} 条")
                    
                    # 随机延迟
                    time.sleep(Config.CRAWLER_DELAY + random.uniform(1, 2))
                    
                    # 随机滚动（模拟浏览）
                    with CrawlerPerformanceTimer("crawl.random_scroll"):
                        self._random_scroll()
                
            except Exception as e:
                logger.error(f"爬取失败: {str(e)}", exc_info=True)
            finally:
                # 爬取完成后生成汇总文件
                if restaurants:
                    self._generate_summary(restaurants)
                
                if keep_browser_open:
                    logger.info("爬取完成，浏览器将保持打开状态（按Ctrl+C退出）")
                    logger.info("提示: 可以继续使用浏览器浏览小红书")
                    # 保持浏览器打开，但释放driver引用，让用户可以手动操作
                    # 注意：如果程序退出，浏览器仍然会关闭，但用户可以在退出前操作
                    try:
                        import signal
                        import sys
                        def signal_handler(sig, frame):
                            logger.info("\n正在关闭浏览器...")
                            self.close_driver()
                            sys.exit(0)
                        signal.signal(signal.SIGINT, signal_handler)
                        logger.info("按 Ctrl+C 退出程序")
                        # 保持程序运行
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        logger.info("\n正在关闭浏览器...")
                        self.close_driver()
                else:
                    self.close_driver()
            
            return restaurants
    
    def _search_keyword(self, keyword: str):
        """搜索关键词"""
        try:
            # 查找搜索框
            # 小红书搜索框的选择器可能需要根据实际页面调整
            search_selectors = [
                "input[placeholder*='搜索']",
                ".search-input",
                "#search-input",
                "input[type='search']",
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not search_input:
                logger.warning("找不到搜索框，尝试直接访问搜索URL")
                search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
                self.driver.get(search_url)
                time.sleep(3)
                return
            
            # 模拟人类输入：逐字符输入
            search_input.click()
            time.sleep(0.5)
            
            # 清空输入框
            search_input.clear()
            time.sleep(0.3)
            
            # 逐字符输入（模拟真实打字）
            for char in keyword:
                search_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            # 按回车或点击搜索按钮
            search_input.send_keys(Keys.RETURN)
            time.sleep(2 + random.uniform(0, 1))
            
            # 等待页面加载
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        try:
            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # 再滚动一点
            self.driver.execute_script("window.scrollBy(0, -200);")
            time.sleep(0.5)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"滚动失败: {str(e)}")
    
    def _check_logged_in(self) -> bool:
        """检查是否已登录小红书"""
        try:
            # 检查是否存在登录相关的元素（登录按钮、登录框等）
            login_selectors = [
                "input[placeholder*='手机号']",
                "input[placeholder*='账号']",
                ".login-button",
                ".login-btn",
                "[class*='login']",
                ".phone-login",
            ]
            
            # 如果找到登录相关元素，说明未登录
            for selector in login_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        return False
                except:
                    continue
            
            # 检查是否存在用户相关元素（已登录的特征）
            user_selectors = [
                "[class*='user']",
                "[class*='avatar']",
                ".user-info",
                ".user-avatar",
                "[data-user-id]",
            ]
            
            for selector in user_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        return True
                except:
                    continue
            
            # 检查URL，如果不在登录页面，可能已登录
            current_url = self.driver.current_url
            if 'login' not in current_url.lower() and 'passport' not in current_url.lower():
                return True
            
            return False
        except Exception as e:
            logger.debug(f"检查登录状态失败: {str(e)}")
            # 默认返回False，让用户手动确认
            return False
    
    def _random_scroll(self):
        """随机滚动（模拟人类浏览行为）"""
        try:
            scroll_amount = random.randint(300, 800)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))
        except:
            pass
    
    def _parse_notes_on_page(self) -> List[Dict]:
        """解析当前页面的笔记"""
        notes = []
        
        try:
            # 等待笔记加载
            time.sleep(2)
            
            # 小红书笔记的选择器（需要根据实际页面结构调整）
            note_selectors = [
                ".note-item",
                ".feed-item",
                ".note-card",
                "[data-note-id]",
                ".note-wrapper",
            ]
            
            note_elements = []
            for selector in note_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        note_elements = elements
                        logger.info(f"找到 {len(elements)} 个笔记（使用选择器: {selector}）")
                        break
                except:
                    continue
            
            if not note_elements:
                logger.warning("未找到笔记元素，尝试通用选择器")
                # 尝试通用的笔记容器
                note_elements = self.driver.find_elements(By.CSS_SELECTOR, "article, .note, [class*='note']")
            
            for element in note_elements[:20]:  # 限制每次最多20个
                try:
                    # 滚动到元素可见
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(0.3)
                    
                    note = self._extract_note_from_element(element)
                    if note:
                        notes.append(note)
                        
                except Exception as e:
                    logger.debug(f"解析单个笔记失败: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"解析笔记列表失败: {str(e)}")
        
        return notes
    
    def _extract_note_from_element(self, element) -> Optional[Dict]:
        """从元素中提取笔记信息（列表页预览）"""
        try:
            note = {}
            
            # 标题（尝试多种选择器）
            title_elem = element.find_elements(By.CSS_SELECTOR, ".title, .note-title, h3, h4, h2, [class*='title'], [class*='Title']")
            if not title_elem:
                # 尝试获取元素的文本内容
                title_elem = element.find_elements(By.CSS_SELECTOR, "a[class*='title'], div[class*='title']")
            note['title'] = title_elem[0].text.strip() if title_elem else ''
            
            # 内容（列表页预览内容，通常是缩略的）
            content_elem = element.find_elements(By.CSS_SELECTOR, ".content, .note-content, .desc, .description, [class*='content'], [class*='Content'], p")
            if not content_elem:
                # 尝试获取整个元素的文本
                full_text = element.text.strip()
                note['content'] = full_text
            else:
                note['content'] = content_elem[0].text.strip() if content_elem else ''
            
            # 图片（列表页预览图）
            img_elements = element.find_elements(By.CSS_SELECTOR, "img")
            note['images'] = []
            for img in img_elements[:5]:  # 最多5张图
                img_url = img.get_attribute('src') or img.get_attribute('data-src')
                if img_url and img_url.startswith('http'):
                    note['images'].append(img_url)
            
            # 链接（关键：获取帖子详情页链接）
            link_elem = element.find_elements(By.CSS_SELECTOR, "a")
            if link_elem:
                href = link_elem[0].get_attribute('href')
                # 确保URL完整（如果是相对路径，添加域名）
                if href:
                    if href.startswith('/'):
                        note['url'] = 'https://www.xiaohongshu.com' + href
                    elif href.startswith('http'):
                        note['url'] = href
                    else:
                        note['url'] = 'https://www.xiaohongshu.com/' + href
                else:
                    note['url'] = ''
            else:
                note['url'] = ''
            
            if note['title'] or note['content'] or note['url']:
                return note
            
        except Exception as e:
            logger.debug(f"提取笔记信息失败: {str(e)}")
        
        return None
    
    def _get_note_detail(self, note_url: str) -> Optional[Dict]:
        """点击进入帖子详情页获取完整内容"""
        if not note_url:
            return None
        
        try:
            # 保存当前窗口句柄和URL
            original_window = self.driver.current_window_handle
            original_url = self.driver.current_url
            
            # 确保URL完整
            if not note_url.startswith('http'):
                if note_url.startswith('/'):
                    note_url = 'https://www.xiaohongshu.com' + note_url
                else:
                    note_url = 'https://www.xiaohongshu.com/' + note_url
            
            logger.debug(f"访问帖子详情页: {note_url}")
            
            # 在新标签页打开帖子详情页
            try:
                self.driver.execute_script(f"window.open('{note_url}', '_blank');")
                time.sleep(2)
            except:
                # 如果新标签页打开失败，直接跳转
                self.driver.get(note_url)
                time.sleep(3)
            
            # 切换到新标签页
            windows = self.driver.window_handles
            if len(windows) > 1:
                self.driver.switch_to.window(windows[-1])
            else:
                # 如果新标签页没有打开，直接跳转
                self.driver.get(note_url)
                time.sleep(3)
            
            # 等待页面加载
            time.sleep(2)
            
            # 滚动页面以加载完整内容
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            detail = {}
            
            # 获取完整标题
            title_selectors = [
                ".title",
                ".note-title",
                "h1",
                "h2",
                "[class*='title']",
                "[class*='Title']",
                ".note-detail-title"
            ]
            for selector in title_selectors:
                try:
                    title_elem = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if title_elem and title_elem[0].text.strip():
                        detail['title'] = title_elem[0].text.strip()
                        break
                except:
                    continue
            
            # 获取完整内容
            content_selectors = [
                ".content",
                ".note-content",
                ".desc",
                ".description",
                ".note-detail",
                "[class*='content']",
                "[class*='Content']",
                ".note-text",
                "article p",
                ".note-body"
            ]
            full_content = ""
            for selector in content_selectors:
                try:
                    content_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if content_elems:
                        # 合并所有段落
                        paragraphs = [elem.text.strip() for elem in content_elems if elem.text.strip()]
                        if paragraphs:
                            full_content = "\n".join(paragraphs)
                            break
                except:
                    continue
            
            # 如果还是没找到，尝试获取整个文章标签的文本
            if not full_content:
                try:
                    article_elem = self.driver.find_elements(By.CSS_SELECTOR, "article, .note-detail, .note-wrapper")
                    if article_elem:
                        full_content = article_elem[0].text.strip()
                except:
                    pass
            
            detail['content'] = full_content
            
            # 获取完整图片（详情页的图片通常是高清的）
            img_elements = self.driver.find_elements(By.CSS_SELECTOR, "img")
            detail['images'] = []
            for img in img_elements:
                try:
                    img_url = img.get_attribute('src') or img.get_attribute('data-src') or img.get_attribute('data-original')
                    if img_url and img_url.startswith('http') and 'xiaohongshu' in img_url:
                        # 过滤掉头像、图标等小图
                        img_width = img.get_attribute('width')
                        img_height = img.get_attribute('height')
                        if img_width and img_height:
                            try:
                                if int(img_width) > 100 and int(img_height) > 100:
                                    detail['images'].append(img_url)
                            except:
                                detail['images'].append(img_url)
                        else:
                            detail['images'].append(img_url)
                except:
                    continue
            
            # 去重并限制数量
            detail['images'] = list(dict.fromkeys(detail['images']))[:10]  # 最多10张
            
            # 关闭当前标签页，返回列表页
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(original_window)
            else:
                # 如果没有多个标签页，返回上一页
                self.driver.back()
                time.sleep(2)
            
            # 等待页面恢复
            time.sleep(1)
            
            if detail.get('title') or detail.get('content'):
                logger.debug(f"✓ 成功获取帖子详情: {detail.get('title', '')[:30]}")
                return detail
            else:
                logger.warning(f"无法获取帖子详情内容，URL: {note_url[:50]}")
                return None
                
        except Exception as e:
            logger.error(f"获取帖子详情失败 {note_url[:50]}: {str(e)}")
            # 确保返回原窗口
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                else:
                    self.driver.back()
                    time.sleep(2)
            except:
                pass
            return None
    
    def _parse_note(self, note: Dict, city: str = None) -> Optional[Dict]:
        """解析笔记为餐厅信息"""
        try:
            title = note.get('title', '')
            content = note.get('content', '')
            images = note.get('images', [])
            
            # 提取餐厅名称（放宽条件，即使没有匹配到也使用标题）
            restaurant_name = self._extract_restaurant_name(title, content)
            if not restaurant_name:
                # 如果还是提取不到，至少使用标题或内容的前20个字符
                if title:
                    restaurant_name = title[:20].strip()
                elif content:
                    restaurant_name = content[:20].strip()
                else:
                    logger.debug(f"跳过空笔记: title={title[:50]}, content={content[:50]}")
                    return None
            
            # 提取地址
            address = self._extract_address(content, city)
            
            # 使用AI同时完成转述和分类
            original_content = content or title
            logger.info(f"开始AI转述和分类: {restaurant_name}")
            
            # 添加请求间隔，避免并发过多导致超时
            time.sleep(0.5)  # 每次AI请求前等待0.5秒
            
            try:
                with CrawlerPerformanceTimer("ai.paraphrase_and_classify"):
                    ai_result = self.ai_paraphraser.paraphrase_and_classify(original_content, restaurant_name)
                paraphrased_content = ai_result['paraphrased']
                restaurant_type_info = {
                    'parent_id': ai_result['parent_id'],
                    'child_ids': ai_result['child_ids']
                }
            except Exception as e:
                # AI失败时直接抛出异常，不继续处理该条数据
                error_msg = str(e)
                logger.error(f"AI转述和分类失败，跳过该条数据: {error_msg}")
                
                # 记录错误到性能监控
                monitor = get_crawler_performance_monitor()
                monitor.record_metric("ai.error", 1.0, {
                    'error_type': type(e).__name__,
                    'restaurant_name': restaurant_name[:30],
                    'error_message': error_msg[:200]
                })
                
                raise  # 重新抛出异常，让调用者处理
            
            # 转述描述（简短版本）
            description = self._extract_description(content)
            if description and len(description) > 20:
                # 添加请求间隔
                time.sleep(0.3)
                with CrawlerPerformanceTimer("ai.paraphrase"):
                    paraphrased_description = self.ai_paraphraser.paraphrase(description)
            else:
                paraphrased_description = paraphrased_content[:100] if paraphrased_content else title[:100]
            
            # 处理图片：下载并去除水印
            processed_images = []
            for img_url in images[:5]:
                try:
                    if img_url.startswith(('http://', 'https://')):
                        # 下载图片
                        with CrawlerPerformanceTimer("image.download"):
                            local_path = self.image_downloader.download_image(img_url)
                        if local_path:
                            # 去除水印
                            with CrawlerPerformanceTimer("image.remove_watermark"):
                                clean_path = self.watermark_remover.remove_watermark(local_path)
                            # 保存处理后的图片路径（或上传到服务器后返回URL）
                            processed_images.append(clean_path)
                        else:
                            logger.warning(f"图片下载失败，跳过: {img_url}")
                    else:
                        # 已经是本地路径，直接去除水印
                        with CrawlerPerformanceTimer("image.remove_watermark"):
                            clean_path = self.watermark_remover.remove_watermark(img_url)
                        processed_images.append(clean_path)
                except Exception as e:
                    logger.error(f"处理图片失败 {img_url}: {str(e)}")
                    # 如果处理失败，保留原始URL
                    if img_url.startswith(('http://', 'https://')):
                        processed_images.append(img_url)
            
            restaurant = {
                'name': restaurant_name,
                'address': address or (city or ''),
                'description': paraphrased_description,  # 使用转述后的描述
                'content': paraphrased_content,  # 使用转述后的内容
                'original_content': original_content,  # 保留原文用于调试
                'type_info': restaurant_type_info,  # AI返回的类型信息
                'images': processed_images,  # 处理后的图片（去除水印）
                'source': 'xiaohongshu',
            }
            
            # 逐条保存：立即保存原始文本和转述文本（分开保存）
            self._save_single_restaurant(restaurant)
            
            # 逐条上传：立即上传到数据库
            with CrawlerPerformanceTimer("database.upload.single"):
                try:
                    self._upload_single_restaurant(restaurant)
                except Exception as e:
                    logger.error(f"上传餐厅 {restaurant_name} 到数据库失败: {str(e)}")
                    # 上传失败不影响继续爬取，只记录错误
                    # 如果希望上传失败时停止，可以取消下面的注释：
                    # raise
            
            logger.info(f"✓ 解析餐厅: {restaurant_name} - 类型: {restaurant_type_info['child_ids']} - {len(processed_images)}张图片已处理")
            return restaurant
            
        except Exception as e:
            logger.error(f"解析笔记失败: {str(e)}", exc_info=True)
            return None
    
    def _save_single_restaurant(self, restaurant: Dict):
        """逐条保存餐厅数据（原始文本和转述文本分开保存）"""
        try:
            self.restaurant_counter += 1
            
            restaurant_name = restaurant.get('name', f'restaurant_{self.restaurant_counter}')
            # 清理文件名（移除特殊字符）
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', restaurant_name)[:50]
            
            # 生成唯一文件名（包含时间戳和序号）
            file_suffix = f"_{self.timestamp}_{self.restaurant_counter:03d}"
            
            # 1. 保存原始文本到"原始文本"文件夹（单独文件）
            original_content = restaurant.get('original_content', '')
            if original_content:
                original_file = self.original_texts_dir / f"{safe_name}{file_suffix}.txt"
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(f"餐厅名称: {restaurant_name}\n")
                    f.write(f"地址: {restaurant.get('address', '')}\n")
                    f.write(f"来源: {restaurant.get('source', '')}\n")
                    f.write("="*60 + "\n")
                    f.write("原始文本:\n")
                    f.write("="*60 + "\n")
                    f.write(original_content)
                    f.write("\n")
                logger.debug(f"✓ 原始文本已保存: {original_file.name}")
            
            # 2. 保存转述后的文本到"转述文本"文件夹（单独文件）
            paraphrased_content = restaurant.get('content', '')
            paraphrased_description = restaurant.get('description', '')
            if paraphrased_content or paraphrased_description:
                paraphrased_file = self.paraphrased_texts_dir / f"{safe_name}{file_suffix}.txt"
                with open(paraphrased_file, 'w', encoding='utf-8') as f:
                    f.write(f"餐厅名称: {restaurant_name}\n")
                    f.write(f"地址: {restaurant.get('address', '')}\n")
                    f.write(f"来源: {restaurant.get('source', '')}\n")
                    
                    # 类型信息
                    if 'type_info' in restaurant:
                        type_info = restaurant['type_info']
                        f.write(f"类型ID: parent={type_info.get('parent_id')}, children={type_info.get('child_ids')}\n")
                    
                    f.write("="*60 + "\n")
                    f.write("转述后的描述:\n")
                    f.write("="*60 + "\n")
                    f.write(paraphrased_description)
                    f.write("\n\n")
                    f.write("="*60 + "\n")
                    f.write("转述后的内容:\n")
                    f.write("="*60 + "\n")
                    f.write(paraphrased_content)
                    f.write("\n")
                logger.debug(f"✓ 转述文本已保存: {paraphrased_file.name}")
            
            # 3. 保存图片路径信息
            images = restaurant.get('images', [])
            if images:
                images_file = self.images_info_dir / f"{safe_name}{file_suffix}_图片路径.txt"
                with open(images_file, 'w', encoding='utf-8') as f:
                    f.write(f"餐厅名称: {restaurant_name}\n")
                    f.write(f"图片数量: {len(images)}\n")
                    f.write("="*60 + "\n")
                    f.write("图片路径列表:\n")
                    f.write("="*60 + "\n")
                    for i, img_path in enumerate(images, 1):
                        f.write(f"{i}. {img_path}\n")
                logger.debug(f"✓ 图片信息已保存: {images_file.name}")
            
        except Exception as e:
            logger.error(f"保存单条数据失败: {str(e)}", exc_info=True)
    
    def _generate_summary(self, restaurants: List[Dict]):
        """生成汇总文件（爬取完成后）"""
        try:
            from datetime import datetime
            
            # 保存JSON数据
            json_filename = f"restaurants_{self.timestamp}.json"
            json_file = self.json_dir / json_filename
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(restaurants, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ JSON数据已保存: {json_file}")
            
            # 生成汇总信息
            summary_filename = f"汇总信息_{self.timestamp}.txt"
            summary_file = self.timestamp_dir / summary_filename
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("="*60 + "\n")
                f.write("爬取数据汇总\n")
                f.write("="*60 + "\n")
                f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"餐厅总数: {len(restaurants)}\n")
                f.write(f"图片总数: {sum(len(r.get('images', [])) for r in restaurants)}\n")
                f.write(f"保存目录: {self.timestamp_dir.absolute()}\n")
                f.write("\n" + "="*60 + "\n")
                f.write("餐厅列表:\n")
                f.write("="*60 + "\n")
                for idx, restaurant in enumerate(restaurants, 1):
                    f.write(f"\n{idx}. {restaurant.get('name', 'Unknown')}\n")
                    f.write(f"   地址: {restaurant.get('address', '')}\n")
                    f.write(f"   图片数: {len(restaurant.get('images', []))}\n")
                    if 'type_info' in restaurant:
                        f.write(f"   类型: {restaurant['type_info'].get('child_ids', [])}\n")
            
            logger.info(f"✓ 汇总信息已保存: {summary_file}")
            logger.info(f"✓ 所有数据已保存到目录: {self.timestamp_dir.absolute()}")
            
        except Exception as e:
            logger.error(f"生成汇总文件失败: {str(e)}", exc_info=True)
    
    def _init_database(self):
        """初始化数据库连接（延迟加载）"""
        if not self._db_initialized:
            try:
                from database import db
                self._db = db
                self._db_initialized = True
                logger.debug("数据库连接初始化成功")
            except Exception as e:
                logger.error(f"数据库连接初始化失败: {str(e)}")
                raise
    
    def _upload_single_restaurant(self, restaurant: Dict):
        """逐条上传餐厅数据到数据库"""
        try:
            # 延迟初始化数据库连接
            self._init_database()
            
            # 使用AI返回的类型信息（如果存在）
            if 'type_info' not in restaurant:
                raise ValueError(f"餐厅 {restaurant.get('name')} 缺少类型信息")
            
            parent_id = restaurant['type_info']['parent_id']
            child_ids = restaurant['type_info']['child_ids']
            child_ids_str = ','.join(map(str, child_ids))
            
            logger.debug(f"上传到数据库: {restaurant.get('name')} -> pid={parent_id}, cids={child_ids_str}")
            
            # 处理图片
            images = restaurant.get('images', [])
            if isinstance(images, str):
                try:
                    images = json.loads(images)
                except:
                    images = [img.strip() for img in images.split(',') if img.strip()]
            
            if not isinstance(images, list):
                images = []
            
            # 如果图片是本地路径，转换为URL或保持路径
            # 如果图片是URL，保持URL
            processed_images = []
            for img in images[:5]:
                if img:
                    processed_images.append(img)
            
            # 转换为JSON数组字符串
            images_json = json.dumps(processed_images, ensure_ascii=False)
            
            # 准备数据
            tweet_data = {
                'tweets_type_pid': parent_id,
                'tweets_type_cid': child_ids_str,
                'tweets_title': restaurant.get('name', '')[:120],
                'tweets_user': get_random_username()[:20],  # 使用随机用户名
                'tweets_describe': restaurant.get('description', '')[:400],
                'tweets_img': images_json[:300],
                'tweets_content': restaurant.get('content', '')[:2000],
            }
            
            # 验证必填字段
            if not tweet_data['tweets_title'] or not tweet_data['tweets_type_pid']:
                raise ValueError(f"无效数据: name={restaurant.get('name')}, title={tweet_data['tweets_title']}, pid={tweet_data['tweets_type_pid']}")
            
            # 插入数据库
            with CrawlerPerformanceTimer("database.upload.single"):
                query = """
                    INSERT INTO tweets (
                        tweets_type_pid, tweets_type_cid, tweets_title, tweets_user,
                        tweets_describe, tweets_img, tweets_content
                    ) VALUES (
                        :tweets_type_pid, :tweets_type_cid, :tweets_title, :tweets_user,
                        :tweets_describe, :tweets_img, :tweets_content
                    )
                """
                
                rows_affected = self._db.execute_update(query, tweet_data)
                if rows_affected > 0:
                    logger.info(f"✓ 上传成功: {tweet_data['tweets_title']}")
                else:
                    raise Exception(f"上传失败（无影响行数）: {tweet_data['tweets_title']}")
                    
        except Exception as e:
            logger.error(f"上传餐厅 {restaurant.get('name')} 到数据库失败: {str(e)}")
            raise  # 重新抛出异常，让调用者决定如何处理
    
    def _extract_restaurant_name(self, title: str, content: str) -> str:
        """提取餐厅名称"""
        text = f"{title} {content}"
        
        patterns = [
            r'【(.+?)】',
            r'「(.+?)」',
            r'《(.+?)》',
            r'(.+?)(餐厅|店|馆|食府|酒楼)',
            r'(.+?)(美食|菜|料理|火锅|烧烤|小吃)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text[:200])
            if match:
                name = match.group(1).strip()
                if len(name) > 1 and len(name) < 50:
                    return name
        
        # 如果标题不为空，直接使用标题（前30个字符）
        if title and len(title.strip()) > 0:
            return title[:30].strip()
        
        # 如果内容不为空，尝试提取前20个字符作为名称
        if content and len(content.strip()) > 0:
            # 移除常见的无用字符
            name = content[:30].strip()
            name = re.sub(r'[【】「」《》\s]+', '', name)
            if len(name) > 1:
                return name[:20]
        
        return ''
    
    def _extract_address(self, content: str, city: str = None) -> str:
        """提取地址"""
        address_patterns = [
            r'地址[：:]\s*(.+?)(?:\n|$)',
            r'位置[：:]\s*(.+?)(?:\n|$)',
            r'📍\s*(.+?)(?:\n|$)',
            r'(.+?[路|街|道|区|号].+?)(?:\n|$)',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, content)
            if match:
                address = match.group(1).strip()
                if city and city not in address:
                    address = f"{city}{address}"
                return address
        
        return city or ''
    
    def _extract_description(self, content: str) -> str:
        """提取描述"""
        if content:
            desc = re.sub(r'\s+', ' ', content[:200]).strip()
            return desc
        return ''


def save_to_file(restaurants: List[Dict], output_file: str, format_type: str = 'json'):
    """保存餐厅数据到文件（包含原始文本、转述文本和图片路径）"""
    if not restaurants:
        logger.warning("没有数据需要保存")
        return None
    
    try:
        from pathlib import Path
        from datetime import datetime
        
        # 创建保存目录
        save_dir = Path(Config.SAVE_DIR)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建时间戳目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_dir = save_dir / timestamp
        timestamp_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建不同的文件夹用于分类保存
        original_texts_dir = timestamp_dir / "原始文本"
        paraphrased_texts_dir = timestamp_dir / "转述文本"
        images_info_dir = timestamp_dir / "图片信息"
        json_dir = timestamp_dir / "JSON数据"
        
        original_texts_dir.mkdir(parents=True, exist_ok=True)
        paraphrased_texts_dir.mkdir(parents=True, exist_ok=True)
        images_info_dir.mkdir(parents=True, exist_ok=True)
        json_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 保存完整的JSON数据（包含所有信息）
        json_filename = f"restaurants_{timestamp}.json"
        json_file = json_dir / json_filename if not output_file.startswith('/') else Path(output_file)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(restaurants, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ 完整数据已保存到JSON文件: {json_file}")
        
        # 2. 为每个餐厅保存单独的文本文件
        for idx, restaurant in enumerate(restaurants):
            restaurant_name = restaurant.get('name', f'restaurant_{idx+1}')
            # 清理文件名（移除特殊字符）
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', restaurant_name)[:50]
            
            # 生成唯一文件名（包含时间戳和序号）
            file_suffix = f"_{timestamp}_{idx+1:03d}"
            
            # 保存原始文本到"原始文本"文件夹
            original_content = restaurant.get('original_content', '')
            if original_content:
                original_file = original_texts_dir / f"{safe_name}{file_suffix}.txt"
                with open(original_file, 'w', encoding='utf-8') as f:
                    f.write(f"餐厅名称: {restaurant_name}\n")
                    f.write(f"地址: {restaurant.get('address', '')}\n")
                    f.write(f"来源: {restaurant.get('source', '')}\n")
                    f.write("="*60 + "\n")
                    f.write("原始文本:\n")
                    f.write("="*60 + "\n")
                    f.write(original_content)
                    f.write("\n")
            
            # 保存转述后的文本到"转述文本"文件夹
            paraphrased_content = restaurant.get('content', '')
            paraphrased_description = restaurant.get('description', '')
            if paraphrased_content or paraphrased_description:
                paraphrased_file = paraphrased_texts_dir / f"{safe_name}{file_suffix}.txt"
                with open(paraphrased_file, 'w', encoding='utf-8') as f:
                    f.write(f"餐厅名称: {restaurant_name}\n")
                    f.write(f"地址: {restaurant.get('address', '')}\n")
                    f.write(f"来源: {restaurant.get('source', '')}\n")
                    
                    # 类型信息
                    if 'type_info' in restaurant:
                        type_info = restaurant['type_info']
                        f.write(f"类型ID: parent={type_info.get('parent_id')}, children={type_info.get('child_ids')}\n")
                    
                    f.write("="*60 + "\n")
                    f.write("转述后的描述:\n")
                    f.write("="*60 + "\n")
                    f.write(paraphrased_description)
                    f.write("\n\n")
                    f.write("="*60 + "\n")
                    f.write("转述后的内容:\n")
                    f.write("="*60 + "\n")
                    f.write(paraphrased_content)
                    f.write("\n")
            
            # 记录图片路径到"图片信息"文件夹
            images = restaurant.get('images', [])
            if images:
                images_file = images_info_dir / f"{safe_name}{file_suffix}_图片路径.txt"
                with open(images_file, 'w', encoding='utf-8') as f:
                    f.write(f"餐厅名称: {restaurant_name}\n")
                    f.write(f"图片数量: {len(images)}\n")
                    f.write("="*60 + "\n")
                    f.write("图片路径列表:\n")
                    f.write("="*60 + "\n")
                    for i, img_path in enumerate(images, 1):
                        f.write(f"{i}. {img_path}\n")
        
        # 3. 保存汇总信息
        summary_filename = f"汇总信息_{timestamp}.txt"
        summary_file = timestamp_dir / summary_filename
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("爬取数据汇总\n")
            f.write("="*60 + "\n")
            f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"餐厅总数: {len(restaurants)}\n")
            f.write(f"图片总数: {sum(len(r.get('images', [])) for r in restaurants)}\n")
            f.write("\n" + "="*60 + "\n")
            f.write("餐厅列表:\n")
            f.write("="*60 + "\n")
            for idx, restaurant in enumerate(restaurants, 1):
                f.write(f"\n{idx}. {restaurant.get('name', 'Unknown')}\n")
                f.write(f"   地址: {restaurant.get('address', '')}\n")
                f.write(f"   图片数: {len(restaurant.get('images', []))}\n")
                if 'type_info' in restaurant:
                    f.write(f"   类型: {restaurant['type_info'].get('child_ids', [])}\n")
        
        logger.info(f"✓ 原始文本已保存到: {original_texts_dir}")
        logger.info(f"✓ 转述文本已保存到: {paraphrased_texts_dir}")
        logger.info(f"✓ 图片信息已保存到: {images_info_dir}")
        logger.info(f"✓ 汇总信息已保存到: {summary_file}")
        logger.info(f"✓ 所有数据已保存到目录: {timestamp_dir}")
        
        # 如果指定了CSV格式，也保存CSV
        if format_type.lower() == 'csv':
            csv_filename = f"restaurants_{timestamp}.csv"
            csv_file = json_dir / csv_filename
            import csv
            fieldnames = ['name', 'address', 'description', 'content', 'original_content', 'images', 'source', 'type_info']
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in restaurants:
                    row = {k: v for k, v in r.items() if k in fieldnames}
                    row['images'] = ','.join(row.get('images', []))
                    row['type_info'] = json.dumps(row.get('type_info', {}), ensure_ascii=False)
                    writer.writerow(row)
            logger.info(f"✓ CSV文件已保存到: {csv_file}")
        
        # 打印完整路径给用户
        print(f"\n{'='*60}")
        print(f"数据已保存到本地:")
        print(f"  完整路径: {timestamp_dir.absolute()}")
        print(f"  原始文本: {original_texts_dir.absolute()}")
        print(f"  转述文本: {paraphrased_texts_dir.absolute()}")
        print(f"  图片信息: {images_info_dir.absolute()}")
        print(f"  JSON数据: {json_dir.absolute()}")
        print(f"  汇总信息: {summary_file.absolute()}")
        print(f"{'='*60}\n")
        
        return str(timestamp_dir.absolute())
            
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}", exc_info=True)
        raise


def upload_to_database(restaurants: List[Dict]):
    """上传餐厅数据到数据库"""
    if not restaurants:
        logger.warning("没有数据需要上传")
        return
    
    with CrawlerPerformanceTimer(f"database.upload.{len(restaurants)}"):
        try:
            # 导入数据库模块（现在在同一目录下）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, current_dir)
            from database import db
            from config import Config as BatchConfig
            
            logger.info("数据库模块导入成功，开始上传数据...")
            
            # 处理每个餐厅
            success_count = 0
            for restaurant in restaurants:
                try:
                    # 使用AI返回的类型信息（如果存在）
                    if 'type_info' in restaurant:
                        parent_id = restaurant['type_info']['parent_id']
                        child_ids = restaurant['type_info']['child_ids']
                    else:
                        # 如果没有类型信息，跳过该条数据
                        logger.error(f"餐厅 {restaurant.get('name')} 缺少类型信息，跳过该条数据")
                        continue  # 跳过这条数据，不插入数据库
                    
                    child_ids_str = ','.join(map(str, child_ids))
                    
                    logger.debug(f"使用类型: {restaurant.get('name')} -> pid={parent_id}, cids={child_ids_str}")
                    
                    # 处理图片
                    images = restaurant.get('images', [])
                    if isinstance(images, str):
                        try:
                            images = json.loads(images)
                        except:
                            images = [img.strip() for img in images.split(',') if img.strip()]
                    
                    if not isinstance(images, list):
                        images = []
                    
                    # 如果图片是本地路径，转换为URL或保持路径
                    # 如果图片是URL，保持URL
                    processed_images = []
                    for img in images[:5]:
                        if img:
                            # 如果是本地路径，可以上传到服务器或保持路径
                            # 这里暂时保持原样（如果是本地路径，数据库存储路径；如果是URL，存储URL）
                            processed_images.append(img)
                    
                    # 转换为JSON数组字符串
                    images_json = json.dumps(processed_images, ensure_ascii=False)
                    
                    # 准备数据
                    tweet_data = {
                        'tweets_type_pid': parent_id,
                        'tweets_type_cid': child_ids_str,
                        'tweets_title': restaurant.get('name', '')[:120],
                        'tweets_user': get_random_username()[:20],  # 使用随机用户名（中药名、星宿名或星体名）
                        'tweets_describe': restaurant.get('description', '')[:400],
                        'tweets_img': images_json[:300],
                        'tweets_content': restaurant.get('content', '')[:2000],
                    }
                    
                    # 验证必填字段
                    if not tweet_data['tweets_title'] or not tweet_data['tweets_type_pid']:
                        logger.warning(f"跳过无效数据: name={restaurant.get('name')}, title={tweet_data['tweets_title']}, pid={tweet_data['tweets_type_pid']}")
                        continue
                    
                    # 插入数据库
                    query = """
                        INSERT INTO tweets (
                            tweets_type_pid, tweets_type_cid, tweets_title, tweets_user,
                            tweets_describe, tweets_img, tweets_content
                        ) VALUES (
                            :tweets_type_pid, :tweets_type_cid, :tweets_title, :tweets_user,
                            :tweets_describe, :tweets_img, :tweets_content
                        )
                    """
                    
                    rows_affected = db.execute_update(query, tweet_data)
                    if rows_affected > 0:
                        success_count += 1
                        logger.debug(f"✓ 上传成功: {tweet_data['tweets_title']}")
                    else:
                        logger.warning(f"✗ 上传失败（无影响行数）: {tweet_data['tweets_title']}")
                
                except Exception as e:
                    logger.error(f"上传餐厅失败 {restaurant.get('name')}: {str(e)}")
                    continue
            
            logger.info(f"成功上传 {success_count}/{len(restaurants)} 条数据")
            
        except Exception as e:
            logger.error(f"上传数据库失败: {str(e)}", exc_info=True)
            raise


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="小红书Selenium爬虫（模拟浏览器）")
    parser.add_argument('--keyword', required=True, help='搜索关键词，如：深圳美食、潮汕菜')
    parser.add_argument('--city', help='城市名称，如：深圳')
    parser.add_argument('--pages', type=int, default=5, help='爬取页数（默认：5）')
    parser.add_argument('--headless', action='store_true', help='无头模式（后台运行）')
    parser.add_argument('--output', default='restaurants.json', help='输出文件')
    parser.add_argument('--upload', action='store_true', help='直接上传到数据库')
    parser.add_argument('--both', action='store_true', help='既保存文件又上传')
    
    args = parser.parse_args()
    
    try:
        crawler = XiaohongshuSeleniumCrawler()
        
        logger.info(f"开始爬取小红书（Selenium模式）：关键词={args.keyword}")
        
        # 启动实时性能监控显示
        real_time_display = get_real_time_display(update_interval=2.0)
        real_time_display.start()
        
        print("\n" + "="*60)
        print("📊 实时性能监控已启动（每2秒自动更新）")
        print("="*60 + "\n")
        
        try:
            restaurants = crawler.crawl_by_keyword(
                keyword=args.keyword,
                city=args.city,
                pages=args.pages,
                headless=args.headless,
                keep_browser_open=True  # 默认保持浏览器打开
            )
        finally:
            # 停止实时显示
            real_time_display.stop()
        
        if not restaurants:
            print("没有获取到餐厅数据")
            print("\n提示：")
            print("1. 可能需要登录小红书账号")
            print("2. 可以尝试使用非无头模式查看浏览器操作")
            print("3. 检查网络连接和浏览器是否正常")
            sys.exit(1)
        
        logger.info(f"共获取 {len(restaurants)} 条餐厅数据")
        
        # 注意：数据已经逐条保存和上传（原始文本和转述文本分开保存）
        # 爬取过程中，每条数据都会立即：
        # 1. 保存到本地文件（原始文本和转述文本分开）
        # 2. 上传到数据库
        logger.info("✓ 所有数据已逐条保存（原始文本和转述文本分开）")
        logger.info("✓ 所有数据已逐条上传到数据库")
        
        # 打印前几条数据示例用于调试
        if restaurants:
            logger.info("数据示例（前3条）：")
            for i, r in enumerate(restaurants[:3]):
                logger.info(f"  {i+1}. {r.get('name', 'Unknown')} - {r.get('description', '')[:50]}")
        
        # 汇总文件已在爬取完成时生成
        logger.info(f"✓ 汇总文件已生成: {crawler.timestamp_dir / f'汇总信息_{crawler.timestamp}.txt'}")
        
        # 显示详细性能统计
        print("\n" + "="*80)
        print("📊 爬取完成！性能统计报告")
        print("="*80)
        from performance_monitor import get_crawler_performance_monitor
        monitor = get_crawler_performance_monitor()
        summary = monitor.get_summary()
        all_stats = monitor.get_all_statistics()
        
        # 总体统计
        print(f"\n【总体统计】")
        print(f"  总操作数: {summary.get('total_operations', 0)}")
        print(f"  总耗时: {summary.get('total_time', 0):.2f}秒")
        print(f"  平均每次操作耗时: {summary.get('avg_time_per_operation', 0):.3f}秒")
        print(f"  当前内存使用: {summary.get('current_memory_mb', 0):.2f} MB")
        print(f"  当前CPU使用率: {summary.get('current_cpu_percent', 0):.2f}%")
        
        # 爬虫操作统计
        print(f"\n【爬虫操作统计】")
        crawl_ops = {k: v for k, v in all_stats.items() if k.startswith('crawl.')}
        for op_name, op_stats in sorted(crawl_ops.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            print(f"  {op_name}: {count}次, 平均{avg:.3f}秒/次, 总计{total:.2f}秒")
        
        # AI操作统计
        print(f"\n【AI操作统计】")
        ai_ops = {k: v for k, v in all_stats.items() if k.startswith('ai.')}
        for op_name, op_stats in sorted(ai_ops.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            print(f"  {op_name}: {count}次, 平均{avg:.3f}秒/次, 总计{total:.2f}秒")
        
        # AI成功/失败统计
        ai_success = monitor.metrics.get('ai.success', [])
        ai_error = monitor.metrics.get('ai.error', [])
        if ai_success or ai_error:
            success_count = len(ai_success)
            error_count = len(ai_error)
            total_ai = success_count + error_count
            if total_ai > 0:
                success_rate = (success_count / total_ai) * 100
                print(f"\n  AI成功率: {success_count}/{total_ai} ({success_rate:.1f}%)")
                print(f"  AI失败数: {error_count}/{total_ai}")
                if error_count > 0:
                    # 统计错误类型
                    error_types = {}
                    for err in ai_error:
                        err_type = err.get('extra', {}).get('error_type', 'unknown')
                        error_types[err_type] = error_types.get(err_type, 0) + 1
                    print(f"  错误类型分布:")
                    for err_type, count in error_types.items():
                        print(f"    - {err_type}: {count}次")
        
        # 解析操作统计
        print(f"\n【解析操作统计】")
        parse_ops = {k: v for k, v in all_stats.items() if k.startswith('parse.')}
        for op_name, op_stats in sorted(parse_ops.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            print(f"  {op_name}: {count}次, 平均{avg:.3f}秒/次, 总计{total:.2f}秒")
        
        # 图片处理统计
        print(f"\n【图片处理统计】")
        image_ops = {k: v for k, v in all_stats.items() if k.startswith('image.')}
        for op_name, op_stats in sorted(image_ops.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            print(f"  {op_name}: {count}次, 平均{avg:.3f}秒/次, 总计{total:.2f}秒")
        
        # 数据库操作统计
        print(f"\n【数据库操作统计】")
        db_ops = {k: v for k, v in all_stats.items() if k.startswith('database.')}
        for op_name, op_stats in sorted(db_ops.items()):
            count = op_stats.get('count', 0)
            avg = op_stats.get('avg_duration', 0)
            total = op_stats.get('total_duration', 0)
            print(f"  {op_name}: {count}次, 平均{avg:.3f}秒/次, 总计{total:.2f}秒")
        
        # 自动保存性能数据
        perf_file = crawler.timestamp_dir / f'性能统计_{crawler.timestamp}.json'
        monitor.export_to_json(str(perf_file))
        print(f"\n✅ 性能数据已自动保存到: {perf_file}")
        print(f"💡 使用 'python3 get_performance.py' 查看更详细的性能数据")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"爬取失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

