#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trip.com 餐厅爬虫脚本
爬取 Trip.com 上的餐厅信息
"""
import os
import sys
import logging
import argparse
import time
import random
import json
import re
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.config import Config
from base.browser_cleanup import safe_close_browser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def crawl_trip_com_restaurants(
    url: str,
    pages: int = 1,
    headless: bool = False,
    max_restaurants: Optional[int] = None
) -> List[Dict]:
    """
    爬取 Trip.com 餐厅信息
    
    Args:
        url: Trip.com 餐厅列表页面URL（如：https://hk.trip.com/restaurant/shanghai-2/）
        pages: 爬取页数
        headless: 是否使用无头模式
        max_restaurants: 最大爬取餐厅数量（None表示不限制）
        
    Returns:
        餐厅信息列表，每个餐厅包含 name, address, rating, price_range, cuisine, images, url 等
    """
    try:
        try:
            from DrissionPage._pages.chromium_page import ChromiumPage
            from DrissionPage import ChromiumOptions
        except ImportError:
            try:
                from DrissionPage import ChromiumPage, ChromiumOptions
            except ImportError:
                logger.error("无法导入ChromiumPage，请确保已安装DrissionPage: pip install DrissionPage")
                return []
        
        config = Config()
        
        logger.info(f"开始爬取 Trip.com: URL={url}, 页数={pages}")
        
        # 初始化浏览器
        logger.info("正在启动浏览器...")
        
        options = ChromiumOptions()
        import random as random_module
        random_port = random_module.randint(9223, 9999)
        options.set_address(f'127.0.0.1:{random_port}')
        options.set_argument(f'--remote-debugging-port={random_port}')
        logger.info(f"使用调试端口: {random_port}")
        
        options.set_argument(f'--window-size={config.WINDOW_WIDTH},{config.WINDOW_HEIGHT}')
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--disable-dev-shm-usage')
        
        if headless:
            options.headless(True)
        
        # 尝试自动检测浏览器路径（macOS）
        try:
            import subprocess
            chrome_paths = [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '/Applications/Chromium.app/Contents/MacOS/Chromium',
                '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
            ]
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    options.set_browser_path(chrome_path)
                    logger.info(f"检测到浏览器路径: {chrome_path}")
                    break
        except Exception as e:
            logger.debug(f"自动检测浏览器路径失败: {e}，使用默认路径")
        
        try:
            page = ChromiumPage(options)
            logger.info("✅ 浏览器启动成功")
        except Exception as e:
            logger.warning(f"使用配置启动失败: {e}，尝试使用默认配置...")
            try:
                page = ChromiumPage()
                logger.info("✅ 使用默认配置启动浏览器成功")
            except Exception as e2:
                logger.error(f"浏览器启动失败: {e2}")
                raise
        
        # 设置浏览器参数
        user_agent = random.choice(config.USER_AGENTS)
        headers = config.DEFAULT_HEADERS.copy()
        headers['User-Agent'] = user_agent
        
        try:
            page.set.headers(headers)
            page.set.window.size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
            logger.info("✅ 浏览器参数已配置")
        except Exception as e:
            logger.warning(f"设置浏览器参数失败: {e}，继续使用默认配置")
        
        restaurants = []
        
        try:
            # 访问餐厅列表页面
            logger.info(f"正在访问: {url}")
            page.get(url)
            page.wait.doc_loaded()
            time.sleep(random.uniform(3, 5))
            
            # 模拟滚动加载更多内容
            logger.info("滚动页面加载内容...")
            for _ in range(3):
                page.run_js("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(2, 4))
            
            # 提取餐厅列表
            restaurant_elements = []
            try:
                # 尝试多种选择器来找到餐厅卡片
                selectors = [
                    'div[class*="restaurant"]',
                    'div[class*="Restaurant"]',
                    'a[href*="/restaurant/"]',
                    'div[data-testid*="restaurant"]',
                    '.restaurant-item',
                    '.restaurant-card'
                ]
                
                for selector in selectors:
                    elements = page.eles(selector)
                    if elements:
                        logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                        restaurant_elements = elements
                        break
                
                # 如果没找到，尝试通过链接查找
                if not restaurant_elements:
                    links = page.eles('tag:a')
                    restaurant_links = [link for link in links if '/restaurant/' in (link.attr('href') or '')]
                    if restaurant_links:
                        logger.info(f"通过链接找到 {len(restaurant_links)} 个餐厅链接")
                        restaurant_elements = restaurant_links
                
            except Exception as e:
                logger.warning(f"查找餐厅元素失败: {e}")
            
            if not restaurant_elements:
                logger.warning("未找到餐厅元素，尝试从页面HTML中提取")
                # 尝试从页面HTML中提取
                html = page.html
                # 查找包含餐厅信息的JSON数据
                json_pattern = r'window\.__INITIAL_STATE__\s*=\s*({.+?});'
                match = re.search(json_pattern, html)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        logger.info("从页面JSON中提取数据")
                        # 这里可以根据实际JSON结构提取餐厅信息
                    except:
                        pass
            
            logger.info(f"找到 {len(restaurant_elements)} 个餐厅元素")
            
            # 限制处理数量
            if max_restaurants:
                restaurant_elements = restaurant_elements[:max_restaurants]
            
            # 提取每个餐厅的信息
            for idx, element in enumerate(restaurant_elements, 1):
                if max_restaurants and len(restaurants) >= max_restaurants:
                    break
                
                try:
                    logger.info(f"\n处理餐厅 {idx}/{len(restaurant_elements)}")
                    
                    restaurant_info = {}
                    
                    # 提取餐厅名称
                    name = None
                    try:
                        # 尝试多种方式获取名称
                        name_elem = element.ele('tag:h2', timeout=1) or element.ele('tag:h3', timeout=1) or element.ele('tag:h1', timeout=1)
                        if name_elem:
                            name = name_elem.text.strip()
                        else:
                            # 尝试从链接文本获取
                            if element.tag == 'a':
                                name = element.text.strip()
                            else:
                                # 尝试从子元素获取
                                text_elem = element.ele('css:.title', timeout=1) or element.ele('css:.name', timeout=1)
                                if text_elem:
                                    name = text_elem.text.strip()
                    except:
                        pass
                    
                    if not name:
                        # 尝试从属性获取
                        name = element.attr('title') or element.attr('data-title') or element.attr('aria-label')
                    
                    if not name or len(name) < 2:
                        logger.warning(f"  跳过：无法获取餐厅名称")
                        continue
                    
                    restaurant_info['name'] = name
                    logger.info(f"  餐厅名称: {name}")
                    
                    # 提取餐厅链接
                    restaurant_url = None
                    try:
                        if element.tag == 'a':
                            restaurant_url = element.attr('href')
                        else:
                            link_elem = element.ele('tag:a', timeout=1)
                            if link_elem:
                                restaurant_url = link_elem.attr('href')
                    except:
                        pass
                    
                    if restaurant_url:
                        if not restaurant_url.startswith('http'):
                            restaurant_url = 'https://hk.trip.com' + restaurant_url
                        restaurant_info['url'] = restaurant_url
                        logger.info(f"  餐厅链接: {restaurant_url}")
                    
                    # 提取评分
                    try:
                        rating_elem = element.ele('css:.rating', timeout=1) or element.ele('css:[class*="rating"]', timeout=1)
                        if rating_elem:
                            rating_text = rating_elem.text.strip()
                            # 提取数字评分
                            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                            if rating_match:
                                restaurant_info['rating'] = float(rating_match.group(1))
                                logger.info(f"  评分: {restaurant_info['rating']}")
                    except:
                        pass
                    
                    # 提取评价数量
                    try:
                        review_elem = element.ele('css:.review', timeout=1) or element.ele('css:[class*="review"]', timeout=1)
                        if review_elem:
                            review_text = review_elem.text.strip()
                            review_match = re.search(r'(\d+)', review_text)
                            if review_match:
                                restaurant_info['review_count'] = int(review_match.group(1))
                                logger.info(f"  评价数: {restaurant_info['review_count']}")
                    except:
                        pass
                    
                    # 提取价格范围
                    try:
                        price_elem = element.ele('css:.price', timeout=1) or element.ele('css:[class*="price"]', timeout=1)
                        if price_elem:
                            price_text = price_elem.text.strip()
                            restaurant_info['price_range'] = price_text
                            logger.info(f"  价格: {price_text}")
                    except:
                        pass
                    
                    # 提取菜系
                    try:
                        cuisine_elem = element.ele('css:.cuisine', timeout=1) or element.ele('css:[class*="cuisine"]', timeout=1)
                        if cuisine_elem:
                            cuisine_text = cuisine_elem.text.strip()
                            restaurant_info['cuisine'] = cuisine_text
                            logger.info(f"  菜系: {cuisine_text}")
                    except:
                        pass
                    
                    # 提取图片
                    images = []
                    try:
                        img_elem = element.ele('tag:img', timeout=1)
                        if img_elem:
                            img_url = img_elem.attr('src') or img_elem.attr('data-src')
                            if img_url:
                                if not img_url.startswith('http'):
                                    img_url = 'https://hk.trip.com' + img_url
                                images.append(img_url)
                                restaurant_info['images'] = images
                                logger.info(f"  图片: {len(images)} 张")
                    except:
                        pass
                    
                    # 如果有链接，访问详情页获取更多信息
                    if restaurant_url:
                        try:
                            logger.info(f"  访问详情页获取更多信息...")
                            page.get(restaurant_url)
                            page.wait.doc_loaded()
                            time.sleep(random.uniform(2, 4))
                            
                            # 提取地址
                            try:
                                address_selectors = [
                                    'css:.address',
                                    'css:[class*="address"]',
                                    'css:[data-testid*="address"]',
                                    'xpath://span[contains(text(), "地址")]/following-sibling::span',
                                    'xpath://div[contains(text(), "地址")]/following-sibling::div'
                                ]
                                for selector in address_selectors:
                                    try:
                                        addr_elem = page.ele(selector, timeout=2)
                                        if addr_elem:
                                            address = addr_elem.text.strip()
                                            if address and len(address) > 5:
                                                restaurant_info['address'] = address
                                                logger.info(f"  地址: {address[:50]}...")
                                                break
                                    except:
                                        continue
                            except:
                                pass
                            
                            # 提取更多图片
                            try:
                                detail_images = []
                                img_elements = page.eles('tag:img')
                                for img in img_elements[:5]:  # 最多5张图片
                                    img_url = img.attr('src') or img.attr('data-src')
                                    if img_url and 'restaurant' in img_url.lower() and img_url not in images:
                                        if not img_url.startswith('http'):
                                            img_url = 'https://hk.trip.com' + img_url
                                        detail_images.append(img_url)
                                
                                if detail_images:
                                    restaurant_info['images'] = (restaurant_info.get('images', []) + detail_images)[:5]
                                    logger.info(f"  详情页图片: {len(detail_images)} 张")
                            except:
                                pass
                            
                            # 提取描述
                            try:
                                desc_selectors = [
                                    'css:.description',
                                    'css:[class*="description"]',
                                    'css:.intro',
                                    'css:[class*="intro"]'
                                ]
                                for selector in desc_selectors:
                                    try:
                                        desc_elem = page.ele(selector, timeout=2)
                                        if desc_elem:
                                            description = desc_elem.text.strip()
                                            if description and len(description) > 10:
                                                restaurant_info['description'] = description
                                                logger.info(f"  描述: {description[:50]}...")
                                                break
                                    except:
                                        continue
                            except:
                                pass
                            
                            # 返回列表页
                            page.get(url)
                            page.wait.doc_loaded()
                            time.sleep(random.uniform(2, 3))
                            
                        except Exception as e:
                            logger.warning(f"  访问详情页失败: {e}")
                            # 返回列表页
                            try:
                                page.get(url)
                                page.wait.doc_loaded()
                                time.sleep(random.uniform(2, 3))
                            except:
                                pass
                    
                    # 确保有基本信息
                    if restaurant_info.get('name'):
                        restaurants.append(restaurant_info)
                        logger.info(f"  ✅ 成功提取餐厅: {name}")
                    else:
                        logger.warning(f"  ⚠️  餐厅信息不完整，跳过")
                    
                    # 延迟
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    logger.error(f"  处理餐厅失败: {e}")
                    continue
            
            logger.info(f"\n成功爬取 {len(restaurants)} 个餐厅")
            return restaurants
            
        finally:
            # 关闭浏览器
            try:
                logger.info("正在关闭浏览器...")
                safe_close_browser(page, random_port if 'random_port' in locals() else None)
                logger.info("✅ 浏览器已关闭")
            except Exception as e:
                logger.warning(f"关闭浏览器时出错: {e}")
                
    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.error("请确保已安装 DrissionPage: pip install DrissionPage")
        return []
    except Exception as e:
        logger.error(f"爬取 Trip.com 失败: {e}", exc_info=True)
        return []


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='Trip.com 餐厅爬虫',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 爬取上海餐厅列表
  python3 crawl_trip_com.py --url "https://hk.trip.com/restaurant/shanghai-2/" --pages 1
  
  # 无头模式，限制数量
  python3 crawl_trip_com.py --url "https://hk.trip.com/restaurant/shanghai-2/" --headless --max 10
  
  # 保存到JSON文件
  python3 crawl_trip_com.py --url "https://hk.trip.com/restaurant/shanghai-2/" --output restaurants.json
        """
    )
    
    parser.add_argument('--url', type=str, required=True, help='Trip.com 餐厅列表页面URL')
    parser.add_argument('--pages', type=int, default=1, help='爬取页数（默认：1）')
    parser.add_argument('--headless', action='store_true', help='无头模式（不显示浏览器窗口）')
    parser.add_argument('--max', type=int, help='最大爬取餐厅数量')
    parser.add_argument('--output', type=str, help='输出JSON文件路径')
    
    args = parser.parse_args()
    
    try:
        restaurants = crawl_trip_com_restaurants(
            url=args.url,
            pages=args.pages,
            headless=args.headless,
            max_restaurants=args.max
        )
        
        if restaurants:
            logger.info(f"\n成功爬取 {len(restaurants)} 个餐厅")
            
            # 保存到文件
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(restaurants, f, ensure_ascii=False, indent=2)
                logger.info(f"数据已保存到: {args.output}")
            else:
                # 打印前几个餐厅信息
                logger.info("\n前5个餐厅信息:")
                for i, restaurant in enumerate(restaurants[:5], 1):
                    logger.info(f"\n{i}. {restaurant.get('name', '未知')}")
                    logger.info(f"   地址: {restaurant.get('address', '未知')}")
                    logger.info(f"   评分: {restaurant.get('rating', '未知')}")
                    logger.info(f"   链接: {restaurant.get('url', '未知')}")
        else:
            logger.warning("未爬取到任何餐厅")
            
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

