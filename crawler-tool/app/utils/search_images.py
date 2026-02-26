#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一图片搜索脚本
支持多种图片搜索方式：Bing搜索、高德地图API、AI生成关键词等
"""
import os
import sys
import json
import logging
import argparse
import requests
import time
import re
import random
from typing import List, Dict, Optional
from urllib.parse import quote, urlparse, urlunparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.database import db
from base.config import Config
from app.services.address_service import AddressService
from app.utils.image_utils import update_restaurant_images, build_tweets_query, process_restaurant_batch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BingImageSearcher:
    """Bing图片搜索器（使用DrissionPage模拟浏览器）"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.page = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.bing.com/'
        })
    
    def _cleanup_browser(self, page, port: int = None):
        """清理浏览器进程"""
        if not page:
            return
        try:
            from base.browser_cleanup import safe_close_browser
            safe_close_browser(page, port)
        except Exception as e:
            logger.warning(f"清理浏览器失败: {e}")
            # 最后尝试：强制清理进程
            if port:
                try:
                    from base.browser_cleanup import cleanup_chrome_processes
                    cleanup_chrome_processes(port)
                except:
                    pass
    
    def search_images_bing_browser(self, query: str, max_images: int = 3) -> List[str]:
        """使用浏览器搜索Bing图片"""
        image_urls = []
        page = None
        
        try:
            try:
                from DrissionPage._pages.chromium_page import ChromiumPage
                from DrissionPage import ChromiumOptions
            except ImportError:
                try:
                    from DrissionPage import ChromiumPage, ChromiumOptions
                except ImportError:
                    logger.warning("无法导入DrissionPage，回退到网页搜索")
                    return self.search_images_bing_web(query, max_images)
            
            options = ChromiumOptions()
            random_port = random.randint(9223, 9999)
            options.set_address(f'127.0.0.1:{random_port}')
            options.set_argument(f'--remote-debugging-port={random_port}')
            
            if self.headless:
                options.headless(True)
            options.set_argument('--no-sandbox')
            options.set_argument('--disable-blink-features=AutomationControlled')
            options.set_argument('--disable-dev-shm-usage')
            
            try:
                chrome_paths = [
                    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    '/Applications/Chromium.app/Contents/MacOS/Chromium',
                    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
                ]
                for chrome_path in chrome_paths:
                    if os.path.exists(chrome_path):
                        options.set_browser_path(chrome_path)
                        break
            except:
                pass
            
            try:
                page = ChromiumPage(options)
            except Exception as e:
                logger.warning(f"浏览器启动失败: {e}，回退到网页搜索")
                self._cleanup_browser(page, random_port)
                return self.search_images_bing_web(query, max_images)
            
            search_query = f"{query} 美食 食物 高清"
            encoded_query = quote(search_query)
            search_url = f"https://www.bing.com/images/search?q={encoded_query}&qft=+filterui:imagesize-large+filterui:photo-photo&FORM=IRFLTR"
            
            page.get(search_url)
            page.wait.doc_loaded()
            time.sleep(2)
            
            for _ in range(2):
                page.run_js("window.scrollBy(0, 500)")
                time.sleep(1)
            
            try:
                img_elements = page.eles('tag:img')
                for img in img_elements:
                    if len(image_urls) >= max_images:
                        break
                    try:
                        img_url = img.attr('src') or img.attr('data-src') or img.attr('data-lazy-src')
                        if img_url and img_url.startswith('http'):
                            if self._is_valid_image_url(img_url) and img_url not in image_urls:
                                if self.validate_image_url(img_url):
                                    image_urls.append(img_url)
                    except:
                        continue
                
                if len(image_urls) < max_images:
                    html_content = page.html
                    json_pattern = r'var _model = ({.*?});'
                    matches = re.findall(json_pattern, html_content, re.DOTALL)
                    for match in matches:
                        try:
                            data = json.loads(match)
                            self._extract_image_urls_from_json(data, image_urls, max_images)
                            if len(image_urls) >= max_images:
                                break
                        except:
                            continue
            except Exception as e:
                logger.warning(f"提取图片失败: {e}")
            
            # 验证并过滤URL
            unique_urls = []
            seen = set()
            for url in image_urls:
                if url not in seen:
                    # 双重验证：格式检查 + 实际访问验证
                    if self._is_valid_image_url(url):
                        if self.validate_image_url(url):
                            unique_urls.append(url)
                            seen.add(url)
                            if len(unique_urls) >= max_images:
                                break
                        else:
                            logger.debug(f"URL验证失败（不可访问）: {url[:50]}...")
                    else:
                        logger.debug(f"URL格式无效: {url[:50]}...")
            
            return unique_urls[:max_images]
            
        except Exception as e:
            logger.warning(f"浏览器搜索失败: {e}，回退到网页搜索")
            self._cleanup_browser(page, random_port)
            return self.search_images_bing_web(query, max_images)
        finally:
            self._cleanup_browser(page, random_port)
    
    def search_images_bing_web(self, query: str, max_images: int = 3) -> List[str]:
        """通过Bing网页搜索图片"""
        image_urls = []
        
        try:
            search_query = f"{query} 美食 食物 高清"
            encoded_query = quote(search_query)
            search_url = f"https://www.bing.com/images/search?q={encoded_query}&qft=+filterui:imagesize-large+filterui:photo-photo&FORM=IRFLTR"
            
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            html_content = response.text
            
            json_pattern = r'var _model = ({.*?});'
            matches = re.findall(json_pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    self._extract_image_urls_from_json(data, image_urls, max_images)
                    if len(image_urls) >= max_images:
                        break
                except:
                    continue
            
            if len(image_urls) < max_images:
                cleaned_html = html_content.replace('&quot;', '"').replace('&amp;', '&')
                murl_patterns = [
                    r'"murl"\s*:\s*"([^"]+)"',
                    r'murl["\']\s*:\s*["\']([^"\']+)["\']',
                ]
                for pattern in murl_patterns:
                    matches = re.findall(pattern, cleaned_html, re.IGNORECASE)
                    for url in matches:
                        url = url.strip().replace('&quot;', '').replace('&amp;', '&')
                        if url.startswith('http') and url not in image_urls:
                            if self._is_valid_image_url(url):
                                if self.validate_image_url(url):
                                    image_urls.append(url)
                                    if len(image_urls) >= max_images:
                                        break
                    if len(image_urls) >= max_images:
                        break
                
                if len(image_urls) < max_images:
                    img_patterns = [
                        r'https://[^"\s<>]+\.(jpg|jpeg|png|webp)(\?[^"\s<>]*)?',
                        r'https://[^"\s<>]+/images/[^"\s<>]+\.(jpg|jpeg|png|webp)',
                    ]
                    for pattern in img_patterns:
                        matches = re.findall(pattern, cleaned_html, re.IGNORECASE)
                        for match in matches:
                            url = match[0] if isinstance(match, tuple) else match
                            url = url.strip()
                            if '.html' in url.lower():
                                continue
                            if url.startswith('http') and url not in image_urls:
                                if self._is_valid_image_url(url):
                                    image_urls.append(url)
                                    if len(image_urls) >= max_images:
                                        break
                        if len(image_urls) >= max_images:
                            break
            
            if len(image_urls) < max_images:
                script_pattern = r'<script[^>]*>.*?murl.*?</script>'
                scripts = re.findall(script_pattern, cleaned_html, re.DOTALL | re.IGNORECASE)
                for script in scripts:
                    script = script.replace('&quot;', '"').replace('&amp;', '&')
                    murl_matches = re.findall(r'"murl"\s*:\s*"([^"]+)"', script, re.IGNORECASE)
                    for url in murl_matches:
                        url = url.strip()
                        if url.startswith('http') and url not in image_urls:
                            if self._is_valid_image_url(url):
                                if self.validate_image_url(url):
                                    image_urls.append(url)
                                    if len(image_urls) >= max_images:
                                        break
                    if len(image_urls) >= max_images:
                        break
            
            # 验证并过滤URL
            unique_urls = []
            seen = set()
            for url in image_urls:
                if url not in seen:
                    # 双重验证：格式检查 + 实际访问验证
                    if self._is_valid_image_url(url):
                        if self.validate_image_url(url):
                            unique_urls.append(url)
                            seen.add(url)
                            if len(unique_urls) >= max_images:
                                break
                        else:
                            logger.debug(f"URL验证失败（不可访问）: {url[:50]}...")
                    else:
                        logger.debug(f"URL格式无效: {url[:50]}...")
            
            return unique_urls[:max_images]
            
        except Exception as e:
            logger.warning(f"Bing搜索失败: {e}")
            return []
    
    def _extract_image_urls_from_json(self, data: dict, image_urls: List[str], max_images: int):
        """递归从JSON数据中提取图片URL"""
        if len(image_urls) >= max_images:
            return
        
        if isinstance(data, dict):
            for key in ['murl', 'imgurl', 'url', 'src', 'imageUrl', 'thumbnailUrl']:
                if key in data and isinstance(data[key], str):
                    url = data[key]
                    if url.startswith('http') and self._is_valid_image_url(url):
                        if self.validate_image_url(url):
                            if url not in image_urls:
                                image_urls.append(url)
                                if len(image_urls) >= max_images:
                                    return
            
            for value in data.values():
                self._extract_image_urls_from_json(value, image_urls, max_images)
                if len(image_urls) >= max_images:
                    return
        elif isinstance(data, list):
            for item in data:
                self._extract_image_urls_from_json(item, image_urls, max_images)
                if len(image_urls) >= max_images:
                    return
    
    def _is_valid_image_url(self, url: str) -> bool:
        """检查URL是否是有效的图片URL"""
        if not url or not url.startswith('http'):
            return False
        
        url = url.strip().replace('&quot;', '').replace('&amp;', '&')
        
        invalid_patterns = [
            r'\.(gif|svg|html)$',
            r'\.html\?',
            r'logo', r'avatar', r'icon', r'placeholder', r'data:image',
            r'&quot;', r'&amp;',
        ]
        
        url_lower = url.lower()
        for pattern in invalid_patterns:
            if re.search(pattern, url_lower):
                return False
        
        if url.count('"') % 2 != 0 or '","' in url or '":' in url:
            return False
        
        return True
    
    def validate_image_url(self, url: str) -> bool:
        """验证图片URL是否可访问（更严格的验证）"""
        if not url or not url.strip():
            return False
        
        url = url.strip()
        
        # 基本格式检查
        if not url.startswith('http'):
            return False
        
        # 检查是否是图片URL（排除HTML、SVG等）
        invalid_extensions = ['.html', '.htm', '.svg', '.gif']
        if any(url.lower().endswith(ext) for ext in invalid_extensions):
            return False
        
        # 检查URL中是否包含无效模式
        invalid_patterns = [
            'logo', 'avatar', 'icon', 'placeholder', 'data:image',
            '&quot;', '&amp;', '","', '":', 'headphoto', 'user',
            '0102c120008jgkcxjB98F',  # Trip.com 通用占位图
            # Trip.com banner/marketing assets（常见带品牌logo/文案，非餐厅实拍图）
            '/images/fd/tg/',
            # Trip.com 通用占位图（实测在库中出现）
            '05e2j12000cjsihpq0418',
            '05e5k12000cjsg4e48d91',
            '05e2z12000cjsfsqb7a2b',
            '05e5112000f3br0wz5303',
            '05E6e12000cjso3ro7BEE',
            '05E4f12000cjsls8g082A',
            '0M74z2224tibbx728D6EF',
            # 实测：翠湖广东乡下菜命中的banner（包含logo/文案）
            'cghzgvw7usiazm7daaa0kqyhcl8653',
            'huitu.com',  # Stock photos
            'nipic.com',  # Stock photos
            'nximg.cn',   # Nipic image server
            'pconline.com.cn', # Often unrelated blog images
            'ytimg.com',  # YouTube thumbnails
            'youtube.com', # YouTube
            'mc.yandex.ru', # Yandex tracking pixel
            '1mi2r12000j159k505CB1', # Trip.com user level badge (lv9)
            'CghzgVW7USqAL6kEAABDYVl5N3Y173', # Pizza Hut logo / Banner
            '0100d12000953lfww79B3',
            '10071a0000019stakE862',
            '100w0k000000cp3cm1818',
            'CggYHlX08oOAFufEAAF3YzRdmmg013' # Lao Da Chang incorrect image
        ]
        url_lower = url.lower()
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        # 检查是否包含尺寸限制（排除小图，如 _C_30_30_）
        size_match = re.search(r'_[CR]_(\d+)_(\d+)', url)
        if size_match:
            try:
                w, h = int(size_match.group(1)), int(size_match.group(2))
                if w < 100 or h < 100:  # 排除小于 100x100 的图片
                    return False
            except:
                pass
        
        # 尝试访问URL验证
        try:
            # 先尝试HEAD请求（更快）
            response = self.session.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                if 'image' in content_type:
                    return True
                # 如果HEAD请求成功但没有Content-Type，尝试GET请求检查文件头
                if not content_type:
                    response = self.session.get(url, timeout=5, stream=True, allow_redirects=True)
                    if response.status_code == 200:
                        chunk = response.raw.read(10)
                        if chunk:
                            # 检查图片文件头
                            image_signatures = [
                                b'\xff\xd8\xff',  # JPEG
                                b'\x89PNG\r\n',   # PNG
                                b'GIF87a',        # GIF
                                b'GIF89a',        # GIF
                            ]
                            for sig in image_signatures:
                                if chunk.startswith(sig):
                                    return True
                        return True  # 如果返回200，即使无法识别也认为可能有效
            
            # 如果HEAD失败，尝试GET请求
            else:
                response = self.session.get(url, timeout=5, stream=True, allow_redirects=True)
                if response.status_code == 200:
                    chunk = response.raw.read(10)
                    if chunk:
                        image_signatures = [
                            b'\xff\xd8\xff',  # JPEG
                            b'\x89PNG\r\n',   # PNG
                            b'GIF87a',        # GIF
                            b'GIF89a',        # GIF
                        ]
                        for sig in image_signatures:
                            if chunk.startswith(sig):
                                return True
                    return True  # 如果返回200，认为可能有效
            
            return False
        except requests.exceptions.Timeout:
            logger.debug(f"URL验证超时: {url}")
            return False
        except requests.exceptions.RequestException as e:
            logger.debug(f"URL验证失败: {url} - {e}")
            return False
        except Exception as e:
            logger.debug(f"验证URL时出错: {url} - {e}")
            return False
    
    def search_images(self, restaurant_name: str, restaurant_desc: str = "", 
                     city: str = "上海", max_images: int = 3) -> List[str]:
        """搜索餐厅图片"""
        # 使用更通用的搜索词，不限制在 Trip.com
        query = f"{restaurant_name} {city} 美食"
        if "店" not in restaurant_name and "馆" not in restaurant_name and "餐厅" not in restaurant_name:
             query = f"{restaurant_name} 餐厅 {city} 美食"
            
        # 移除 site:trip.com 限制，增加排除词
        # query = f"site:trip.com {query} 美食"
        
        # 优先使用Web搜索，避免浏览器环境问题
        return self.search_images_bing_web(query, max_images)


class AmapImageSearcher:
    """高德地图图片搜索器"""
    
    def __init__(self):
        self.address_service = AddressService()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search_images_from_amap(self, restaurant_name: str, city: str = "上海", max_images: int = 3) -> List[str]:
        """从高德地图API搜索餐厅图片"""
        try:
            address_result = self.address_service.search_restaurant_address(restaurant_name, city)
            if not address_result:
                return []
            
            amap_api_key = os.getenv('AMAP_API_KEY', '')
            if not amap_api_key:
                return []
            
            poi_id = address_result.get('poi_id')
            if not poi_id:
                url = "https://restapi.amap.com/v3/place/text"
                params = {
                    'key': amap_api_key,
                    'keywords': restaurant_name,
                    'city': city,
                    'types': '050000',
                    'output': 'json',
                    'offset': 1,
                    'page': 1,
                    'extensions': 'all'
                }
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '1' and data.get('count') != '0':
                        pois = data.get('pois', [])
                        if pois:
                            poi = pois[0]
                            photos = poi.get('photos', [])
                            if photos:
                                return [photo.get('url', '') for photo in photos[:max_images] if photo.get('url')]
                            poi_id = poi.get('id', '')
                            if poi_id:
                                return self._get_images_from_poi_detail(poi_id, amap_api_key, max_images)
            elif poi_id:
                return self._get_images_from_poi_detail(poi_id, amap_api_key, max_images)
            
            return []
        except Exception as e:
            logger.warning(f"从高德API搜索图片失败: {e}")
            return []
    
    def _get_images_from_poi_detail(self, poi_id: str, api_key: str, max_images: int = 3) -> List[str]:
        """从高德POI详情接口获取图片"""
        try:
            url = "https://restapi.amap.com/v3/place/detail"
            params = {'key': api_key, 'id': poi_id, 'output': 'json', 'extensions': 'all'}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1':
                    pois = data.get('pois', [])
                    if pois:
                        photos = pois[0].get('photos', [])
                        if photos:
                            return [photo.get('url', '') for photo in photos[:max_images] if photo.get('url')]
            return []
        except Exception as e:
            logger.warning(f"获取POI详情图片失败: {e}")
            return []
    
    def validate_image_url(self, url: str) -> bool:
        """验证图片URL是否有效（更严格的验证）"""
        if not url or not url.strip():
            return False
        
        url = url.strip()
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 检查是否是图片URL（排除HTML、SVG等）
            invalid_extensions = ['.html', '.htm', '.svg']
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in invalid_extensions):
                return False
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            has_image_extension = any(path_lower.endswith(ext) for ext in valid_extensions)
            
            # 如果有图片扩展名，直接返回True
            if has_image_extension:
                # 但还是要验证URL是否可访问
                try:
                    response = self.session.head(url, timeout=5, allow_redirects=True)
                    return response.status_code == 200
                except:
                    return False
            
            # 如果没有扩展名，检查Content-Type
            try:
                response = self.session.head(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'image' in content_type:
                        return True
                    # 如果没有Content-Type，尝试GET请求检查文件头
                    if not content_type:
                        response = self.session.get(url, timeout=5, stream=True, allow_redirects=True)
                        if response.status_code == 200:
                            chunk = response.raw.read(10)
                            if chunk:
                                image_signatures = [
                                    b'\xff\xd8\xff',  # JPEG
                                    b'\x89PNG\r\n',   # PNG
                                ]
                                for sig in image_signatures:
                                    if chunk.startswith(sig):
                                        return True
                            return True  # 如果返回200，认为可能有效
                return False
            except requests.exceptions.Timeout:
                return False
            except requests.exceptions.RequestException:
                return False
        except Exception:
            return False
    
    def search_images(self, restaurant_name: str, restaurant_desc: str = "", 
                     city: str = "上海", max_images: int = 3) -> List[str]:
        """搜索餐厅图片"""
        return self.search_images_from_amap(restaurant_name, city, max_images)


def create_searcher(method: str = "bing") -> object:
    """
    创建图片搜索器实例
    
    Args:
        method: 搜索方式 ("bing" 或 "amap")
        
    Returns:
        搜索器实例
    """
    if method.lower() == "bing":
        return BingImageSearcher()
    elif method.lower() == "amap":
        return AmapImageSearcher()
    else:
        logger.warning(f"未知的搜索方式: {method}，使用Bing搜索")
        return BingImageSearcher()


def process_restaurants(limit: Optional[int] = None, city: Optional[str] = None, 
                       tweet_id: Optional[int] = None, skip_existing: bool = True,
                       since_time: Optional[str] = None, method: str = "bing") -> Dict:
    """
    处理数据库中的餐厅，搜索并上传图片
    
    Args:
        limit: 处理数量限制
        city: 城市筛选（可选）
        tweet_id: 指定推文ID（可选）
        skip_existing: 是否跳过已有图片的记录
        since_time: 起始时间（格式：YYYY-MM-DD HH:MM:SS）
        method: 搜索方式 ("bing" 或 "amap")
        
    Returns:
        处理结果统计
    """
    searcher = create_searcher(method)
    
    try:
        query, params = build_tweets_query(
            tweet_id=tweet_id,
            city=city,
            since_time=since_time,
            skip_existing=skip_existing,
            limit=limit
        )
        
        restaurants = db.execute_query(query, params)
        return process_restaurant_batch(restaurants, searcher, skip_existing)
        
    except Exception as e:
        logger.error(f"处理餐厅失败: {e}", exc_info=True)
        return {
            'total': 0,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [f"处理失败: {str(e)}"]
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='统一图片搜索脚本 - 支持Bing和高德地图搜索',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用Bing搜索（默认）
  python3 search_images.py --method bing
  
  # 使用高德地图API搜索
  python3 search_images.py --method amap
  
  # 处理指定城市的餐厅
  python3 search_images.py --city 上海 --method bing
  
  # 处理指定数量的餐厅
  python3 search_images.py --limit 10 --method bing
  
  # 处理2025-11-07 17:03:36之后的数据
  python3 search_images.py --since-time "2025-11-07 17:03:36" --method bing
  
  # 强制更新所有餐厅（包括已有图片的）
  python3 search_images.py --force --method bing
        """
    )
    
    parser.add_argument('--method', type=str, default='bing', 
                       choices=['bing', 'amap'],
                       help='搜索方式：bing（Bing搜索，默认）或 amap（高德地图API）')
    parser.add_argument('--city', type=str, help='城市筛选（只处理该城市的餐厅）')
    parser.add_argument('--limit', type=int, help='处理数量限制')
    parser.add_argument('--tweet-id', type=int, help='指定推文ID（只处理该推文）')
    parser.add_argument('--force', action='store_true', help='强制更新（包括已有图片的餐厅）')
    parser.add_argument('--since-time', type=str, help='起始时间（格式：YYYY-MM-DD HH:MM:SS）')
    
    args = parser.parse_args()
    
    try:
        method_name = "Bing搜索" if args.method == "bing" else "高德地图API"
        logger.info("=" * 80)
        logger.info(f"开始使用{method_name}搜索并上传高清食物图片")
        logger.info("=" * 80)
        
        stats = process_restaurants(
            limit=args.limit,
            city=args.city,
            tweet_id=args.tweet_id,
            skip_existing=not args.force,
            since_time=args.since_time,
            method=args.method
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("处理完成")
        logger.info("=" * 80)
        logger.info(f"总计: {stats['total']} 个")
        logger.info(f"已处理: {stats['processed']} 个")
        logger.info(f"成功: {stats['success']} 个")
        logger.info(f"失败: {stats['failed']} 个")
        logger.info(f"跳过: {stats['skipped']} 个")
        
        if stats['errors']:
            logger.warning(f"\n错误列表（共 {len(stats['errors'])} 个）:")
            for error in stats['errors'][:10]:
                logger.warning(f"  - {error}")
            if len(stats['errors']) > 10:
                logger.warning(f"  ... 还有 {len(stats['errors']) - 10} 个错误未显示")
        
    except KeyboardInterrupt:
        logger.info("\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

