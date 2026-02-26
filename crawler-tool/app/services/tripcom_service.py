#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trip.com 餐厅爬虫模块 - 基于 DrissionPage (搜索) + requests (详情)
"""
import os
import sys
import time
import random
import json
import logging
import re
from typing import List, Dict, Optional, Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from DrissionPage import ChromiumPage
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, quote
from collections import Counter

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from bs4 import BeautifulSoup
import zhconv  # 繁体转简体
from base.config import Config

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    HAS_DRISSION = True
except ImportError:
    HAS_DRISSION = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def traditional_to_simplified(text: str) -> str:
    """将繁体中文转换为简体中文"""
    if not text:
        return text
    try:
        return zhconv.convert(text, 'zh-cn')
    except Exception:
        return text


def fetch_restaurant_detail_browser(page: 'ChromiumPage', detail_url: str, extract_address: bool = True, extract_comments: bool = False, min_image_size: int = 200, max_images: int = 20) -> Optional[Dict]:
    """
    使用浏览器访问餐厅详情页并提取详细信息（地址、图片和评论）
    模拟人操作：点击链接进入详情页
    
    Args:
        page: 浏览器页面实例
        detail_url: 详情页URL
        extract_address: 是否提取地址（默认True）
        extract_comments: 是否提取评论（默认False，跳过评论提取以加快速度）
        min_image_size: 最小图片尺寸（宽或高），默认200
        max_images: 最大提取图片数量，默认20
    
    Returns:
        包含 address, images, comments 的字典
    """
    if not HAS_DRISSION:
        logger.warning("未安装 DrissionPage，无法使用浏览器访问详情页")
        return None
    
    try:
        logger.debug(f"正在访问详情页: {detail_url}")
        
        # 模拟人操作：点击链接进入详情页
        page.get(detail_url)
        page.wait.load_start(timeout=6)  # 减少超时时间
        
        # 等待页面加载完成（减少等待时间）
        time.sleep(random.uniform(0.3, 0.6))  # 进一步减少等待时间
        
        # 快速滚动一次，让页面加载更多内容（异步，不等待）
        try:
            page.run_js("window.scrollBy(0, 500)")
            time.sleep(random.uniform(0.2, 0.3))  # 进一步减少等待时间
        except:
            pass
        
        result = {'address': '', 'images': [], 'comments': [], 'price_range': ''}
        
        # === 0. 提取价格标识（优先提取） ===
        try:
            # 从页面HTML中提取价格标识
            page_text = page.html
            soup = BeautifulSoup(page_text, 'html.parser')
            
            # 策略1: 查找包含价格标识的特定元素（更精确）
            # 价格标识通常在评价数（如 8條評價）和菜系标签（如 快餐）的同一行或附近
            # 格式通常是：8條評價 | 快餐 | 其他快餐 | $ 或 $$-$$$ 等
            # 优先匹配范围格式（如 $$-$$$），如果找不到再匹配单个格式（如 $$$$）
            
            # 查找包含评价数的元素（如 "8條評價"）
            for elem in soup.find_all(['span', 'div']):
                elem_text = elem.get_text(strip=True)
                # 查找包含评价数格式的元素（如 "8條評價"）
                if re.search(r'\d+\s*(?:条|條)\s*(?:评|評)', elem_text):
                    # 在同一容器（父元素）中查找价格标识
                    # 找到什么格式就用什么格式，不需要区分优先级
                    parent = elem.parent
                    if parent:
                        # 在父容器中查找价格标识（无论是范围格式还是单个格式）
                        for sibling in parent.find_all(['span', 'div']):
                            sibling_text = sibling.get_text(strip=True)
                            # 价格标识通常很短，且只包含$和-符号
                            if '$' in sibling_text and len(sibling_text.strip()) < 20:
                                # 清理文本，移除所有非$和-的字符，用于判断格式
                                clean_text = re.sub(r'[^$\-]', '', sibling_text)
                                
                                # 尝试匹配范围格式（如 $$-$$$）
                                if '-' in clean_text:
                                    range_match = re.search(r'(\$+\s*-\s*\$+)', sibling_text)
                                    if range_match:
                                        price_str = range_match.group(1).strip()
                                        # 验证：确保是有效的范围格式
                                        parts = price_str.split('-')
                                        if len(parts) == 2:
                                            start_dollars = parts[0].strip().count('$')
                                            end_dollars = parts[1].strip().count('$')
                                            if 1 <= start_dollars <= 5 and 1 <= end_dollars <= 5:
                                                result['price_range'] = price_str
                                                logger.info(f"✅ 从HTML元素提取到价格标识（范围格式）: {result['price_range']}")
                                                break
                                # 尝试匹配单个价格标识（如 $$$$）
                                elif not '-' in clean_text:
                                    # 匹配单个价格标识（元素文本应该只包含$符号，没有其他字符）
                                    if re.match(r'^\s*\$+\s*$', sibling_text):
                                        price_str = re.sub(r'\s', '', sibling_text)  # 移除空格
                                        dollar_count = price_str.count('$')
                                        if 1 <= dollar_count <= 5:
                                            result['price_range'] = price_str
                                            logger.info(f"✅ 从HTML元素提取到价格标识（单个格式）: {result['price_range']}")
                                            break
                        
                        # 如果找到了价格标识，退出外层循环
                        if result['price_range']:
                            break
            
            # 如果没在评价数附近找到，查找所有包含$符号的元素
            # 找到什么格式就用什么格式，不需要区分优先级
            if not result['price_range']:
                for elem in soup.find_all(['span', 'div', 'p', 'td', 'li']):
                    elem_text = elem.get_text(strip=True)
                    # 价格标识通常很短，且只包含$和-符号
                    if '$' in elem_text and len(elem_text.strip()) < 20:
                        # 清理文本，移除所有非$和-的字符，用于判断格式
                        clean_text = re.sub(r'[^$\-]', '', elem_text)
                        
                        # 尝试匹配范围格式（如 $$-$$$）
                        if '-' in clean_text:
                            range_match = re.search(r'(\$+\s*-\s*\$+)', elem_text)
                            if range_match:
                                price_str = range_match.group(1).strip()
                                # 验证：确保是有效的范围格式
                                parts = price_str.split('-')
                                if len(parts) == 2:
                                    start_dollars = parts[0].strip().count('$')
                                    end_dollars = parts[1].strip().count('$')
                                    if 1 <= start_dollars <= 5 and 1 <= end_dollars <= 5:
                                        result['price_range'] = price_str
                                        logger.info(f"✅ 从HTML元素提取到价格标识（范围格式）: {result['price_range']}")
                                        break
                        # 尝试匹配单个价格标识（如 $$$$）
                        elif not '-' in clean_text:
                            # 匹配单个价格标识（元素文本应该只包含$符号，没有其他字符）
                            if re.match(r'^\s*\$+\s*$', elem_text):
                                price_str = re.sub(r'\s', '', elem_text)  # 移除空格
                                dollar_count = price_str.count('$')
                                if 1 <= dollar_count <= 5:
                                    result['price_range'] = price_str
                                    logger.info(f"✅ 从HTML元素提取到价格标识（单个格式）: {result['price_range']}")
                                    break
            
            # 策略2: 如果策略1没找到，从完整文本中提取
            if not result['price_range']:
                full_text = soup.get_text(separator=' ', strip=True)
                
                # 先尝试匹配范围格式（如 $$-$$$）
                range_match = re.search(r'(\$+\s*-\s*\$+)', full_text)
                if range_match:
                    price_str = range_match.group(1).strip()
                    # 验证范围格式
                    parts = price_str.split('-')
                    if len(parts) == 2:
                        start_dollars = parts[0].strip().count('$')
                        end_dollars = parts[1].strip().count('$')
                        if 1 <= start_dollars <= 5 and 1 <= end_dollars <= 5:
                            result['price_range'] = price_str
                            logger.info(f"✅ 从文本提取到价格标识（范围格式）: {result['price_range']}")
                
                # 如果没有范围格式，再匹配单个价格标识
                if not result['price_range']:
                    # 使用更严格的正则，确保匹配的是独立的价格标识（前后是空格、标点或行首/行尾）
                    single_match = re.search(r'(?<![$\-])(\$+)(?![$\-])', full_text)
                    if single_match:
                        price_str = single_match.group(1).strip()
                        dollar_count = price_str.count('$')
                        if 1 <= dollar_count <= 5:
                            result['price_range'] = price_str
                            logger.info(f"✅ 从文本提取到价格标识（单个格式）: {result['price_range']}")
        except Exception as e:
            logger.debug(f"提取价格标识失败: {e}")
        
        # === 1. 提取地址（可选） ===
        if extract_address:
            try:
                # 尝试多种选择器查找地址
                address_selectors = [
                '[class*="address"]',
                '[class*="location"]',
                '[class*="position"]',
                '[class*="addr"]'
            ]
                
                # 优化：使用更短的超时，快速查找
                for selector in address_selectors:
                    try:
                        elems = page.eles(f'css:{selector}')
                        # 只检查前5个元素，加快速度
                        for elem in elems[:5]:
                            try:
                                text = elem.text.strip()
                                if 5 < len(text) < 80 and not re.search(r'评价|评分|推荐|营业|预订|电话|地图', text):
                                    if '新华路151号' not in text:
                                        result['address'] = traditional_to_simplified(text)
                                        logger.info(f"✅ 提取到地址: {result['address']}")
                                        break
                            except:
                                continue
                        if result['address']:
                            break
                    except:
                        continue
                
                    # 如果还没找到，尝试从页面HTML中搜索
                    if not result['address']:
                        try:
                            page_text = page.html
                            soup = BeautifulSoup(page_text, 'html.parser')
                            
                            # 策略1: 查找包含地址特征的元素
                            potential_addrs = soup.find_all(['span', 'div', 'p'], class_=re.compile(r'address|location|position', re.I))
                            for p in potential_addrs:
                                text = p.get_text(strip=True)
                                if 5 < len(text) < 80 and not re.search(r'评价|评分|推荐|营业|预订|电话|地图', text):
                                    if '新华路151号' not in text:
                                        result['address'] = traditional_to_simplified(text)
                                        logger.info(f"✅ 从HTML class提取到地址: {result['address']}")
                                        break
                            
                            # 策略2: 查找包含地址特征词的文本
                            if not result['address']:
                                potential_addrs = soup.find_all(['span', 'div', 'p'], string=re.compile(r'.*[省市区县路街巷道号].*|.*出口.*'))
                                for p in potential_addrs:
                                    text = p.get_text(strip=True)
                                    if 5 < len(text) < 50 and not re.search(r'评价|评分|推荐|营业|预订|电话|地图|ICP|版权', text):
                                        if '新华路151号' not in text:
                                            result['address'] = traditional_to_simplified(text)
                                            logger.info(f"✅ 从文本提取到地址: {result['address']}")
                                            break
                        except Exception as e:
                            logger.debug(f"从HTML提取地址失败: {e}")
            except Exception as e:
                logger.debug(f"提取地址失败: {e}")
        
        # === 2. 提取评论和评论中的图片（可选） ===
        if extract_comments:
            try:
                # 快速滚动到评论区域（减少等待时间）
                page.run_js("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(0.5, 0.8))  # 减少等待时间
                
                # 尝试点击"查看更多评论"或"加载更多"按钮（快速查找，超时更短）
                try:
                    # 使用更精确的选择器，快速查找
                    btn = page.ele(f'xpath://*[contains(text(), "更多") or contains(text(), "more")]', timeout=0.5)
                    if btn:
                        btn.click()
                        time.sleep(random.uniform(0.3, 0.5))  # 减少等待时间
                except:
                    pass
                
                # 提取评论（优化：使用更精确的选择器，减少查找时间）
                comment_selectors = [
                    '[class*="review-item"]',
                    '[class*="comment-item"]',
                    '[class*="review-content"]',
                    '[class*="comment-content"]',
                    '[class*="review"]',
                    '[class*="comment"]'
                ]
                
                seen_comments = set()
                for selector in comment_selectors:
                    try:
                        # 添加超时保护：使用 try-except 包装，限制执行时间
                        comment_elems = page.eles(f'css:{selector}')
                    except Exception as e:
                        logger.debug(f"获取评论元素失败: {e}")
                        continue
                    
                    # 限制检查数量，加快速度（只检查前15个元素，足够找到图片）
                    for elem in comment_elems[:15]:  # 减少检查数量，加快速度
                        try:
                            # 提取评论文本
                            comment_text = elem.text.strip()
                            if not comment_text or len(comment_text) < 10:
                                continue
                            
                            # 过滤掉不是评论的内容
                            if any(keyword in comment_text for keyword in ['评分', '评分:', 'Rating', '地址', '电话']):
                                continue
                            
                            # 检查是否是重复评论
                            comment_hash = hash(comment_text[:50])
                            if comment_hash in seen_comments:
                                continue
                            seen_comments.add(comment_hash)
                            
                            # 提取用户名（如果有）
                            username = ""
                            try:
                                user_elem = elem.ele('css:[class*="user"], css:[class*="author"], css:[class*="name"]', timeout=0.1)
                                if user_elem:
                                    username = user_elem.text.strip()
                            except:
                                pass
                            
                            # 提取评分（如果有）
                            rating = None
                            try:
                                rating_elem = elem.ele('css:[class*="rating"], css:[class*="score"], css:.star', timeout=0.1)
                                if rating_elem:
                                    rating_text = rating_elem.text.strip()
                                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                                    if rating_match:
                                        rating = float(rating_match.group(1))
                            except:
                                pass
                            
                            # 从评论元素中提取图片
                            comment_images = []
                            try:
                                # 在评论元素内查找图片（添加超时保护）
                                img_elems = []
                                try:
                                    img_elems = elem.eles('css:img')
                                except Exception as e:
                                    logger.debug(f"获取图片元素失败: {e}")
                                    continue
                                
                                for img_elem in img_elems:
                                    try:
                                        src = img_elem.attr('src') or img_elem.attr('data-src') or img_elem.attr('data-lazy-src')
                                        if not src or not src.startswith('http'):
                                            continue
                                        
                                        # 过滤小图/头像/图标
                                        if any(k in src.lower() for k in ['avatar', 'head', 'icon', 'logo', 'facebook', 'twitter', 'youtube', 'instagram', 'social', 'payment', 'wechat', 'scan', 'code', 'qrcode', 'tripcdn.com/packages']):
                                            continue
                                        if '_C_' in src and ('_30_30' in src or '_50_50' in src):
                                            continue
                                        
                                        # 检查图片尺寸（通过URL中的尺寸信息或属性）
                                        # Trip.com 图片URL通常包含尺寸信息
                                        # 只保留较大的图片（宽度或高度大于 min_image_size）
                                        size_match = re.search(r'[_-](\d+)[_-](\d+)[_-]', src)
                                        if size_match:
                                            w, h = int(size_match.group(1)), int(size_match.group(2))
                                            if w < min_image_size or h < min_image_size:
                                                logger.info(f"    ℹ️ 图片尺寸检查: {w}x{h} (阈值: {min_image_size}) -> ❌ 过滤")
                                                continue
                                            else:
                                                logger.info(f"    ℹ️ 图片尺寸检查: {w}x{h} (阈值: {min_image_size}) -> ✅ 通过")
                                        else:
                                            logger.info(f"    ℹ️ 图片无尺寸信息，保留: {src[-30:]}...")
                                        
                                        if src not in result['images']:
                                            result['images'].append(src)
                                            comment_images.append(src)
                                        if len(result['images']) >= max_images:  # 减少到max_images张图片，加快速度
                                            break
                                    except:
                                        continue
                            except:
                                pass
                            
                            result['comments'].append({
                                'username': username,
                                'content': traditional_to_simplified(comment_text),
                                'rating': rating,
                                'images': comment_images
                            })
                            
                            # 如果已经找到足够的图片，可以提前退出
                            if len(result['images']) >= max_images:
                                break
                            if len(result['comments']) >= 10:  # 减少到10条评论，加快速度
                                break
                        except:
                            continue
                    # 如果已经找到足够的图片，可以提前退出
                    if len(result['images']) >= 5:
                        break
                    if len(result['comments']) >= 10:
                        break
                
                if result['comments']:
                    logger.info(f"✅ 提取到 {len(result['comments'])} 条评论")
                
                if result['images']:
                    logger.info(f"✅ 从评论中提取到 {len(result['images'])} 张图片")
            except Exception as e:
                logger.debug(f"提取评论和图片失败: {e}")
        
        # === 3. 如果评论中没有图片，尝试从页面其他地方提取图片（仅在需要时） ===
        # 如果只需要价格标识，跳过图片提取
        # 注意：现在即使 extract_comments=False，如果 result['images'] 为空，我们也要尝试提取页面图片
        if not result['images']:
            try:
                logger.info("尝试从页面其他地方提取图片...")
                # 尝试从页面HTML中提取图片
                try:
                    page_text = page.html
                    soup = BeautifulSoup(page_text, 'html.parser')
                    
                    # 策略1: 从相册容器提取
                    gallery = soup.find_all(['div', 'ul'], class_=re.compile(r'gallery|photo|image', re.I))
                    for container in gallery:
                        imgs = container.find_all('img')
                        for img in imgs:
                            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                            if src and src.startswith('http') and src not in result['images']:
                                # 过滤小图/头像
                                if any(k in src.lower() for k in ['avatar', 'head', 'icon', 'logo', 'facebook', 'twitter', 'youtube', 'instagram', 'social', 'payment', 'wechat', 'scan', 'code', 'qrcode', 'tripcdn.com/packages']):
                                    continue
                                if '_C_' in src and ('_30_30' in src or '_50_50' in src):
                                    continue
                                
                                # 检查图片尺寸
                                size_match = re.search(r'[_-](\d+)[_-](\d+)[_-]', src)
                                if size_match:
                                    w, h = int(size_match.group(1)), int(size_match.group(2))
                                    logger.info(f"    🔍 检查图片尺寸: {w}x{h} (src: {src[:50]}...)")
                                    if w < min_image_size or h < min_image_size:
                                        logger.info(f"    ⚠️ 过滤低清图: {w}x{h} < {min_image_size}")
                                        continue
                                
                                result['images'].append(src)
                                if len(result['images']) >= 5:
                                    break
                        if len(result['images']) >= 5:
                            break
                    
                    # 策略2: 提取页面大图
                    if len(result['images']) < 5:
                        all_imgs = soup.find_all('img')
                        for img in all_imgs:
                            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                            if src and src.startswith('http') and src not in result['images']:
                                # 严格过滤
                                if any(k in src.lower() for k in ['avatar', 'head', 'icon', 'logo', 'facebook', 'twitter', 'youtube', 'instagram', 'social', 'payment', 'wechat', 'scan', 'code', 'qrcode', 'tripcdn.com/packages']):
                                    continue
                                
                                # 检查图片尺寸
                                size_match = re.search(r'[_-](\d+)[_-](\d+)[_-]', src)
                                if size_match:
                                    w, h = int(size_match.group(1)), int(size_match.group(2))
                                    logger.info(f"    🔍 检查图片尺寸: {w}x{h} (src: {src[:50]}...)")
                                    if w < min_image_size or h < min_image_size:
                                        logger.info(f"    ⚠️ 过滤低清图: {w}x{h} < {min_image_size}")
                                        continue
                                
                                result['images'].append(src)
                                if len(result['images']) >= 5:
                                    break
                    
                    if result['images']:
                        logger.info(f"✅ 从页面其他地方提取到 {len(result['images'])} 张图片")
                except Exception as e:
                    logger.debug(f"从页面HTML提取图片失败: {e}")
            except Exception as e:
                logger.debug(f"提取页面图片失败: {e}")
        
        return result
        
    except Exception as e:
        logger.warning(f"获取详情页失败: {e}")
        return None


def fetch_restaurant_detail(session, detail_url: str, max_images: int = 20) -> Optional[Dict]:
    """
    请求餐厅详情页并提取详细信息（地址和图片）
    保留此函数以兼容旧代码，但推荐使用 fetch_restaurant_detail_browser
    """
    try:
        logger.info(f"正在请求详情页获取信息: {detail_url}")
        # 稍微延迟一下，避免请求过快
        time.sleep(random.uniform(0.5, 1.5))
        
        response = session.get(detail_url, timeout=20)
        if response.status_code != 200:
            logger.warning(f"请求详情页失败，状态码: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        result = {'address': '', 'images': []}
        
        # === 1. 提取地址 ===
        # 策略1: 优先从 HTML 文本中提取地址
        addr_candidates = soup.find_all(['div', 'span', 'p'], class_=re.compile(r'address|location|position', re.I))
        for candidate in addr_candidates:
            text = candidate.get_text(strip=True)
            if 5 < len(text) < 80 and not re.search(r'评价|评分|推荐|营业|预订|电话|地图', text):
                result['address'] = traditional_to_simplified(text)
                logger.info(f"✅ 从 HTML class 提取到地址: {result['address']}")
                break
        
        # 策略2: 查找包含地址特征词的元素
        if not result['address']:
            potential_addrs = soup.find_all(['span', 'div', 'p'], string=re.compile(r'.*[省市区县路街巷道号].*|.*出口.*'))
            for p in potential_addrs:
                text = p.get_text(strip=True)
                if 5 < len(text) < 50 and not re.search(r'评价|评分|推荐|营业|预订|电话|地图|ICP|版权', text):
                    if '新华路151号' in text: continue
                    result['address'] = traditional_to_simplified(text)
                    logger.info(f"✅ 从文本特征提取到地址: {result['address']}")
                    break

        # 策略3: 查找 JSON-LD 数据 (地址)
        if not result['address']:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if item.get('@type') in ['Restaurant', 'FoodEstablishment', 'LocalBusiness']:
                            addr_obj = item.get('address')
                            addr_str = ""
                            if isinstance(addr_obj, str):
                                addr_str = addr_obj
                            elif isinstance(addr_obj, dict):
                                parts = []
                                if addr_obj.get('addressLocality'): parts.append(addr_obj['addressLocality'])
                                if addr_obj.get('streetAddress'): parts.append(addr_obj['streetAddress'])
                                addr_str = "".join(parts)
                            
                            if addr_str:
                                final_addr = traditional_to_simplified(addr_str)
                                if '新华路151号' not in final_addr:
                                    result['address'] = final_addr
                                    logger.info(f"✅ 从 JSON-LD 提取到地址: {result['address']}")
                                    break
                    if result['address']: break
                except: pass

        # === 2. 提取图片 (最多3张) ===
        # 策略1: 从 JSON-LD 提取 (质量最高)
        if not result['images']:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if 'image' in item:
                            imgs = item['image']
                            if isinstance(imgs, str): imgs = [imgs]
                            for img in imgs:
                                if img and img.startswith('http') and img not in result['images']:
                                    result['images'].append(img)
                                    if len(result['images']) >= 3: break
                        if len(result['images']) >= 3: break
                    if len(result['images']) >= 3: break
                except: pass
        
        # 策略2: 从相册容器提取
        if len(result['images']) < 3:
            gallery = soup.find_all(['div', 'ul'], class_=re.compile(r'gallery|photo|image', re.I))
            for container in gallery:
                imgs = container.find_all('img')
                for img in imgs:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src and src.startswith('http') and src not in result['images']:
                        # 过滤小图/头像
                        if any(k in src for k in ['avatar', 'head', 'icon']): continue
                        if '_C_' in src and ('_30_30' in src or '_50_50' in src): continue
                        
                        result['images'].append(src)
                        if len(result['images']) >= 3: break
                if len(result['images']) >= 3: break

        # 策略3: 提取页面大图
        if len(result['images']) < 3:
            # 查找所有图片，但优先查找可能的大图容器
            # 许多 Trip.com 页面使用特定的 class 容器来展示相册
            all_imgs = soup.find_all('img')
            
            # 添加更多潜在的图片选择器，以应对不同页面结构
            if not result['images']: # 只在还没有找到图片时尝试动态查找，避免重复
                try:
                    # 尝试从页面元素中直接获取 img 标签 (drissionpage 方式)
                    img_elements = page.eles('tag:img')
                    for img_ele in img_elements:
                        src = img_ele.attr('src') or img_ele.attr('data-src') or img_ele.attr('data-lazy-src')
                        if src and src.startswith('http'):
                             if src not in result['images']:
                                # 同样的过滤逻辑
                                if any(k in src.lower() for k in ['avatar', 'head', 'icon', 'logo', 'facebook', 'twitter', 'youtube', 'instagram', 'social', 'payment', 'wechat', 'scan', 'code', 'qrcode', 'tripcdn.com/packages']):
                                    continue
                                
                                # 检查图片尺寸
                                size_match = re.search(r'[_-](\d+)[_-](\d+)[_-]', src)
                                if size_match:
                                    w, h = int(size_match.group(1)), int(size_match.group(2))
                                    if w < min_image_size or h < min_image_size:
                                        logger.info(f"    ⚠️ 过滤低清图 (动态元素): {w}x{h} < {min_image_size}")
                                        continue
                                
                                result['images'].append(src)
                                if len(result['images']) >= 3:
                                    break
                except:
                    pass

            for img in all_imgs:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src and src.startswith('http') and src not in result['images']:
                    # 严格过滤
                    if any(k in src.lower() for k in ['avatar', 'head', 'icon', 'logo', 'facebook', 'twitter', 'youtube', 'instagram', 'social', 'payment', 'wechat', 'scan', 'code', 'qrcode', 'tripcdn.com/packages']): continue
                    
                    # 检查 HTML 属性中的尺寸
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w < min_image_size or h < min_image_size:
                                logger.info(f"    ⚠️ 过滤低清图 (HTML属性): {w}x{h} < {min_image_size}")
                                continue
                        except:
                            pass
                    
                    # 检查图片尺寸 (从 URL)
                    size_match = re.search(r'[_-](\d+)[_-](\d+)[_-]', src)
                    if size_match:
                        w, h = int(size_match.group(1)), int(size_match.group(2))
                        logger.info(f"    🔍 检查图片尺寸: {w}x{h} (src: {src[:50]}...)")
                        if w < min_image_size or h < min_image_size:
                            logger.info(f"    ⚠️ 过滤低清图 (URL): {w}x{h} < {min_image_size}")
                            continue
                    
                    result['images'].append(src)
                    if len(result['images']) >= 3: break

        # 策略4: 专门针对 Trip.com 新版详情页的相册结构
        if len(result['images']) < 3:
            try:
                # 尝试点击相册/更多图片按钮，展开更多图片
                # 查找类似 "全部 x 张照片" 或相册入口
                album_btn = page.ele('xpath://*[contains(text(), "照片") or contains(text(), "Photos") or contains(text(), "全部")]', timeout=1)
                if album_btn:
                    # 不点击，只是作为定位参考，查找附近的图片
                    # 或者尝试直接在页面中查找大图容器
                    pass
                
                # 查找具有大尺寸背景图的元素 (style="background-image: url(...)")
                bg_elems = page.eles('css:[style*="background-image"]', timeout=1)
                for elem in bg_elems:
                    style = elem.attr('style')
                    if style:
                        bg_match = re.search(r'url\(["\']?(http[^"\']+)["\']?\)', style)
                        if bg_match:
                            src = bg_match.group(1)
                            if src not in result['images']:
                                # 检查图片尺寸
                                size_match = re.search(r'[_-](\d+)[_-](\d+)[_-]', src)
                                if size_match:
                                    w, h = int(size_match.group(1)), int(size_match.group(2))
                                    if w < min_image_size or h < min_image_size:
                                        logger.info(f"    ⚠️ 过滤低清图 (背景图): {w}x{h} < {min_image_size}")
                                        continue
                                result['images'].append(src)
                                if len(result['images']) >= 3: break
            except:
                pass

        if result['images']:
            logger.info(f"✅ 从详情页提取到 {len(result['images'])} 张图片")

        return result

    except Exception as e:
        logger.warning(f"获取详情页失败: {e}")
        return None


def extract_restaurant_info_from_element(elem, base_url: str) -> Optional[Dict]:
    """从 HTML 元素中提取餐厅基本信息"""
    try:
        restaurant = {
            'name': '',
            'rating': None,
            'review_count': None,
            'price_range': '',
            'cuisine_type': '',
            'description': '',
            'address': '',
            'url': '',
            'images': [],
            'tags': {'cuisine': [], 'price': [], 'meal': [], 'feature': [], 'special': []}
        }
        
        # 获取完整文本并转简体
        full_text = elem.get_text(separator=' ', strip=True)
        full_text_simplified = traditional_to_simplified(full_text)
        
        # 1. 提取链接和URL
        link_elem = None
        if elem.name == 'a' and elem.get('href'):
            link_elem = elem
        else:
            link_elem = elem.find('a', href=True)
            
        # 如果没找到，尝试向上查找（父元素）
        if not link_elem:
            parent = elem.parent
            for _ in range(3):
                if parent and parent.name == 'a' and parent.get('href'):
                    link_elem = parent
                    break
                if parent:
                    parent = parent.parent
                else:
                    break

        if link_elem:
            href = link_elem.get('href')
            if href:
                restaurant['url'] = urljoin(base_url, href)
            
            # 尝试从链接文本提取名称
            link_text = traditional_to_simplified(link_elem.get_text(strip=True))
            if (link_text and 2 < len(link_text) < 50 and 
                not re.match(r'^\d+\.?\d*\s*/\s*5', link_text) and 
                '条评价' not in link_text):
                restaurant['name'] = link_text

        # 2. 提取名称（如果链接文本无效）
        if not restaurant['name']:
            name_elem = elem.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
            if name_elem:
                name_text = traditional_to_simplified(name_elem.get_text(strip=True))
                if name_text and 2 < len(name_text) < 50:
                    restaurant['name'] = name_text

        # 3. 提取评分
        rating_match = re.search(r'(\d+\.?\d*)\s*/\s*5', full_text)
        if rating_match:
            try:
                restaurant['rating'] = float(rating_match.group(1))
            except: pass
            
        # 4. 提取评价数
        review_match = re.search(r'(\d+)\s*(?:条|條)\s*(?:评|評)', full_text)
        if review_match:
            try:
                restaurant['review_count'] = int(review_match.group(1))
            except: pass
            
        # 5. 提取价格（支持多种格式：$, $$, $$$, $$-$$$, $$$-$$$$ 等）
        # 优先匹配范围格式（如 $$-$$$），然后匹配单个格式（如 $$）
        price_match = re.search(r'(\$+\s*-\s*\$+)', full_text)
        if not price_match:
            # 如果没有范围格式，尝试匹配单个价格标识（如 $, $$, $$$）
            price_match = re.search(r'(\$+)(?=\s|$|[^$])', full_text)
        if price_match:
            restaurant['price_range'] = price_match.group(1).strip()
            restaurant['tags']['price'].append(restaurant['price_range'])

        # 6. 提取菜系
        cuisine_match = re.search(r'([^/\n]*菜[^/\n]*(?:\s*[／/]\s*[^/\n]*菜[^/\n]*)?)', full_text_simplified)
        if cuisine_match:
            cuisine_text = cuisine_match.group(1).strip()
            if 1 < len(cuisine_text) < 20:
                restaurant['cuisine_type'] = cuisine_text
                restaurant['tags']['cuisine'].append(cuisine_text)

        # 7. 提取图片
        img_candidates = []
        for img in elem.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if not src or not src.startswith('http'):
                continue
                
            # 过滤掉头像和图标
            # 1. 过滤 URL 中的关键词
            if any(kw in src.lower() for kw in ['headphoto', 'avatar', 'icon', 'logo', 'user', 'facebook', 'twitter', 'youtube', 'instagram', 'social', 'payment', 'wechat', 'scan', 'code', 'qrcode', 'tripcdn.com/packages']):
                continue
                
            # 2. 过滤尺寸过小的图片 (Trip.com URL 通常包含尺寸信息，如 _C_30_30_)
            # 匹配 _C_宽_高_ 或 _R_宽_高_ 模式
            size_match = re.search(r'_[CR]_(\d+)_(\d+)', src)
            if size_match:
                w, h = int(size_match.group(1)), int(size_match.group(2))
                if w < 100 or h < 100:  # 忽略小于 100x100 的图片
                    logger.info(f"    ⚠️ 过滤超小图: {w}x{h}")
                    continue
            
            # 3. 检查 HTML 属性（如果存在）
            width = img.get('width')
            height = img.get('height')
            if width and height:
                try:
                    if int(width) < 100 or int(height) < 100:
                        logger.info(f"    ⚠️ 过滤超小图: {width}x{height}")
                        continue
                except:
                    pass
            
            # 4. 检查 class (排除明确标记为头像的)
            classes = img.get('class', [])
            if any('avatar' in c or 'head' in c for c in classes):
                continue

            if src not in restaurant['images']:
                restaurant['images'].append(src)

        return restaurant if restaurant['name'] else None

    except Exception as e:
        logger.debug(f"提取信息失败: {e}")
        return None


def extract_restaurants_from_html(soup: BeautifulSoup, base_url: str) -> List[Dict]:
    """使用核心策略提取餐厅列表"""
    restaurants = []
    restaurant_elements = []
    
    # 核心策略：基于列表容器的反向查找
    logger.info("使用核心策略: 查找包含评价的列表容器...")
    try:
        review_texts = soup.find_all(string=re.compile(r'\d+\s*[条條]\s*[评評]价|\d+\s*[条條]\s*[评評]價'))
        logger.info(f"找到 {len(review_texts)} 个评价节点")
        
        if len(review_texts) > 1:
            common_parents = []
            for text_node in review_texts[:20]:
                parent = text_node.parent
                depth = 0
                while parent and parent.name not in ['body', 'html'] and depth < 8:
                    common_parents.append(parent)
                    parent = parent.parent
                    depth += 1
            
            if common_parents:
                parent_counts = Counter(common_parents)
                list_container = parent_counts.most_common(1)[0][0]
                
                # 遍历容器查找卡片 (加入 'a' 标签)
                for child in list_container.find_all(['div', 'article', 'li', 'a'], recursive=True):
                    child_text = child.get_text(separator=' ', strip=True)
                    if len(child_text) < 50 or '住宿' in child_text:
                        continue
                        
                    # 必须包含评价、名称
                    has_review = bool(re.search(r'\d+\s*[条條]\s*[评評]', child_text))
                    has_name = bool(re.search(r'[\u4e00-\u9fa5]{2,}', child_text))
                    
                    # 链接检查：元素本身是链接，或者包含链接，或者被链接包裹
                    has_link = False
                    if child.name == 'a' and child.get('href'):
                        has_link = True
                    elif child.find('a', href=True):
                        has_link = True
                    
                    # 如果还没有找到链接，尝试向上查找父级是否是链接
                    if not has_link:
                        parent = child.parent
                        for _ in range(3):
                            if parent and parent.name == 'a' and parent.get('href'):
                                has_link = True
                                break
                            if parent:
                                parent = parent.parent
                            else:
                                break
                    
                    if has_review and has_name and has_link:
                        # 避免重复添加子元素/父元素
                        is_duplicate = False
                        for existing in restaurant_elements:
                            if child in existing.descendants or existing in child.descendants:
                                is_duplicate = True
                                break
                        if not is_duplicate:
                            restaurant_elements.append(child)
                            if len(restaurant_elements) >= 20: break
                            
    except Exception as e:
        logger.error(f"提取失败: {e}")

    # 解析找到的元素
    logger.info(f"找到 {len(restaurant_elements)} 个餐厅卡片")
    for elem in restaurant_elements:
        info = extract_restaurant_info_from_element(elem, base_url)
        if info:
            restaurants.append(info)
            logger.info(f"提取: {info['name']}")
            
    return restaurants


def crawl_tripcom_restaurants(url: str, pages: int = 1, config: Optional['Config'] = None) -> Generator[Dict, None, None]:
    """主爬取函数"""
    if config is None:
        config = Config()
    
    session = requests.Session()
    # 使用随机 User-Agent
    session.headers.update({
        'User-Agent': random.choice(config.USER_AGENTS),
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    })
    
    try:
        logger.info(f"开始爬取: {url}")
        seen_names = set()
        pagination_template = None
        
        for page_num in range(1, pages + 1):
            # 构建 URL
            if page_num > 1:
                if pagination_template:
                    current_url = pagination_template.replace('{page}', str(page_num))
                else:
                    # 默认追加 page 参数
                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    params['page'] = [str(page_num)]
                    current_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(params, doseq=True)}"
            else:
                current_url = url
                
            logger.info(f"请求第 {page_num} 页: {current_url}")
            
            try:
                resp = session.get(current_url, timeout=30)
                if resp.status_code != 200:
                    logger.error(f"请求失败: {resp.status_code}")
                    continue
                    
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                # 第1页尝试分析分页链接
                if page_num == 1 and not pagination_template:
                    # 查找数字链接
                    links = soup.find_all('a', href=True, string=re.compile(r'^\s*\d+\s*$'))
                    for link in links:
                        if link.get_text(strip=True) == '2':
                            href = link['href']
                            full_href = urljoin(url, href)
                            # 简单的模板推断
                            if 'page=2' in full_href:
                                pagination_template = full_href.replace('page=2', 'page={page}')
                            elif '/2/' in full_href:
                                pagination_template = full_href.replace('/2/', '/{page}/')
                            elif full_href.endswith('/2'):
                                pagination_template = full_href[:-1] + '{page}'
                            
                            if pagination_template:
                                logger.info(f"✅ 发现分页模板: {pagination_template}")
                                break
                
                # 提取餐厅
                restaurants = extract_restaurants_from_html(soup, current_url)
                if not restaurants:
                    logger.warning("本页未找到餐厅")
                    break
                    
                for restaurant in restaurants:
                    if restaurant['name'] in seen_names:
                        continue
                    seen_names.add(restaurant['name'])
                    
                    # 如果没有地址，获取详情
                    if not restaurant['address'] and restaurant['url']:
                        detail_info = fetch_restaurant_detail(session, restaurant['url'])
                        if detail_info:
                            if detail_info.get('address'):
                                restaurant['address'] = detail_info['address']
                            
                            # 合并图片（优先使用详情页的高清图）
                            if detail_info.get('images'):
                                # 将详情页图片放在前面
                                restaurant['images'] = detail_info['images'] + restaurant['images']
                                # 去重并保持顺序
                                seen_imgs = set()
                                unique_imgs = []
                                for img in restaurant['images']:
                                    if img not in seen_imgs:
                                        unique_imgs.append(img)
                                        seen_imgs.add(img)
                                restaurant['images'] = unique_imgs[:3]  # 最多保留3张
                            
                    yield restaurant
                    
                # 页面间隔
                if page_num < pages:
                    time.sleep(random.uniform(2, 5))
                    
            except Exception as e:
                logger.error(f"页面处理失败: {e}", exc_info=True)
                
    finally:
        session.close()


def create_browser_page(headless: bool = False):
    """
    创建浏览器页面实例（可复用）
    """
    if not HAS_DRISSION:
        logger.warning("未安装 DrissionPage，无法进行浏览器搜索")
        return None
    
    try:
        co = ChromiumOptions()
        co.headless(headless)
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        # 设为中文环境
        co.set_argument('--lang=zh-CN')
        
        # 尝试自动查找浏览器路径 (兼容 Mac/Win)
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
        return page
    except Exception as e:
        logger.error(f"创建浏览器失败: {e}")
        return None


def search_restaurant_on_tripcom(keyword: str, city: str = "", page: Optional['ChromiumPage'] = None) -> Optional[str]:
    """
    模拟人操作搜索餐厅：在搜索框输入关键词并点击搜索按钮
    
    Args:
        keyword: 搜索关键词（餐厅名称）
        city: 城市（可选）
        page: 可选的浏览器页面实例，如果提供则复用，否则创建新的
    
    Returns:
        餐厅详情页 URL，如果未找到则返回 None
    """
    logger.info(f"DEBUG: search_restaurant_on_tripcom called with keyword='{keyword}', city='{city}'")
    if not HAS_DRISSION:
        logger.warning("未安装 DrissionPage，无法进行浏览器搜索")
        return None
    
    should_close_page = False
    
    # 检查 page 是否有效（如果提供了但已失效，不创建新的，让调用者处理）
    if page is None:
        # 如果没有提供 page，创建新的
        page = create_browser_page(headless=False)
        if not page:
            return None
        should_close_page = True
    else:
        # 如果提供了 page，检查是否仍然有效
        try:
            # 尝试获取当前URL来检查连接是否有效
            _ = page.url
        except Exception as e:
            logger.warning(f"提供的浏览器页面已失效: {e}，需要调用者重新创建")
            # 不在这里创建新浏览器，返回 None 让调用者处理
            return None
        
    try:
        # 优化：直接使用搜索URL，比查找搜索框更快
        from urllib.parse import quote
        encoded_keyword = quote(keyword)
        logger.info(f"DEBUG: encoded_keyword='{encoded_keyword}'")
        
        # 如果有城市信息，添加到搜索URL中
        city_param = ""
        if city:
            import re
            city_match = re.search(r'([^市]+市)', city)
            if city_match:
                city_name = city_match.group(1)
                city_param = f"&city={quote(city_name)}"
            elif len(city) < 20:
                city_param = f"&city={quote(city)}"
        
        # 直接构建搜索URL（使用实际的搜索URL格式）
        # 优先使用 global-search 搜索，然后通过标签筛选餐厅
        search_urls = [
            f"https://hk.trip.com/global-search/searchlist/search/?keyword={encoded_keyword}{city_param}&from=home",
            f"https://hk.trip.com/global-search/searchlist/search/?keyword={encoded_keyword}&from=home",
            f"https://hk.trip.com/travel-guide/restaurant/search?keyword={encoded_keyword}{city_param}",
            f"https://hk.trip.com/travel-guide/search?keyword={encoded_keyword}{city_param}"
        ]
        
        logger.info(f"DEBUG: search_urls length: {len(search_urls)}")
        for i, u in enumerate(search_urls):
            logger.info(f"DEBUG: url[{i}]: {u}")
        
        search_url = None
        for url in search_urls:
            try:
                logger.debug(f"正在访问搜索页面: {url}")
                page.get(url)
                page.wait.load_start(timeout=6)  # 减少超时时间
                time.sleep(random.uniform(0.5, 0.8))  # 减少等待时间
                
                current_url = page.url
                logger.info(f"    👉 尝试访问: {url} -> 实际到达: {current_url}")
                # 检查是否成功跳转到搜索页面或详情页
                # 必须确保 URL 发生了变化，或者包含新的关键词（防止停留在上一次的搜索页面）
                # 注意：浏览器可能会重新编码 URL，所以比较 encoded_keyword 可能不完全匹配，
                # 但至少应该包含 keyword 的某些部分或者是新的页面
                if ('/search' in current_url or '/global-search' in current_url or '/restaurant/' in current_url or '/food/' in current_url):

                    from urllib.parse import unquote
                    
                    # Debug log for stale page check
                    logger.debug(f"    🔎 检查跳转: keyword='{keyword}' in url? {'keyword=' in current_url}")
                    
                    if 'keyword=' in current_url and encoded_keyword not in current_url and keyword not in unquote(current_url):
                         logger.warning(f"页面似乎未跳转，当前 URL 关键词不匹配: {current_url}")
                         # 视为失败，继续尝试下一个 URL 或重试
                         continue

                    search_url = current_url
                    logger.debug(f"✅ 成功访问搜索页面: {current_url}")
                    break
            except Exception as e:
                logger.debug(f"访问 {url} 失败: {e}")
                continue
        
        if not search_url:
            logger.warning("直接URL访问失败，尝试从首页搜索")
            # 备用方案：从首页搜索
            try:
                page.get("https://hk.trip.com/travel-guide/")
                page.wait.load_start(timeout=10)
                time.sleep(random.uniform(1, 1.5))  # 减少等待时间
                
                # 快速查找搜索框（只尝试最常用的选择器）
                search_input = None
                quick_selectors = [
                    'input[type="search"]',
                    'input[placeholder*="搜索"]',
                    'input[placeholder*="Search"]',
                    'input[class*="search"]'
                ]
                
                for selector in quick_selectors:
                    try:
                        inp = page.ele(f'css:{selector}', timeout=2)  # 使用超时，快速失败
                        if inp and inp.states.is_displayed:
                            search_input = inp
                            logger.info(f"✅ 找到搜索框")
                            break
                    except:
                        continue
                
                if search_input:
                    # 快速输入（减少延迟）
                    try:
                        search_input.set.value(keyword)  # 直接设置值，比逐字符输入快
                        time.sleep(random.uniform(0.3, 0.5))
                        
                        # 尝试按回车或查找搜索按钮
                        try:
                            search_input.input('\n')
                            time.sleep(random.uniform(1, 2))
                        except:
                            # 查找搜索按钮
                            try:
                                btn = page.ele('css:button[type="submit"], css:button[class*="search"]', timeout=1)
                                if btn:
                                    btn.click()
                                    time.sleep(random.uniform(1, 2))
                            except:
                                pass
                    except Exception as e:
                        logger.warning(f"输入失败: {e}")
            except Exception as e:
                logger.warning(f"从首页搜索失败: {e}")
        
        # 5. 等待搜索结果加载
        current_url = page.url
        logger.info(f"当前页面 URL: {current_url}")
        
        # 检查是否直接进入详情页
        if '/restaurant/' in current_url or '/food/' in current_url:
            if 'review' not in current_url and 'search' not in current_url:
                logger.info(f"✅ 直接进入详情页: {current_url}")
                return current_url
        
        # 6. 快速滚动一次，让页面加载内容（减少滚动次数）
        try:
            page.run_js("window.scrollBy(0, 500)")
            time.sleep(random.uniform(0.2, 0.4))  # 进一步减少等待时间
        except:
            pass
        
        # 7. 快速尝试点击 "美食" / "Restaurants" 标签（如果存在）- 确保只搜索餐厅类型
        try:
            # 优先查找餐厅/美食相关的标签
            tab_keywords = ['美食', '餐厅', 'Restaurants', 'Food', 'Dining', 'Restaurant']
            for tab_kw in tab_keywords:
                try:
                    # 使用XPath查找包含关键词的标签
                    tab = page.ele(f'xpath://*[contains(text(), "{tab_kw}")]', timeout=0.5)
                    if tab and tab.states.is_displayed:
                        logger.info(f"  ✅ 找到并点击 '{tab_kw}' 标签")
                        tab.click()
                        time.sleep(random.uniform(0.3, 0.5))  # 减少等待时间
                        break
                except:
                    continue
        except Exception as e:
            logger.debug(f"点击标签时出错: {e}")
            pass
            
        # 8. 查找搜索结果中的餐厅链接并点击
        logger.debug(f"正在查找搜索结果中的餐厅链接...")
        
        # 优先查找搜索结果列表中的链接（针对搜索页面结构）
        restaurant_links = []
        try:
            # 策略1: 查找搜索结果容器中的链接（最准确）
            result_container_selectors = [
                'css:[class*="search-result"] a',
                'css:[class*="result-item"] a',
                'css:[class*="result-list"] a',
                'css:[class*="search-list"] a',
                'css:[class*="card"] a',
                'css:[class*="item"] a'
            ]
            
            for selector in result_container_selectors:
                try:
                    links = page.eles(selector)
                    if links:
                        logger.debug(f"使用选择器 {selector} 找到 {len(links)} 个链接")
                        restaurant_links.extend(links)
                        break
                except:
                    continue
            
            # 策略2: 如果没找到，查找包含餐厅URL的链接
            if not restaurant_links:
                restaurant_links = page.eles('css:a[href*="/restaurant/"], css:a[href*="/food/"]')
                logger.debug(f"查找餐厅URL链接，找到 {len(restaurant_links)} 个")
            
            # 策略3: 如果还是没找到，查找所有可见的链接（排除导航链接）
            if not restaurant_links:
                all_links = page.eles('tag:a')
                # 过滤掉导航、页脚等链接
                for link in all_links:
                    try:
                        href = link.attr('href') or ''
                        text = link.text.strip()
                        
                        # 先检查是否是餐厅URL（优先保留）
                        is_restaurant_path = '/restaurant/' in href.lower() or '/food/' in href.lower() or '/dining/' in href.lower()
                        
                        # 排除明显的导航链接和非餐厅链接
                        # 注意：不排除 /travel-guide/restaurant/ 路径
                        excluded_paths = ['javascript:', '#', '/hotel', '/flight', '/train', '/packages', 
                                         '/things-to-do', '/attractions', '/activities',
                                         '/car', '/cruise', '/vacation', '/tours', '/deals', '/giftcard']
                        
                        # 排除 /travel-guide 但不包含 /restaurant/ 的路径
                        if '/travel-guide' in href.lower() and '/restaurant/' not in href.lower():
                            continue
                        
                        if not is_restaurant_path and any(x in href.lower() for x in excluded_paths):
                            continue
                        
                        # 排除太短的文本（可能是图标）
                        if len(text) < 3:
                            continue
                        
                        # 排除导航文本和非餐厅相关文本
                        excluded_texts = ['主页', '首页', 'Home', '搜索', 'Search', '登录', 'Login', 
                                         '机票', '酒店', '機票', '酒店', 'Flight', 'Hotel', 'Packages',
                                         '套餐', '旅游', '旅遊', 'Travel', 'Tour']
                        if text in excluded_texts or any(excluded in text for excluded in excluded_texts):
                            continue
                        
                        restaurant_links.append(link)
                        if len(restaurant_links) >= 20:  # 限制数量
                            break
                    except:
                        continue
                logger.debug(f"查找所有链接，过滤后找到 {len(restaurant_links)} 个")
        except Exception as e:
            logger.debug(f"查找链接时出错: {e}")
            restaurant_links = []
        
        logger.debug(f"找到 {len(restaurant_links)} 个可能的餐厅链接")
        
        # 收集所有有效的餐厅链接
        valid_restaurant_links = []
        
        for link in restaurant_links:
            try:
                href = link.attr('href')
                if not href: 
                    continue
                
                # 快速排除非餐厅相关的URL（在详细检查之前）
                href_lower = href.lower()
                if any(excluded in href_lower for excluded in ['/giftcard', '/gift-card', '/insurance', '/insurance', '/help', '/support', '/contact', '/about', '/terms', '/privacy']):
                    continue  # 跳过礼品卡、保险、帮助等非餐厅页面
                
                # 必须是餐厅详情页
                is_restaurant_url = False
                
                # 检查是否是餐厅相关的URL
                if '/restaurant/' in href or '-restaurant/' in href or '/food/' in href or '/dining/' in href:
                    # 排除评论页、搜索页、榜单页等
                    excluded_in_restaurant_url = ['review', 'search', 'list', 'toplist', 'top-list', 'best', 'ranking']
                    if not any(x in href.lower() for x in excluded_in_restaurant_url):
                        # 检查是否是详情页格式
                        if 'restaurantdetail' in href or 'restaurant-detail' in href or href.endswith('.html'):
                            is_restaurant_url = True
                            logger.debug(f"  ✅ 识别为餐厅URL (详情页格式): {href}")
                        elif ('/restaurant/' in href or '-restaurant/' in href) and not any(x in href for x in ['/search', '/list', '/category', '/toplist', '/top-list']):
                            is_restaurant_url = True
                            logger.debug(f"  ✅ 识别为餐厅URL (restaurant路径): {href}")
                        # 也接受包含餐厅ID的URL（如 /restaurant/123456）
                        elif '/restaurant/' in href and re.search(r'/restaurant/\d+', href):
                            is_restaurant_url = True
                            logger.debug(f"  ✅ 识别为餐厅URL (包含ID): {href}")
                    else:
                        logger.debug(f"  ❌ 被排除 (包含排除关键词): {href}")
                
                # 如果链接文本包含餐厅相关关键词，也可能是餐厅链接
                if not is_restaurant_url:
                    text = link.text.strip()
                    if text and len(text) > 3:
                        # 先排除明显不是餐厅的文本
                        excluded_keywords = ['机票', '酒店', '機票', '酒店', 'Flight', 'Hotel', 'Packages',
                                            '套餐', '旅游', '旅遊', 'Travel', 'Tour', 'Attraction', 'Activity',
                                            '榜单', '排行榜', 'Top', 'Best', 'Must', '必試', '必试', '推荐',
                                            'Toplist', 'List', '50大', '100大', '十大']
                        if any(excluded in text for excluded in excluded_keywords):
                            continue  # 跳过这个链接
                        
                        # 检查文本是否包含餐厅相关关键词
                        restaurant_keywords = ['餐厅', '餐廳', 'Restaurant', 'Food', 'Dining', '菜', '店', '馆', '館', '食', '餐']
                        if any(kw in text for kw in restaurant_keywords):
                            # 检查URL是否不是导航链接和非餐厅链接
                            # 注意：不排除 /travel-guide/restaurant/ 路径，这是有效的餐厅详情页路径
                            excluded_urls = ['javascript:', '#', '/hotel', '/flight', '/train', '/search', 
                                            '/packages', '/things-to-do', '/attractions', 
                                            '/activities', '/car', '/cruise', '/vacation', '/tours', '/deals',
                                            '/toplist', '/top-list', '/best', '/ranking', '/list', '/giftcard']
                            # 排除 /travel-guide 但不包含 /restaurant/ 的路径
                            if '/travel-guide' in href.lower() and '/restaurant/' not in href.lower() and '-restaurant/' not in href.lower():
                                continue  # 跳过非餐厅的travel-guide链接
                            if not any(x in href.lower() for x in excluded_urls):
                                is_restaurant_url = True
                
                if is_restaurant_url:
                    text = link.text.strip()
                    # 处理相对路径
                    if href.startswith('http'):
                        full_url = href
                    else:
                        full_url = urljoin(page.url, href)
                    
                    # 最终验证：确保URL不是非餐厅链接
                    # 注意：不排除 /travel-guide/restaurant/ 路径，这是有效的餐厅详情页路径
                    excluded_url_patterns = ['/packages', '/hotel', '/flight', '/train',
                                            '/things-to-do', '/attractions', '/activities', '/car', '/cruise',
                                            '/vacation', '/tours', '/deals', '/toplist', '/top-list', '/best',
                                            '/ranking', '/list', '/giftcard']
                    # 排除 /travel-guide 但不包含 /restaurant/ 的路径
                    if '/travel-guide' in full_url.lower() and '/restaurant/' not in full_url.lower() and '-restaurant/' not in full_url.lower():
                        logger.debug(f"  ❌ 被排除 (travel-guide但不包含restaurant): {full_url}")
                        continue  # 跳过非餐厅的travel-guide链接
                    if any(pattern in full_url.lower() for pattern in excluded_url_patterns):
                        logger.debug(f"  ❌ 被排除 (包含排除模式): {full_url}")
                        continue  # 跳过这个链接
                    logger.debug(f"  ✅ 通过最终验证: {full_url}")
                    
                    # 如果URL不包含餐厅相关路径，但文本匹配，需要更严格的验证
                    # 注意：/travel-guide/restaurant/ 路径已经在上面的检查中通过了，这里不需要再检查
                    if '/restaurant/' not in full_url.lower() and '-restaurant/' not in full_url.lower() and '/food/' not in full_url.lower() and '/dining/' not in full_url.lower():
                        # 对于非餐厅URL路径的链接，需要文本高度匹配才接受
                        if keyword not in text and text not in keyword:
                            # 如果文本不包含关键词，降低优先级或跳过
                            if not any(kw in text for kw in ['餐厅', '餐廳', 'Restaurant', 'Food', 'Dining', '菜', '店', '馆', '館']):
                                logger.debug(f"  ❌ 被排除 (文本不匹配且URL不是餐厅路径): {full_url}, text: {text}")
                                continue  # 跳过不相关的链接
                    
                    # 计算匹配度（更严格的匹配逻辑）
                    match_score = 0
                    keyword_lower = keyword.lower()
                    text_lower = text.lower()
                    
                    # 完全匹配（关键词完整出现在文本中）
                    if keyword_lower in text_lower:
                        match_score = 100  # 完全匹配
                    # 文本是关键词的一部分（文本较短，可能是餐厅名称）
                    elif text_lower in keyword_lower and len(text_lower) >= 2:
                        match_score = 90
                    # 关键词的前2个字符在文本中（部分匹配）
                    elif len(keyword) > 2 and keyword_lower[:2] in text_lower:
                        # 进一步检查：确保不是误匹配（如"海"匹配到"拉斯维加斯"）
                        # 如果文本长度远大于关键词，且关键词只是部分字符匹配，降低分数
                        if len(text_lower) > len(keyword_lower) * 2:
                            match_score = 30  # 降低分数，可能是误匹配
                        else:
                            match_score = 50
                    # 关键词的每个字符都在文本中（但顺序可能不同）
                    elif len(keyword) > 2 and all(char in text_lower for char in keyword_lower if char.isalnum()):
                        # 如果文本长度远大于关键词，可能是误匹配
                        if len(text_lower) > len(keyword_lower) * 2:
                            match_score = 10  # 很低的分数
                        else:
                            match_score = 20  # 部分匹配
                    else:
                        # 如果文本不匹配，但URL是餐厅相关的，给一个基础分数
                        if '/restaurant/' in full_url.lower() or '-restaurant/' in full_url.lower() or '/food/' in full_url.lower() or '/dining/' in full_url.lower():
                            match_score = 10  # 基础分数
                        else:
                            continue  # 完全不匹配且不是餐厅URL，跳过
                    
                    valid_restaurant_links.append({
                        'link': link,
                        'url': full_url,
                        'text': text,
                        'match_score': match_score
                    })
            except:
                continue
        
        # 按匹配度排序
        valid_restaurant_links.sort(key=lambda x: x['match_score'], reverse=True)
        
        # 输出所有有效链接
        if valid_restaurant_links:
            logger.info(f"找到 {len(valid_restaurant_links)} 个有效餐厅链接:")
            for i, link_info in enumerate(valid_restaurant_links):
                logger.info(f"  {i+1}. 匹配度: {link_info['match_score']}, 文本: {link_info['text'][:50]}, URL: {link_info['url']}")
        
        # 如果有有效的餐厅链接，点击第一个（优先匹配度高的）
        if valid_restaurant_links:
            best_match = valid_restaurant_links[0]
            link = best_match['link']
            full_url = best_match['url']
            text = best_match['text']
            match_score = best_match['match_score']
            
            if match_score >= 50:
                logger.info(f"✅ 找到匹配餐厅 (匹配度: {match_score}): {text} -> {full_url}")
            else:
                logger.info(f"✅ 未找到精确匹配，点击第一个餐厅链接 (匹配度: {match_score}): {text} -> {full_url}")
            
            # 点击链接进入详情页
            try:
                link.click()
                page.wait.load_start(timeout=6)
                time.sleep(random.uniform(0.3, 0.5))  # 减少等待时间
                logger.info(f"✅ 成功进入详情页")
                return full_url
            except Exception as e:
                logger.warning(f"点击链接失败: {e}，直接返回URL")
                return full_url
        
        # 如果还是没有找到餐厅链接，直接返回None，不尝试点击其他无关链接
        logger.warning("未找到匹配的餐厅链接，跳过...")
        return None
            
    except Exception as e:
        import traceback
        logger.warning(f"网页搜索失败: {e}")
        logger.debug(f"错误详情: {traceback.format_exc()}")
        return None
    finally:
        # 只有在创建了新页面时才关闭浏览器
        if should_close_page and page:
            try:
                logger.info("正在关闭浏览器...")
                page.quit()
            except Exception as e:
                logger.debug(f"关闭浏览器时出错（可忽略）: {e}")
                pass


def search_and_crawl_restaurant_detail(keyword: str, city: str = "", page: Optional['ChromiumPage'] = None, extract_address: bool = True, extract_comments: bool = False, min_image_size: int = 220, max_images: int = 20) -> Optional[Dict]:
    """
    完整的模拟人操作流程：搜索餐厅 → 点击进入详情页 → 爬取图片和评论
    
    Args:
        keyword: 搜索关键词（餐厅名称）
        city: 城市（可选）
        page: 可选的浏览器页面实例，如果提供则复用，否则创建新的
        extract_address: 是否提取地址（默认True）
        extract_comments: 是否提取评论（默认False，跳过评论提取以加快速度）
        min_image_size: 最小图片尺寸（宽或高），默认220
        max_images: 最大提取图片数量，默认20
    
    Returns:
        包含餐厅详细信息的字典，包括：
        - url: 详情页URL
        - address: 地址（如果extract_address=True）
        - images: 图片列表
        - comments: 评论列表（每个评论包含 username, content, rating，如果extract_comments=True）
    """
    if not HAS_DRISSION:
        logger.warning("未安装 DrissionPage，无法进行浏览器操作")
        return None
    
    should_close_page = False
    
    # 检查或创建浏览器页面
    if page is None:
        page = create_browser_page(headless=False)
        if not page:
            return None
        should_close_page = True
    else:
        try:
            _ = page.url
        except Exception as e:
            logger.warning(f"提供的浏览器页面已失效: {e}")
            return None
    
    try:
        # 1. 搜索餐厅
        logger.debug(f"开始搜索餐厅: {keyword}")
        detail_url = search_restaurant_on_tripcom(keyword, city, page)
        
        if not detail_url:
            logger.warning(f"未找到餐厅: {keyword}")
            return None
        
        logger.info(f"✅ 找到餐厅详情页: {detail_url}")
        
        # 2. 访问详情页并爬取信息
        logger.info(f"开始爬取详情页信息...")
        detail_info = fetch_restaurant_detail_browser(page, detail_url, extract_address=extract_address, extract_comments=extract_comments, min_image_size=min_image_size, max_images=max_images)
        
        if not detail_info:
            logger.warning(f"爬取详情页失败: {detail_url}")
            return None
        
        # 3. 整合结果
        result = {
            'url': detail_url,
            'address': detail_info.get('address', ''),
            'images': detail_info.get('images', []),
            'comments': detail_info.get('comments', []),
            'price_range': detail_info.get('price_range', '')
        }
        
        # 简化日志输出
        if result['price_range']:
            logger.debug(f"✅ 爬取完成: 价格标识={result['price_range']}")
        elif extract_address or extract_comments:
            logger.debug(f"✅ 爬取完成")
        
        return result
        
    except Exception as e:
        import traceback
        logger.error(f"搜索和爬取失败: {e}")
        logger.debug(f"错误详情: {traceback.format_exc()}")
        return None
    finally:
        # 只有在创建了新页面时才关闭浏览器
        if should_close_page and page:
            try:
                logger.info("正在关闭浏览器...")
                page.quit()
            except Exception as e:
                logger.debug(f"关闭浏览器时出错（可忽略）: {e}")
                pass
