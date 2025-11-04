#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成爬虫脚本 - 一键完成：爬虫 → AI转述 → 水印清洗 → 上传数据库
"""
import datetime
import time
import random
import json
import csv
import os
import sys
import requests
import threading
import psutil
from urllib.parse import quote
from DrissionPage._pages.chromium_page import ChromiumPage

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from ai_paraphrase import get_ai_paraphraser
from database import db
from batch_upload_tweets import insert_tweet, prepare_tweet_data
from username_generator import get_random_username
from image_processor import ImageProcessor
from performance_monitor import get_crawler_performance_monitor

try:
    from PIL import Image
    import numpy as np
    import cv2
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False
    print("警告: PIL/OpenCV未安装，水印清洗功能将使用AI方式")


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, warning_threshold_gb=10.0, critical_threshold_gb=5.0):
        """
        初始化内存监控器
        
        Args:
            warning_threshold_gb: 警告阈值（GB），可用内存低于此值时发出警告
            critical_threshold_gb: 严重警告阈值（GB），可用内存低于此值时发出严重警告
        """
        self.warning_threshold = warning_threshold_gb * 1024 * 1024 * 1024  # 转换为字节
        self.critical_threshold = critical_threshold_gb * 1024 * 1024 * 1024
        self.process = psutil.Process(os.getpid())
        self.monitoring = False
        self.monitor_thread = None
        self.last_check_time = 0
        self.check_interval = 30  # 每30秒检查一次
        
        # 根据模型大小调整内存阈值
        # 7b模型需要约8-16GB，32b模型需要约32GB+
        # 保守设置：7b模型警告阈值10GB，严重阈值5GB
        # 32b模型警告阈值20GB，严重阈值10GB
        if '32b' in Config.LLM_MODEL.lower():
            # 32b模型需要更多内存
            self.warning_threshold = 20.0 * 1024 * 1024 * 1024
            self.critical_threshold = 10.0 * 1024 * 1024 * 1024
        else:
            # 7b或更小的模型
            self.warning_threshold = warning_threshold_gb * 1024 * 1024 * 1024
            self.critical_threshold = critical_threshold_gb * 1024 * 1024 * 1024
        
    def format_bytes(self, bytes_size):
        """格式化字节大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"
    
    def get_memory_info(self):
        """获取内存信息"""
        try:
            system_memory = psutil.virtual_memory()
            process_memory = self.process.memory_info()
            
            # 获取Ollama进程内存
            ollama_memory = 0
            ollama_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if 'ollama' in proc.info['name'].lower():
                        ollama_memory += proc.info['memory_info'].rss
                        ollama_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            return {
                'system': {
                    'total': system_memory.total,
                    'available': system_memory.available,
                    'used': system_memory.used,
                    'percent': system_memory.percent
                },
                'process': {
                    'rss': process_memory.rss,
                    'vms': process_memory.vms
                },
                'ollama': {
                    'memory': ollama_memory,
                    'count': ollama_count
                }
            }
        except Exception as e:
            return None
    
    def check_memory(self, print_info=True, raise_on_critical=True):
        """
        检查内存使用情况
        
        Args:
            print_info: 是否打印内存信息
            raise_on_critical: 内存严重不足时是否抛出异常
            
        Returns:
            bool: True表示内存充足，False表示内存不足
        """
        memory_info = self.get_memory_info()
        if not memory_info:
            return True
        
        available = memory_info['system']['available']
        process_rss = memory_info['process']['rss']
        ollama_memory = memory_info['ollama']['memory']
        
        # 检查系统可用内存
        is_warning = available < self.warning_threshold
        is_critical = available < self.critical_threshold
        
        if print_info:
            print(f"\n[内存监控] 系统可用: {self.format_bytes(available)} | "
                  f"进程: {self.format_bytes(process_rss)} | "
                  f"Ollama: {self.format_bytes(ollama_memory)} ({memory_info['ollama']['count']}个进程)")
        
        if is_critical:
            error_msg = f"系统可用内存严重不足: {self.format_bytes(available)} (低于阈值 {self.format_bytes(self.critical_threshold)})"
            print(f"\n[严重警告] {error_msg}")
            print("   建议: 1. 关闭其他程序 2. 重启Ollama服务 3. 使用更小的模型")
            print("   为防止模型崩溃，程序将终止")
            
            if raise_on_critical:
                raise MemoryError(error_msg)
            return False
        elif is_warning:
            print(f"\n[警告] 系统可用内存较低: {self.format_bytes(available)} (低于阈值 {self.format_bytes(self.warning_threshold)})")
            print("   建议释放内存或使用更小的模型")
            return True
        
        return True
    
    def start_monitoring(self):
        """开始后台监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    time.sleep(self.check_interval)
                    if self.monitoring:
                        # 后台监控不抛出异常，只打印警告
                        self.check_memory(print_info=True, raise_on_critical=False)
                except Exception as e:
                    print(f"[内存监控] 检查出错: {e}")
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[内存监控] 已启动后台监控")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
    
    def print_summary(self):
        """打印内存使用摘要"""
        memory_info = self.get_memory_info()
        if not memory_info:
            return
        
        print("\n" + "=" * 60)
        print("内存使用摘要")
        print("=" * 60)
        print(f"系统总内存: {self.format_bytes(memory_info['system']['total'])}")
        print(f"系统可用内存: {self.format_bytes(memory_info['system']['available'])}")
        print(f"系统已使用: {self.format_bytes(memory_info['system']['used'])} ({memory_info['system']['percent']:.2f}%)")
        print(f"当前进程内存: {self.format_bytes(memory_info['process']['rss'])}")
        print(f"Ollama进程内存: {self.format_bytes(memory_info['ollama']['memory'])} ({memory_info['ollama']['count']}个进程)")
        print("=" * 60)


class WatermarkRemover:
    """水印清洗工具"""
    
    def __init__(self):
        self.use_ai = not IMAGE_PROCESSING_AVAILABLE
        self.ai_paraphraser = get_ai_paraphraser()
    
    def remove_watermark_ai(self, image_url: str) -> str:
        """使用AI清洗水印（如果图像处理不可用）"""
        # 对于AI方式，我们直接返回原URL，因为AI主要用于内容转述
        # 实际的水印清洗需要专门的图像处理AI模型
        return image_url
    
    def is_grid_image(self, img_cv):
        """
        检测是否为四格拼图
        通过检测图片中的分割线来判断
        """
        h, w = img_cv.shape[:2]
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 检测垂直和水平分割线
        # 使用边缘检测
        edges = cv2.Canny(gray, 50, 150)
        
        # 检测垂直分割线（中间位置）
        vertical_mid = w // 2
        vertical_region = edges[:, max(0, vertical_mid-10):min(w, vertical_mid+10)]
        vertical_line_score = np.sum(vertical_region > 0) / (h * 20)  # 归一化
        
        # 检测水平分割线（中间位置）
        horizontal_mid = h // 2
        horizontal_region = edges[max(0, horizontal_mid-10):min(h, horizontal_mid+10), :]
        horizontal_line_score = np.sum(horizontal_region > 0) / (w * 20)  # 归一化
        
        # 如果垂直和水平都有明显的分割线，可能是四格拼图
        # 阈值可以根据实际情况调整
        is_grid = vertical_line_score > 0.3 and horizontal_line_score > 0.3
        
        return is_grid
    
    def split_grid_image(self, img_cv, base_save_path: str) -> list:
        """
        将四格拼图拆分成4张单独的图片，并对每个格子进行水印清洗
        
        Args:
            img_cv: OpenCV格式的图片
            base_save_path: 基础保存路径（不含扩展名）
            
        Returns:
            拆分后的图片路径列表
        """
        h, w = img_cv.shape[:2]
        
        # 计算每个格子的尺寸
        cell_h = h // 2
        cell_w = w // 2
        
        # 拆分4个格子
        # 左上、右上、左下、右下
        cells = [
            (0, cell_h, 0, cell_w),           # 左上
            (0, cell_h, cell_w, w),          # 右上
            (cell_h, h, 0, cell_w),          # 左下
            (cell_h, h, cell_w, w)           # 右下
        ]
        
        split_paths = []
        
        # 确保目录存在
        os.makedirs(os.path.dirname(base_save_path), exist_ok=True)
        
        # 获取文件扩展名
        ext = os.path.splitext(base_save_path)[1] or '.jpg'
        base_name = os.path.splitext(os.path.basename(base_save_path))[0]
        base_dir = os.path.dirname(base_save_path)
        
        for idx, (y1, y2, x1, x2) in enumerate(cells):
            # 提取单个格子
            cell_img = img_cv[y1:y2, x1:x2]
            
            # 对每个格子进行水印清洗
            # 检测文字区域
            text_mask = self.detect_text_regions(cell_img)
            
            # 检查mask是否有内容
            if np.sum(text_mask) == 0:
                # 没有检测到文字，使用原图
                cleaned_cell = cell_img
            else:
                # 限制inpainting半径，避免过度处理
                cell_h, cell_w = cell_img.shape[:2]
                cell_size = max(cell_h, cell_w)
                inpaint_radius = min(3, max(1, cell_size // 400))
                
                # 使用inpainting填充
                cleaned_cell = cv2.inpaint(cell_img, text_mask, inpaint_radius, cv2.INPAINT_NS)
            
            # 生成保存路径
            cell_path = os.path.join(base_dir, f"{base_name}_grid_{idx+1}{ext}")
            
            # 转换为RGB并保存
            cell_rgb = cv2.cvtColor(cleaned_cell, cv2.COLOR_BGR2RGB)
            cell_pil = Image.fromarray(cell_rgb)
            cell_pil.save(cell_path, quality=95)
            
            split_paths.append(cell_path)
        
        return split_paths
    
    def detect_text_regions(self, img_cv):
        """
        检测图片中的文字区域（水印、餐厅名等）
        优化版本：减少误检，避免过度处理导致马赛克
        
        策略：
        1. 只检测明显的水印区域（角落和中心明显文字）
        2. 使用更严格的阈值，避免误检正常内容
        3. 限制处理区域大小，避免过度处理
        """
        h, w = img_cv.shape[:2]
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 创建全图mask
        mask = np.zeros((h, w), np.uint8)
        
        # 策略1: 只检测角落的水印（小红书logo等） - 使用更严格的阈值
        corner_regions = [
            (0, int(h*0.15), int(w*0.85), w),      # 右上角
            (int(h*0.85), h, int(w*0.85), w),     # 右下角
            (0, int(h*0.15), 0, int(w*0.15)),     # 左上角
            (int(h*0.85), h, 0, int(w*0.15)),     # 左下角
        ]
        
        for y1, y2, x1, x2 in corner_regions:
            if x2 > x1 and y2 > y1:  # 确保区域有效
                corner_gray = gray[y1:y2, x1:x2]
                # 使用更高的阈值，只检测明显的白色文字
                _, corner_thresh = cv2.threshold(corner_gray, 220, 255, cv2.THRESH_BINARY)
                mask[y1:y2, x1:x2] = cv2.bitwise_or(
                    mask[y1:y2, x1:x2],
                    corner_thresh
                )
        
        # 策略2: 检测中心区域明显的文字（但使用更严格的规则）
        # 只在中心区域检测，且使用更严格的阈值
        center_h_start = int(h * 0.35)
        center_h_end = int(h * 0.65)
        center_w_start = int(w * 0.25)
        center_w_end = int(w * 0.75)
        
        if center_h_end > center_h_start and center_w_end > center_w_start:
            center_region = gray[center_h_start:center_h_end, center_w_start:center_w_end]
            
            # 检测高对比度的文字区域（白色文字在深色背景）
            _, center_white = cv2.threshold(center_region, 240, 255, cv2.THRESH_BINARY)
            # 检测深色文字在浅色背景
            _, center_black = cv2.threshold(center_region, 30, 255, cv2.THRESH_BINARY_INV)
            
            # 合并中心区域的检测
            center_mask = cv2.bitwise_or(center_white, center_black)
            
            # 形态学操作，连接文字笔画，但不要过度膨胀
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            center_mask = cv2.morphologyEx(center_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            # 过滤掉太小的区域（可能是噪点）
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(center_mask, connectivity=8)
            center_filtered = np.zeros_like(center_mask)
            
            # 提高最小面积阈值，减少误检
            min_area = max(100, (h * w) // 10000)  # 动态最小面积
            
            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                # 检查宽高比，文字通常宽高比大于1
                width = stats[i, cv2.CC_STAT_WIDTH]
                height = stats[i, cv2.CC_STAT_HEIGHT]
                aspect_ratio = width / height if height > 0 else 0
                
                # 只保留面积足够大且宽高比合理的区域（文字特征）
                if area >= min_area and (aspect_ratio > 1.2 or aspect_ratio < 0.8):
                    center_filtered[labels == i] = 255
            
            # 将中心区域的检测结果加入mask
            mask[center_h_start:center_h_end, center_w_start:center_w_end] = \
                cv2.bitwise_or(
                    mask[center_h_start:center_h_end, center_w_start:center_w_end],
                    center_filtered
                )
        
        # 最后去噪：只保留较大的连通区域
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        filtered_mask = np.zeros_like(mask)
        
        # 计算图片总面积，动态调整最小区域
        total_area = h * w
        min_area = max(50, total_area // 5000)  # 至少占总面积的0.02%
        
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area >= min_area:
                filtered_mask[labels == i] = 255
        
        # 轻微膨胀，确保文字边缘也被覆盖（但不要过度）
        kernel_expand = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        filtered_mask = cv2.dilate(filtered_mask, kernel_expand, iterations=1)
        
        # 限制处理区域：如果mask覆盖面积超过图片的10%，可能是误检，减少处理
        mask_area_ratio = np.sum(filtered_mask > 0) / total_area
        if mask_area_ratio > 0.1:
            # 如果检测到的区域太大，只保留最大的几个区域
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(filtered_mask, connectivity=8)
            areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
            areas.sort(key=lambda x: x[1], reverse=True)
            
            # 只保留前5个最大的区域
            filtered_mask = np.zeros_like(filtered_mask)
            for i, _ in areas[:5]:
                filtered_mask[labels == i] = 255
        
        return filtered_mask
    
    def remove_watermark_image(self, image_url: str, save_path: str = None) -> str:
        """使用图像处理清洗水印和文字"""
        if not IMAGE_PROCESSING_AVAILABLE:
            return image_url
        
        try:
            # 下载图片
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                return image_url
            
            # 转换为PIL Image
            from io import BytesIO
            img = Image.open(BytesIO(response.content))
            img_array = np.array(img)
            
            # 转换为OpenCV格式
            if len(img_array.shape) == 3:
                img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_cv = img_array
            
            h, w = img_cv.shape[:2]  # 获取图片尺寸
            
            # 检测是否为四格拼图
            if self.is_grid_image(img_cv):
                print(f"检测到四格拼图，正在拆分...")
                if save_path:
                    split_paths = self.split_grid_image(img_cv, save_path)
                    print(f"已拆分为 {len(split_paths)} 张图片")
                    # 返回所有拆分后的图片路径（逗号分隔）
                    return ",".join(split_paths) if split_paths else image_url
                else:
                    # 如果没有指定保存路径，先保存到临时文件再拆分
                    temp_path = f"temp_grid_{int(time.time())}.jpg"
                    split_paths = self.split_grid_image(img_cv, temp_path)
                    return ",".join(split_paths) if split_paths else image_url
            
            # 不是四格拼图，正常处理水印
            # 检测文字区域（包括中心区域的餐厅名等）
            text_mask = self.detect_text_regions(img_cv)
            
            # 检查mask是否有内容，如果mask为空则直接返回原图
            if np.sum(text_mask) == 0:
                # 没有检测到文字，直接保存原图
                if save_path:
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    img.save(save_path, quality=95)
                    return save_path
                return image_url
            
            # 限制inpainting的半径，避免过度处理导致马赛克
            # 根据图片大小动态调整半径
            img_size = max(h, w)
            inpaint_radius = min(3, max(1, img_size // 400))  # 半径在1-3之间
            
            # 使用inpainting智能填充文字区域
            # INPAINT_NS 算法效果更自然，适合填充文字区域
            result = cv2.inpaint(img_cv, text_mask, inpaint_radius, cv2.INPAINT_NS)
            
            # 不再进行二次处理，避免过度处理导致马赛克
            
            # 转换回PIL并保存
            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            result_img = Image.fromarray(result_rgb)
            
            if save_path:
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                result_img.save(save_path, quality=95)
                return save_path
            else:
                # 保存到临时文件
                temp_path = f"temp_cleaned_{int(time.time())}.jpg"
                result_img.save(temp_path, quality=95)
                return temp_path
                
        except Exception as e:
            print(f"水印清洗失败: {e}")
            return image_url
    
    def download_image(self, image_url: str, save_path: str) -> str:
        """下载图片并保存到指定路径"""
        try:
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                return ""
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存图片
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return save_path
        except Exception as e:
            print(f"下载图片失败 {image_url}: {e}")
            return ""
    
    def process_image(self, image_url: str, save_path: str = None) -> str:
        """处理图片，清洗水印"""
        if Config.REMOVE_WATERMARK:
            if IMAGE_PROCESSING_AVAILABLE:
                return self.remove_watermark_image(image_url, save_path)
            else:
                return self.remove_watermark_ai(image_url)
        elif save_path:
            return self.download_image(image_url, save_path)
        return image_url


class IntegratedSpider:
    """集成爬虫：爬虫 + AI转述 + 水印清洗 + 上传"""
    
    def __init__(self):
        self.page = ChromiumPage()
        self.setup_browser()
        self.request_count = 0
        self.last_request_time = 0
        self.ai_paraphraser = None
        self.image_processor = ImageProcessor()  # 使用新的图片搜索处理器
        self.perf_monitor = get_crawler_performance_monitor()
        self.memory_monitor = MemoryMonitor(warning_threshold_gb=10.0, critical_threshold_gb=5.0)
        
        # 自动启用AI转述
        try:
            self.ai_paraphraser = get_ai_paraphraser()
            if not self.ai_paraphraser.check_ollama_connection():
                raise Exception("Ollama服务未运行")
            if not self.ai_paraphraser.check_model_exists():
                raise Exception(f"模型 {Config.LLM_MODEL} 未下载")
            print("✅ AI转述功能已启用")
        except Exception as e:
            print(f"❌ AI转述初始化失败: {e}")
            print("请确保：")
            print("1. Ollama服务已运行")
            print(f"2. 模型 {Config.LLM_MODEL} 已下载")
            print("运行: python setup_ollama.py")
            raise
    
    def setup_browser(self):
        """设置浏览器参数"""
        user_agent = random.choice(Config.USER_AGENTS)
        headers = Config.DEFAULT_HEADERS.copy()
        headers['User-Agent'] = user_agent
        self.page.set.headers(headers)
        self.page.set.window.size(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
    
    def enforce_rate_limit(self):
        """强制速率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < Config.MIN_REQUEST_INTERVAL:
            sleep_time = Config.MIN_REQUEST_INTERVAL - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        if self.request_count % Config.EXTRA_DELAY_INTERVAL == 0:
            extra_delay = random.uniform(Config.EXTRA_DELAY_MIN, Config.EXTRA_DELAY_MAX)
            time.sleep(extra_delay)
    
    def random_delay(self, min_delay=None, max_delay=None):
        """随机延迟"""
        if min_delay is None:
            min_delay = Config.DELAY_MIN
        if max_delay is None:
            max_delay = Config.DELAY_MAX
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def human_like_scroll(self):
        """模拟人类滚动"""
        scroll_steps = random.randint(Config.SCROLL_STEPS_MIN, Config.SCROLL_STEPS_MAX)
        for i in range(scroll_steps):
            scroll_distance = random.randint(Config.SCROLL_DISTANCE_MIN, Config.SCROLL_DISTANCE_MAX)
            self.page.run_js(f"window.scrollBy(0, {scroll_distance})")
            time.sleep(random.uniform(Config.SCROLL_INTERVAL_MIN, Config.SCROLL_INTERVAL_MAX))
    
    def check_for_blocking(self):
        """检查是否被阻止"""
        try:
            page_text = self.page.html.lower()
            for indicator in Config.BLOCKING_INDICATORS:
                if indicator in page_text:
                    return True
            return False
        except:
            return False
    
    def handle_blocking(self):
        """处理被阻止的情况"""
        wait_time = random.uniform(Config.BLOCKING_WAIT_MIN, Config.BLOCKING_WAIT_MAX)
        time.sleep(wait_time)
        try:
            self.page.refresh()
            self.page.wait.doc_loaded()
            time.sleep(random.uniform(3, 5))
        except:
            pass
    
    def get_note_detail(self, note_id, xsec_token, retry_count=0):
        """获取笔记详情"""
        start_time = time.time()
        try:
            self.enforce_rate_limit()
            infourl = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search&source=web_explore_feed"
            print(f"正在获取详情：{note_id}")
            
            self.random_delay(3, 6)
            self.page.get(infourl)
            self.page.wait.doc_loaded()
            
            if self.check_for_blocking():
                self.handle_blocking()
                if retry_count < Config.MAX_RETRIES:
                    return self.get_note_detail(note_id, xsec_token, retry_count + 1)
                else:
                    return "", "", ""
            
            self.human_like_scroll()
            
            # 获取图片链接
            img_urls = []
            try:
                swiper_elements = self.page.eles('.swiper-wrapper')
                if swiper_elements:
                    images = swiper_elements[0].eles("tag:img")
                    for img in images:
                        try:
                            imgurl = img.attr("src")
                            if imgurl and imgurl not in img_urls:
                                img_urls.append(imgurl)
                        except:
                            pass
            except Exception as e:
                print(f"获取图片失败: {e}")
            
            # 获取标题和描述
            title = ""
            desc = ""
            try:
                title_ele = self.page.ele("#detail-title")
                if title_ele:
                    title = title_ele.text.strip()
                    
                desc_ele = self.page.ele("#detail-desc")
                if desc_ele:
                    desc = desc_ele.text.strip()
            except Exception as e:
                print(f"获取标题或描述失败: {e}")
            
            duration = time.time() - start_time
            self.perf_monitor.record_metric(
                'crawler.get_note_detail',
                duration,
                {
                    'memory_mb': self.perf_monitor.get_memory_usage(),
                    'cpu_percent': self.perf_monitor.get_cpu_usage(),
                    'note_id': note_id
                }
            )
            return title, desc, ",".join(img_urls)
            
        except Exception as e:
            duration = time.time() - start_time
            self.perf_monitor.record_metric(
                'crawler.get_note_detail.error',
                duration,
                {'error': str(e), 'note_id': note_id}
            )
            print(f"获取详情失败: {e}")
            if retry_count < Config.MAX_RETRIES:
                self.random_delay(8, 15)
                return self.get_note_detail(note_id, xsec_token, retry_count + 1)
            else:
                return "", "", ""
    
    def search_notes(self, keyword, pages):
        """搜索笔记"""
        start_time = time.time()
        # 检查内存
        self.memory_monitor.check_memory(print_info=True)
        try:
            self.page.listen.start("https://edith.xiaohongshu.com/api/sns/web/v1/search/notes")
            encoded_keyword = quote(keyword)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_explore_feed"
            
            print(f"正在访问搜索页面: {search_url}")
            self.page.get(search_url)
            self.page.wait.doc_loaded()
            self.random_delay(5, 8)
            
            responses = []
            
            for page_num in range(pages):
                try:
                    print(f"正在爬取第 {page_num + 1} 页")
                    
                    if self.check_for_blocking():
                        self.handle_blocking()
                        continue
                    
                    self.human_like_scroll()
                    
                    try:
                        packet = self.page.listen.wait(timeout=Config.REQUEST_TIMEOUT)
                        if packet and packet.response:
                            response_body = packet.response.body
                            if response_body:
                                responses.append(response_body)
                                print(f"成功捕获第 {page_num + 1} 页数据")
                    except Exception as e:
                        print(f"第 {page_num + 1} 页捕获失败: {e}")
                    
                    if page_num < pages - 1:
                        page_delay = random.uniform(Config.PAGE_DELAY_MIN, Config.PAGE_DELAY_MAX)
                        time.sleep(page_delay)
                        # 每页后检查内存
                        self.memory_monitor.check_memory(print_info=True)
                        
                except KeyboardInterrupt:
                    print(f"\n⚠️  在第 {page_num + 1} 页爬取时被中断")
                    print(f"已获取 {len(responses)} 页数据")
                    raise
            
            duration = time.time() - start_time
            self.perf_monitor.record_metric(
                'crawler.search_notes',
                duration,
                {
                    'keyword': keyword,
                    'pages': pages,
                    'responses_count': len(responses),
                    'memory_mb': self.perf_monitor.get_memory_usage(),
                    'cpu_percent': self.perf_monitor.get_cpu_usage()
                }
            )
            return responses
            
        except Exception as e:
            duration = time.time() - start_time
            self.perf_monitor.record_metric(
                'crawler.search_notes.error',
                duration,
                {'error': str(e), 'keyword': keyword, 'pages': pages}
            )
            print(f"搜索笔记失败: {e}")
            return []
    
    def process_and_upload(self, responses, keyword):
        """处理数据并上传"""
        start_time = time.time()
        # 开始处理前检查内存
        self.memory_monitor.check_memory(print_info=True)
        
        total_notes = 0
        processed_count = 0
        ai_paraphrased_count = 0
        upload_success_count = 0
        upload_fail_count = 0
        
        nowt = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        
        # 创建保存目录结构: saved/时间戳/图片、原文、转述
        base_dir = os.path.join("saved", nowt)
        images_dir = os.path.join(base_dir, "图片")
        original_dir = os.path.join(base_dir, "原文")
        paraphrased_dir = os.path.join(base_dir, "转述")
        
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(original_dir, exist_ok=True)
        os.makedirs(paraphrased_dir, exist_ok=True)
        
        print(f"保存目录: {base_dir}")
        
        csv_filename = os.path.join(base_dir, f"{keyword}_{nowt}.csv")
        
        with open(csv_filename, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["餐厅名称", "原始描述", "图片链接", "笔记ID", "转述标题", "转述描述", "地址", "清洗后图片"])
            
            for response in responses:
                try:
                    if isinstance(response, str):
                        response_data = json.loads(response)
                    else:
                        response_data = response
                    
                    if 'data' in response_data and 'items' in response_data['data']:
                        notes = response_data['data']['items']
                        total_notes += len(notes)
                        
                        for note in notes:
                            try:
                                note_id = note.get("id")
                                xsec_token = note.get("xsec_token")
                                
                                if note_id and xsec_token:
                                    title, desc, img = self.get_note_detail(note_id, xsec_token)
                                    if title:
                                        # 保存原文
                                        original_filename = os.path.join(original_dir, f"{processed_count:04d}_{note_id}.txt")
                                        with open(original_filename, 'w', encoding='utf-8') as f:
                                            f.write(f"标题: {title}\n\n")
                                            f.write(f"描述: {desc}\n")
                                        print(f"\n📝 正在处理笔记: {title[:50]}...")
                                        
                                        # 提取餐厅信息
                                        print(f"🔍 正在提取餐厅信息...")
                                        # AI调用前检查内存，内存不足时终止
                                        try:
                                            self.memory_monitor.check_memory(print_info=True, raise_on_critical=True)
                                        except MemoryError as e:
                                            print(f"\n❌ 内存不足，终止程序: {e}")
                                            raise
                                        
                                        extract_start = time.time()
                                        restaurants = self.ai_paraphraser.extract_restaurants(title, desc)
                                        extract_duration = time.time() - extract_start
                                        self.perf_monitor.record_metric(
                                            'ai.extract_restaurants',
                                            extract_duration,
                                            {
                                                'restaurant_count': len(restaurants),
                                                'memory_mb': self.perf_monitor.get_memory_usage(),
                                                'cpu_percent': self.perf_monitor.get_cpu_usage()
                                            }
                                        )
                                        
                                        if not restaurants:
                                            # 如果没有提取到餐厅，使用原来的方式处理（作为单个条目）
                                            print(f"⚠️  未提取到餐厅信息，按原笔记处理")
                                            restaurants = [{
                                                'name': title,
                                                'address': '',
                                                'price_range': '',
                                                'description': desc
                                            }]
                                        
                                        print(f"✅ 提取到 {len(restaurants)} 个餐厅")
                                        
                                        # 原帖图片不再处理，每个餐厅会单独搜索图片
                                        
                                        # 为每个餐厅分别转述和上传
                                        for restaurant_idx, restaurant in enumerate(restaurants):
                                            restaurant_name = restaurant.get('name', '未知餐厅')
                                            restaurant_address = restaurant.get('address', '')
                                            print(f"\n🍴 正在处理餐厅 {restaurant_idx + 1}/{len(restaurants)}: {restaurant_name}")
                                            
                                            # 搜索餐厅图片（中间无文字的图片）
                                            # 如果搜索失败，使用原帖第一张图片作为备选
                                            img_start = time.time()
                                            restaurant_safe_name = restaurant_name.replace('/', '_').replace('\\', '_')[:50]
                                            img_filename = f"{processed_count:04d}_{note_id}_{restaurant_idx}_{restaurant_safe_name}.jpg"
                                            img_path = os.path.join(images_dir, img_filename)
                                            
                                            # 获取原帖第一张图片作为备选
                                            fallback_img_url = None
                                            if img:
                                                img_list = img.split(',')
                                                if img_list:
                                                    fallback_img_url = img_list[0].strip()
                                            
                                            saved_image_path = self.image_processor.process_restaurant_image(
                                                restaurant_name=restaurant_name,
                                                restaurant_address=restaurant_address,
                                                save_path=img_path,
                                                fallback_image_url=fallback_img_url
                                            )
                                            img_duration = time.time() - img_start
                                            
                                            if not saved_image_path:
                                                print(f"⚠️  无法获取餐厅图片，跳过: {restaurant_name}")
                                                continue
                                            
                                            saved_image_paths = [saved_image_path]
                                            self.perf_monitor.record_metric(
                                                'image.search_and_download',
                                                img_duration,
                                                {'memory_mb': self.perf_monitor.get_memory_usage()}
                                            )
                                            
                                            # 对餐厅进行转述
                                            # AI调用前检查内存，内存不足时终止
                                            try:
                                                self.memory_monitor.check_memory(print_info=False, raise_on_critical=True)
                                            except MemoryError as e:
                                                print(f"\n❌ 内存不足，终止程序: {e}")
                                                raise
                                            
                                            paraphrase_start = time.time()
                                            paraphrased_title, paraphrased_desc, type_cid = self.ai_paraphraser.paraphrase_restaurant(restaurant, title)
                                            paraphrase_duration = time.time() - paraphrase_start
                                            self.perf_monitor.record_metric(
                                                'ai.paraphrase_restaurant',
                                                paraphrase_duration,
                                                {
                                                    'memory_mb': self.perf_monitor.get_memory_usage(),
                                                    'cpu_percent': self.perf_monitor.get_cpu_usage(),
                                                    'restaurant_name': restaurant_name
                                                }
                                            )
                                            
                                            if not paraphrased_title:
                                                print(f"⚠️  餐厅转述失败，跳过")
                                                continue
                                            
                                            if not type_cid:
                                                print(f"❌ AI分类失败，跳过该餐厅: {restaurant_name}")
                                                continue
                                            else:
                                                print(f"✅ AI分类完成: 子类型ID={type_cid}")
                                            
                                            # 保存转述内容（每个餐厅单独保存）
                                            paraphrased_filename = os.path.join(paraphrased_dir, f"{processed_count:04d}_{note_id}_{restaurant_idx}_{restaurant_safe_name}.txt")
                                            with open(paraphrased_filename, 'w', encoding='utf-8') as f:
                                                f.write(f"餐厅名称: {restaurant_name}\n\n")
                                                f.write(f"标题: {paraphrased_title}\n\n")
                                                f.write(f"描述: {paraphrased_desc}\n")
                                                if restaurant.get('address'):
                                                    f.write(f"\n地址: {restaurant.get('address')}\n")
                                                if restaurant.get('price_range'):
                                                    f.write(f"\n人均: {restaurant.get('price_range')}\n")
                                            print(f"✅ 已保存转述: {paraphrased_filename}")
                                            
                                            # 写入CSV（每个餐厅一行）
                                            writer.writerow([
                                                restaurant_name,  # 原始标题（餐厅名）
                                                restaurant.get('description', desc),  # 原始描述
                                                img,  # 原始图片链接（保留原帖图片链接）
                                                f"{note_id}_{restaurant_idx}",  # 笔记ID_餐厅索引
                                                paraphrased_title,  # 转述标题
                                                paraphrased_desc,  # 转述描述
                                                restaurant.get('address', ''),  # 地址（作为内容类型字段）
                                                saved_image_path  # 搜索到的餐厅图片
                                            ])
                                            
                                            # 准备数据库数据（每个餐厅一条记录）
                                            # 确保父类型ID不为空，如果配置中没有则使用默认值5
                                            type_pid = Config.DEFAULT_TYPE_PID if Config.DEFAULT_TYPE_PID is not None else 5
                                            
                                            # 处理图片路径：转换为相对路径或URL格式
                                            img_paths_for_db = []
                                            if saved_image_path:
                                                if os.path.isabs(saved_image_path):
                                                    # 如果是绝对路径，转换为相对路径（相对于crawler-tool目录）
                                                    crawler_tool_dir = os.path.dirname(os.path.abspath(__file__))
                                                    try:
                                                        rel_path = os.path.relpath(saved_image_path, crawler_tool_dir)
                                                        rel_path = rel_path.replace('\\', '/')
                                                        if not rel_path.startswith('./') and not rel_path.startswith('../'):
                                                            rel_path = './' + rel_path
                                                        img_paths_for_db.append(rel_path)
                                                    except ValueError:
                                                        img_paths_for_db.append(os.path.basename(saved_image_path))
                                                else:
                                                    # 已经是相对路径
                                                    saved_image_path = saved_image_path.replace('\\', '/')
                                                    if not saved_image_path.startswith('./') and not saved_image_path.startswith('../') and not saved_image_path.startswith('/'):
                                                        saved_image_path = './' + saved_image_path
                                                    img_paths_for_db.append(saved_image_path)
                                            
                                            tweet = {
                                                'tweets_title': paraphrased_title,
                                                'tweets_content': paraphrased_desc,
                                                'tweets_describe': paraphrased_desc[:200] if len(paraphrased_desc) > 200 else paraphrased_desc,
                                                'tweets_img': json.dumps(img_paths_for_db) if img_paths_for_db else json.dumps([]),
                                                'tweets_type_pid': type_pid,
                                                'tweets_type_cid': type_cid,  # 使用AI返回的子类型ID
                                                'tweets_user': get_random_username(),  # 随机生成用户名
                                                # 添加随机数：浏览量、点赞量、收藏量
                                                'browse_num': random.randint(50, 500),   # 浏览量：50-500
                                                'like_num': random.randint(5, 100),      # 点赞量：5-100
                                                'collect_num': random.randint(2, 50),   # 收藏量：2-50
                                            }
                                            
                                            # 立即上传到数据库
                                            upload_start = time.time()
                                            try:
                                                prepared_tweet = prepare_tweet_data(tweet)
                                                tweet_id = insert_tweet(prepared_tweet)
                                                upload_duration = time.time() - upload_start
                                                if tweet_id:
                                                    upload_success_count += 1
                                                    print(f"✅ 上传至数据库完成 (ID: {tweet_id}) - {restaurant_name}")
                                                    self.perf_monitor.record_metric(
                                                        'db.insert_tweet',
                                                        upload_duration,
                                                        {
                                                            'success': True,
                                                            'tweet_id': tweet_id,
                                                            'memory_mb': self.perf_monitor.get_memory_usage()
                                                        }
                                                    )
                                                else:
                                                    upload_fail_count += 1
                                                    print(f"❌ 上传至数据库失败: 返回ID为空 - {restaurant_name}")
                                                    self.perf_monitor.record_metric(
                                                        'db.insert_tweet.error',
                                                        upload_duration,
                                                        {'error': '返回ID为空'}
                                                    )
                                            except Exception as e:
                                                upload_duration = time.time() - upload_start
                                                upload_fail_count += 1
                                                print(f"❌ 上传至数据库失败: {e} - {restaurant_name}")
                                                self.perf_monitor.record_metric(
                                                    'db.insert_tweet.error',
                                                    upload_duration,
                                                    {'error': str(e)}
                                                )
                                            
                                            processed_count += 1
                                            ai_paraphrased_count += 1
                                            
                                            if processed_count % Config.BATCH_SIZE == 0:
                                                file.flush()
                                                print(f"已处理 {processed_count} 条数据")
                                                # 每批处理后检查内存
                                                self.memory_monitor.check_memory(print_info=True)
                                                self.random_delay(3, 6)
                            except KeyboardInterrupt:
                                print(f"\n⚠️  在处理第 {processed_count + 1} 条数据时被中断")
                                print(f"已处理 {processed_count} 条数据")
                                raise
                            except (MemoryError, Exception) as e:
                                # 如果是内存不足或AI模型不可用的错误，直接终止程序
                                if isinstance(e, MemoryError) or "AI模型不可用" in str(e):
                                    print(f"\n❌ {e}")
                                    print("程序终止")
                                    raise  # 重新抛出异常，终止程序
                                print(f"处理单条数据时出错: {e}")
                                continue  # 继续处理下一条
                except KeyboardInterrupt:
                    print(f"\n⚠️  在处理响应时被中断")
                    print(f"已处理 {processed_count} 条数据")
                    raise
                except (MemoryError, Exception) as e:
                    # 如果是内存不足或AI模型不可用的错误，直接终止程序
                    if isinstance(e, MemoryError) or "AI模型不可用" in str(e):
                        print(f"\n❌ {e}")
                        print("程序终止")
                        raise  # 重新抛出异常，终止程序
                    print(f"处理响应时出现错误: {e}")
        
        print(f"\n总共处理了 {total_notes} 条笔记，成功保存 {processed_count} 条餐厅数据")
        print(f"保存位置: {base_dir}")
        print(f"AI转述成功: {ai_paraphrased_count} 条")
        print(f"数据库上传: 成功 {upload_success_count} 条, 失败 {upload_fail_count} 条")
        
        # 记录整体处理性能
        total_duration = time.time() - start_time
        self.perf_monitor.record_metric(
            'crawler.process_and_upload',
            total_duration,
            {
                'total_notes': total_notes,
                'processed_count': processed_count,
                'ai_paraphrased_count': ai_paraphrased_count,
                'upload_success_count': upload_success_count,
                'upload_fail_count': upload_fail_count,
                'keyword': keyword,
                'memory_mb': self.perf_monitor.get_memory_usage(),
                'cpu_percent': self.perf_monitor.get_cpu_usage()
            }
        )
        
        return csv_filename
    
    def login(self):
        """手动登录小红书"""
        self.page.get('https://www.xiaohongshu.com')
        print('请扫码登录小红书')
        print('登录完成后按回车继续...')
        input()
        time.sleep(3)
    
    def run(self, keyword, pages):
        """运行完整流程"""
        try:
            # 启动内存监控
            self.memory_monitor.start_monitoring()
            # 初始内存检查
            self.memory_monitor.check_memory(print_info=True)
            
            self.login()
            
            print(f"\n开始抓取关键词：{keyword}")
            print(f"预计抓取 {pages} 页数据")
            print("=" * 60)
            print("提示: 按 Ctrl+C 可以随时终止程序")
            
            responses = self.search_notes(keyword, pages)
            if responses:
                filename = self.process_and_upload(responses, keyword)
                print(f"\n✅ 全部完成！数据已保存到：{filename}")
                
                # 显示性能统计提示
                print("\n" + "=" * 60)
                print("📊 性能监控数据已记录")
                print("查看性能统计：python performance_monitor.py")
                print("导出性能数据：python performance_monitor.py --export performance.json")
                print("=" * 60)
            else:
                print("未获取到任何数据")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  检测到 Ctrl+C，正在安全退出...")
            print("正在保存已处理的数据...")
            print("正在关闭浏览器...")
            raise  # 重新抛出，让外层也能捕获
        except MemoryError as e:
            print(f"\n❌ 内存不足导致程序终止: {e}")
            raise  # 重新抛出，让外层也能捕获
        except Exception as e:
            print(f"程序执行出错: {e}")
        finally:
            # 停止内存监控并打印摘要
            self.memory_monitor.stop_monitoring()
            self.memory_monitor.print_summary()
            
            try:
                self.page.close()
                print("✅ 浏览器已关闭")
            except:
                pass


def main():
    """主函数 - 一键运行"""
    if len(sys.argv) < 3:
        print("用法: python crawler.py <关键词> <页数>")
        print("示例: python crawler.py 深圳美食 5")
        sys.exit(1)
    
    keyword = sys.argv[1]
    try:
        pages = int(sys.argv[2])
    except ValueError:
        print("错误: 页数必须是数字")
        sys.exit(1)
    
    print("=" * 60)
    print("集成爬虫系统")
    print("功能: 爬虫 → AI转述 → 水印清洗 → 自动上传")
    print(f"模型: {Config.LLM_MODEL}")
    print("=" * 60)
    print()
    
    spider = None
    try:
        spider = IntegratedSpider()
        spider.run(keyword, pages)
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被用户中断 (Ctrl+C)")
        print("正在清理资源...")
        if spider:
            try:
                spider.page.close()
            except:
                pass
        print("✅ 程序已安全退出")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        if spider:
            try:
                spider.page.close()
            except:
                pass
        sys.exit(1)


if __name__ == '__main__':
    main()

