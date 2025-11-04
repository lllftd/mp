#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片搜索和处理模块 - 使用浏览器自动化搜索餐厅图片并选择中间无文字的图片
"""
import os
import re
import time
import requests
from typing import Optional, List
from io import BytesIO
from urllib.parse import quote

try:
    import cv2
    import numpy as np
    from PIL import Image
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False

try:
    from DrissionPage._pages.chromium_page import ChromiumPage
    DRISSIONPAGE_AVAILABLE = True
except ImportError:
    DRISSIONPAGE_AVAILABLE = False


class ImageSearcher:
    """图片搜索工具 - 使用浏览器自动化搜索餐厅图片"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        # 使用浏览器自动化（如果可用）
        self.browser_page = None
        if DRISSIONPAGE_AVAILABLE:
            try:
                self.browser_page = ChromiumPage()
                self.browser_page.set.window.size(1920, 1080)
            except Exception as e:
                print(f"浏览器初始化失败，将使用简单HTTP请求: {e}")
                self.browser_page = None
    
    def search_images(self, restaurant_name: str, max_results: int = 10) -> List[str]:
        """
        搜索餐厅图片（优先使用浏览器自动化）
        
        Args:
            restaurant_name: 餐厅名称
            max_results: 最大返回结果数
            
        Returns:
            图片URL列表
        """
        try:
            # 简化搜索关键词，只用餐厅名称（去掉地址，避免搜索失败）
            search_query = restaurant_name.split()[0] if restaurant_name else restaurant_name
            search_query = f"{search_query} 餐厅 美食"
            
            # 方法1：使用浏览器自动化搜索Bing图片（最可靠）
            if self.browser_page:
                try:
                    results = self._search_bing_with_browser(search_query, max_results)
                    if results:
                        print(f"浏览器搜索Bing成功，找到 {len(results)} 张图片")
                        return results
                except Exception as e:
                    print(f"浏览器搜索Bing失败: {e}")
            
            # 方法2：使用简单HTTP请求搜索Bing
            try:
                results = self._search_bing(search_query, max_results)
                if results:
                    print(f"HTTP搜索Bing成功，找到 {len(results)} 张图片")
                    return results
            except Exception as e:
                print(f"Bing搜索失败: {e}")
            
            # 方法3：使用浏览器自动化搜索Google图片
            if self.browser_page:
                try:
                    results = self._search_google_with_browser(search_query, max_results)
                    if results:
                        print(f"浏览器搜索Google成功，找到 {len(results)} 张图片")
                        return results
                except Exception as e:
                    print(f"浏览器搜索Google失败: {e}")
            
            # 方法4：使用简单HTTP请求搜索Google
            try:
                results = self._search_google(search_query, max_results)
                if results:
                    print(f"HTTP搜索Google成功，找到 {len(results)} 张图片")
                    return results
            except Exception as e:
                print(f"Google搜索失败: {e}")
            
            return []
            
        except Exception as e:
            print(f"搜索图片失败: {e}")
            return []
    
    def _search_bing_with_browser(self, query: str, max_results: int) -> List[str]:
        """使用浏览器自动化搜索Bing图片（最可靠）"""
        try:
            url = f"https://www.bing.com/images/search?q={quote(query)}&FORM=HDRSC2"
            
            # 访问搜索页面
            self.browser_page.get(url)
            time.sleep(2)  # 等待页面加载
            
            # 滚动页面以加载更多图片
            for _ in range(2):
                self.browser_page.scroll.to_bottom()
                time.sleep(1)
            
            # 获取页面HTML
            html = self.browser_page.html
            
            # 从HTML中提取图片URL
            # 方法1: 从JSON数据中提取
            pattern1 = r'murl":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
            matches1 = re.findall(pattern1, html)
            
            # 方法2: 从img标签的data-src属性提取
            pattern2 = r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
            matches2 = re.findall(pattern2, html)
            
            # 方法3: 从img标签的src属性提取
            pattern3 = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
            matches3 = re.findall(pattern3, html)
            
            # 合并所有结果并去重
            all_matches = list(set(matches1 + matches2 + matches3))
            
            # 过滤掉明显不是图片的URL
            filtered = [url for url in all_matches 
                       if not any(x in url.lower() for x in ['icon', 'logo', 'avatar', 'thumb', 'google', 'bing', 'favicon', 'svg'])]
            
            return filtered[:max_results]
            
        except Exception as e:
            print(f"浏览器搜索Bing失败: {e}")
            return []
    
    def _search_google_with_browser(self, query: str, max_results: int) -> List[str]:
        """使用浏览器自动化搜索Google图片"""
        try:
            url = f"https://www.google.com/search?q={quote(query)}&tbm=isch"
            
            # 访问搜索页面
            self.browser_page.get(url)
            time.sleep(2)  # 等待页面加载
            
            # 滚动页面以加载更多图片
            for _ in range(2):
                self.browser_page.scroll.to_bottom()
                time.sleep(1)
            
            # 获取页面HTML
            html = self.browser_page.html
            
            # 提取图片URL
            # 从Google图片搜索结果中提取
            # Google使用JSON格式存储图片数据
            pattern1 = r'"ou":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
            matches1 = re.findall(pattern1, html)
            
            pattern2 = r'"url":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
            matches2 = re.findall(pattern2, html)
            
            pattern3 = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
            matches3 = re.findall(pattern3, html)
            
            # 合并并过滤
            all_matches = list(set(matches1 + matches2 + matches3))
            filtered = [url for url in all_matches 
                       if not any(x in url.lower() for x in ['icon', 'logo', 'avatar', 'thumb', 'google', 'favicon', 'gstatic', 'svg'])]
            
            return filtered[:max_results]
            
        except Exception as e:
            print(f"浏览器搜索Google失败: {e}")
            return []
    
    def _search_duckduckgo(self, query: str, max_results: int) -> List[str]:
        """使用DuckDuckGo搜索图片"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                pattern = r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
                matches = re.findall(pattern, response.text)
                return matches[:max_results]
            
            return []
        except Exception as e:
            print(f"DuckDuckGo搜索失败: {e}")
            return []
    
    def _search_bing(self, query: str, max_results: int) -> List[str]:
        """使用HTTP请求搜索Bing图片"""
        try:
            url = f"https://www.bing.com/images/search?q={quote(query)}&FORM=HDRSC2"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                # 解析HTML获取图片URL
                # 方法1: 从JSON数据中提取
                pattern1 = r'murl":"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
                matches1 = re.findall(pattern1, response.text)
                
                # 方法2: 从HTML标签中提取
                pattern2 = r'<img[^>]+src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
                matches2 = re.findall(pattern2, response.text)
                
                # 方法3: 从data-src属性中提取
                pattern3 = r'data-src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
                matches3 = re.findall(pattern3, response.text)
                
                # 合并所有结果并去重
                all_matches = list(set(matches1 + matches2 + matches3))
                
                # 过滤掉明显不是图片的URL
                filtered = [url for url in all_matches 
                           if not any(x in url.lower() for x in ['icon', 'logo', 'avatar', 'thumb', 'google', 'bing', 'favicon', 'svg'])]
                
                return filtered[:max_results]
            
            return []
        except Exception as e:
            print(f"Bing搜索失败: {e}")
            return []
    
    def _search_google(self, query: str, max_results: int) -> List[str]:
        """使用HTTP请求搜索Google图片"""
        try:
            url = f"https://www.google.com/search?q={quote(query)}&tbm=isch"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                # 解析HTML获取图片URL
                pattern = r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"'
                matches = re.findall(pattern, response.text)
                # 过滤掉一些明显不是图片的URL
                filtered = [url for url in matches 
                           if not any(x in url.lower() for x in ['icon', 'logo', 'avatar', 'thumb', 'google', 'favicon', 'gstatic', 'svg'])]
                return filtered[:max_results]
            
            return []
        except Exception as e:
            print(f"Google搜索失败: {e}")
            return []
    
    def check_center_text(self, image_url: str) -> bool:
        """
        检查图片中间区域是否有文字
        
        Args:
            image_url: 图片URL
            
        Returns:
            True表示中间有文字，False表示中间无文字
        """
        if not IMAGE_PROCESSING_AVAILABLE:
            return False
        
        try:
            # 下载图片
            response = self.session.get(image_url, timeout=10, stream=True)
            if response.status_code != 200:
                return True  # 如果下载失败，假设有文字（保守处理）
            
            # 读取图片
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            img_array = np.array(img)
            
            # 转换为OpenCV格式
            if len(img_array.shape) == 3:
                img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_cv = img_array
            
            h, w = img_cv.shape[:2]
            
            # 定义中心区域（中间40%的区域）
            center_h_start = int(h * 0.3)
            center_h_end = int(h * 0.7)
            center_w_start = int(w * 0.3)
            center_w_end = int(w * 0.7)
            
            # 提取中心区域
            center_region = img_cv[center_h_start:center_h_end, center_w_start:center_w_end]
            
            # 转换为灰度图
            gray = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
            
            # 使用阈值检测文字（高对比度区域）
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 检测边缘
            edges = cv2.Canny(gray, 50, 150)
            
            # 计算边缘密度
            edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
            
            # 如果边缘密度超过阈值，可能包含文字
            # 阈值可以根据实际情况调整
            has_text = edge_density > 0.1
            
            return has_text
            
        except Exception as e:
            print(f"检查图片文字失败 {image_url}: {e}")
            return True  # 如果检查失败，假设有文字（保守处理）
    
    def find_image_without_center_text(self, restaurant_name: str, max_tries: int = 10) -> Optional[str]:
        """
        搜索餐厅图片，找到中间没有文字的图片
        
        Args:
            restaurant_name: 餐厅名称
            max_tries: 最大尝试次数
            
        Returns:
            图片URL，如果找不到则返回None
        """
        print(f"正在搜索餐厅图片: {restaurant_name}")
        
        # 搜索图片
        image_urls = self.search_images(restaurant_name, max_results=max_tries)
        
        if not image_urls:
            print(f"未找到餐厅图片: {restaurant_name}")
            return None
        
        print(f"找到 {len(image_urls)} 张图片，正在检查...")
        
        # 逐个检查图片中间是否有文字
        for idx, img_url in enumerate(image_urls, 1):
            print(f"检查图片 {idx}/{len(image_urls)}...")
            has_text = self.check_center_text(img_url)
            
            if not has_text:
                print(f"找到中间无文字的图片: {img_url[:50]}...")
                return img_url
            else:
                print(f"图片中间有文字，跳过")
        
        print(f"未找到中间无文字的图片，使用第一张图片")
        return image_urls[0] if image_urls else None
    
    def __del__(self):
        """清理资源"""
        if self.browser_page:
            try:
                self.browser_page.quit()
            except:
                pass


class ImageProcessor:
    """图片处理器 - 下载并处理图片（包括水印去除）"""
    
    def __init__(self):
        self.searcher = ImageSearcher()
        # 水印去除功能在download_image中直接实现
    
    def detect_text_regions(self, img_cv):
        """
        检测图片中的文字区域（用于水印去除）
        
        Args:
            img_cv: OpenCV格式的图片
            
        Returns:
            文字区域的mask
        """
        if not IMAGE_PROCESSING_AVAILABLE:
            return None
        
        try:
            h, w = img_cv.shape[:2]
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # 使用阈值检测文字（高对比度区域）
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 检测边缘
            edges = cv2.Canny(gray, 50, 150)
            
            # 形态学操作，连接文字区域
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            dilated = cv2.dilate(edges, kernel, iterations=2)
            
            # 查找轮廓
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 创建mask
            mask = np.zeros(gray.shape, dtype=np.uint8)
            
            # 根据图片大小动态设置最小面积
            min_area = max(50, (h * w) // 1000)  # 最小面积是图片面积的0.1%
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue
                
                # 计算长宽比
                x, y, w_rect, h_rect = cv2.boundingRect(contour)
                aspect_ratio = w_rect / h_rect if h_rect > 0 else 0
                
                # 过滤掉明显不是文字的轮廓（太宽或太窄）
                if aspect_ratio > 10 or aspect_ratio < 0.1:
                    continue
                
                # 绘制到mask上
                cv2.drawContours(mask, [contour], -1, 255, -1)
            
            # 限制整体mask面积，避免过度处理
            mask_area_ratio = np.sum(mask > 0) / (h * w)
            if mask_area_ratio > 0.3:  # 如果mask超过30%的图片面积，可能误检
                # 只保留面积较大的区域
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            return mask
            
        except Exception as e:
            print(f"检测文字区域失败: {e}")
            return None
    
    def remove_watermark_from_local_image(self, image_path: str) -> Optional[str]:
        """
        对本地图片文件去除水印
        
        Args:
            image_path: 本地图片路径
            
        Returns:
            处理后的图片路径（覆盖原文件），失败返回None
        """
        if not IMAGE_PROCESSING_AVAILABLE:
            return image_path
        
        try:
            # 读取图片
            img_cv = cv2.imread(image_path)
            if img_cv is None:
                return image_path
            
            h, w = img_cv.shape[:2]
            
            # 检测文字区域
            text_mask = self.detect_text_regions(img_cv)
            
            # 如果没有检测到文字，直接返回
            if text_mask is None or np.sum(text_mask) == 0:
                return image_path
            
            # 限制inpainting半径，避免过度处理
            img_size = max(h, w)
            inpaint_radius = min(3, max(1, img_size // 400))
            
            # 使用inpainting填充文字区域
            cleaned_img = cv2.inpaint(img_cv, text_mask, inpaint_radius, cv2.INPAINT_TELEA)
            
            # 保存处理后的图片（覆盖原文件）
            cv2.imwrite(image_path, cleaned_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            print(f"已去除图片水印: {image_path}")
            return image_path
            
        except Exception as e:
            print(f"去除水印失败 {image_path}: {e}")
            return image_path
    
    def download_image(self, image_url: str, save_path: str) -> Optional[str]:
        """
        下载图片并保存（会自动去除水印）
        
        Args:
            image_url: 图片URL
            save_path: 保存路径
            
        Returns:
            保存的路径，失败返回None
        """
        try:
            # 先下载图片
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            response = session.get(image_url, timeout=30, stream=True)
            if response.status_code != 200:
                return None
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 先保存到临时文件
            temp_path = save_path + '.tmp'
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 如果启用了图像处理，去除水印
            if IMAGE_PROCESSING_AVAILABLE:
                try:
                    # 读取图片并去除水印
                    img_cv = cv2.imread(temp_path)
                    if img_cv is not None:
                        # 检测文字区域
                        text_mask = self.detect_text_regions(img_cv)
                        
                        # 如果检测到文字，进行水印去除
                        if text_mask is not None and np.sum(text_mask) > 0:
                            h, w = img_cv.shape[:2]
                            img_size = max(h, w)
                            inpaint_radius = min(3, max(1, img_size // 400))
                            
                            # 使用inpainting填充文字区域
                            cleaned_img = cv2.inpaint(img_cv, text_mask, inpaint_radius, cv2.INPAINT_TELEA)
                            
                            # 保存处理后的图片
                            cv2.imwrite(save_path, cleaned_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                            os.remove(temp_path)  # 删除临时文件
                            print(f"已下载并去除水印: {save_path}")
                            return save_path
                
                except Exception as e:
                    print(f"水印去除异常: {e}，使用原始图片")
            
            # 如果没有去除水印或去除失败，移动临时文件到最终位置
            if os.path.exists(temp_path):
                os.rename(temp_path, save_path)
            
            return save_path
            
        except Exception as e:
            print(f"下载图片失败 {image_url}: {e}")
            return None
    
    def process_restaurant_image(self, restaurant_name: str, restaurant_address: str = "", save_path: str = None, fallback_image_url: str = None) -> Optional[str]:
        """
        处理餐厅图片：搜索并下载中间无文字的图片
        
        Args:
            restaurant_name: 餐厅名称
            restaurant_address: 餐厅地址（可选，用于搜索）
            save_path: 保存路径
            fallback_image_url: 备选图片URL（如果搜索失败，使用此图片）
            
        Returns:
            保存的图片路径，失败返回None
        """
        # 简化搜索关键词，只使用餐厅名称（去掉地址）
        search_keyword = restaurant_name.split()[0] if restaurant_name else restaurant_name
        
        # 搜索中间无文字的图片
        image_url = self.searcher.find_image_without_center_text(search_keyword, max_tries=10)
        
        # 如果搜索失败，使用备选图片
        if not image_url:
            if fallback_image_url:
                print(f"搜索失败，使用原帖图片: {restaurant_name}")
                image_url = fallback_image_url
            else:
                print(f"未找到合适的餐厅图片: {restaurant_name}")
                return None
        
        # 下载图片
        if save_path:
            saved_path = self.download_image(image_url, save_path)
            if saved_path:
                print(f"已下载餐厅图片: {saved_path}")
                return saved_path
            else:
                print(f"下载图片失败: {image_url[:50]}...")
                return None
        
        return image_url  # 如果没有指定保存路径，返回URL
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'searcher') and self.searcher:
            del self.searcher
