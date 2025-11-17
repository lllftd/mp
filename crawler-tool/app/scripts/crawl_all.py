#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合爬虫脚本 - 同时支持爬取活动和餐厅
使用AI自动判断笔记类型，分别处理并上传到对应的数据库表
"""
import os
import sys
import logging
import argparse
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.ai_service import get_ai_paraphraser
from base.config import Config
from app.services.address_service import AddressService
from app.services.tweet_service import prepare_tweet_data, insert_tweet
from app.utils.process_content import process_note
from base.database import db
from base.location_utils import extract_district_from_address, find_county_code
from base.utils import get_random_username
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def crawl_xiaohongshu_generator(keyword: str, pages: int = 5, headless: bool = False):
    """
    爬取小红书笔记（生成器模式，逐条返回）
    
    Args:
        keyword: 搜索关键词
        pages: 爬取页数
        headless: 是否使用无头模式
        
    Yields:
        笔记字典，包含 title, description, images, url
    """
    try:
        import time
        import random
        from urllib.parse import quote
        
        try:
            from DrissionPage._pages.chromium_page import ChromiumPage
            from DrissionPage import ChromiumOptions
        except ImportError:
            try:
                from DrissionPage import ChromiumPage, ChromiumOptions
            except ImportError:
                logger.error("无法导入ChromiumPage，请确保已安装DrissionPage: pip install DrissionPage")
                return
        
        config = Config()
        
        logger.info(f"开始爬取小红书: 关键词={keyword}, 页数={pages}")
        
        # 初始化浏览器
        logger.info("正在启动浏览器...")
        
        options = ChromiumOptions()
        import random as random_module
        random_port = random_module.randint(9223, 9999)
        options.set_address(f'127.0.0.1:{random_port}')
        options.set_argument(f'--remote-debugging-port={random_port}')
        logger.info(f"使用调试端口: {random_port}")
        
        # 设置用户数据目录，保持登录状态
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        user_data_dir = os.path.join(script_dir, 'chrome_user_data')
        os.makedirs(user_data_dir, exist_ok=True)
        options.set_user_data_path(user_data_dir)
        logger.info(f"使用用户数据目录: {user_data_dir}（保持登录状态）")
        
        options.set_argument(f'--window-size={config.WINDOW_WIDTH},{config.WINDOW_HEIGHT}')
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--disable-dev-shm-usage')
        
        if headless:
            options.headless(True)
        
        # 尝试自动检测浏览器路径（macOS）
        try:
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
        
        try:
            # 检查登录状态
            logger.info("正在检查登录状态...")
            page.get('https://www.xiaohongshu.com')
            page.wait.doc_loaded()
            time.sleep(3)
            
            # 检查是否已登录（通过检查页面元素和Cookie）
            is_logged_in = False
            try:
                # 方法1：检查Cookie中是否有登录相关的cookie
                cookies = page.cookies()
                has_auth_cookie = any('a1' in str(cookie).lower() or 'web_session' in str(cookie).lower() or 'webId' in str(cookie).lower() for cookie in cookies)
                
                # 方法2：检查页面元素
                try:
                    # 查找登录按钮（如果存在说明未登录）
                    login_buttons = page.eles('text:登录', timeout=2)
                    has_login_button = len(login_buttons) > 0
                except:
                    has_login_button = False
                
                # 方法3：检查页面URL和内容
                current_url = page.url
                is_login_page = 'login' in current_url.lower() or 'passport' in current_url.lower()
                
                # 综合判断：如果有认证cookie且没有登录按钮且不是登录页，说明已登录
                if has_auth_cookie and not has_login_button and not is_login_page:
                    is_logged_in = True
                    logger.info("✅ 检测到已登录状态（通过Cookie和页面元素）")
                elif not has_login_button and not is_login_page:
                    # 进一步验证：尝试访问搜索页面
                    try:
                        test_url = 'https://www.xiaohongshu.com/search_result?keyword=test'
                        page.get(test_url)
                        page.wait.doc_loaded()
                        time.sleep(2)
                        # 如果页面正常加载且没有跳转到登录页，说明已登录
                        if 'login' not in page.url.lower() and 'passport' not in page.url.lower():
                            is_logged_in = True
                            logger.info("✅ 检测到已登录状态（通过页面访问验证）")
                    except Exception as e:
                        logger.debug(f"登录验证异常: {e}")
            except Exception as e:
                logger.debug(f"登录状态检查异常: {e}，假设未登录")
            
            if not is_logged_in:
                logger.info("⚠️  未检测到登录状态，请扫码登录小红书...")
                logger.info("浏览器窗口已打开，请在小红书页面扫码登录")
                
                # 检查是否在交互式环境中
                import sys
                if sys.stdin.isatty():
                    # 交互式环境，等待用户输入
                    input('登录完成后按回车继续...')
                else:
                    # 非交互式环境，等待一段时间让用户手动登录
                    logger.info("非交互式环境，等待30秒供您手动登录...")
                    logger.info("如果已登录，脚本将自动继续...")
                    time.sleep(30)
                
                # 再次检查登录状态
                page.get('https://www.xiaohongshu.com')
                page.wait.doc_loaded()
                time.sleep(2)
                
                # 验证登录是否成功
                cookies = page.cookies()
                has_auth_cookie = any('a1' in str(cookie).lower() or 'web_session' in str(cookie).lower() for cookie in cookies)
                if has_auth_cookie:
                    logger.info("✅ 登录成功！登录状态已保存到用户数据目录，下次运行将自动使用")
                else:
                    logger.warning("⚠️  登录状态可能未保存，请确保已成功登录")
            else:
                logger.info("✅ 使用已保存的登录状态，无需重新登录")
            
            time.sleep(2)
            
            # 搜索笔记
            encoded_keyword = quote(keyword)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_explore_feed"
            
            logger.info(f"正在访问搜索页面: {search_url}")
            page.get(search_url)
            page.wait.doc_loaded()
            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
            
            for page_num in range(pages):
                logger.info(f"正在爬取第 {page_num + 1} 页")
                
                api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
                
                packet = None
                retry_count = 0
                
                while True:
                    retry_count += 1
                    
                    try:
                        page.listen.stop()
                    except:
                        pass
                    
                    page.listen.start(api_url)
                    if retry_count == 1:
                        logger.info(f"已启动API监听（第 {page_num + 1} 页）")
                    else:
                        logger.info(f"已启动API监听（第 {page_num + 1} 页，重试第 {retry_count} 次）")
                    
                    time.sleep(2)
                    
                    scroll_steps = random.randint(max(5, config.SCROLL_STEPS_MIN), max(8, config.SCROLL_STEPS_MAX))
                    logger.info(f"开始滚动，步骤数: {scroll_steps}")
                    
                    for step_idx in range(scroll_steps):
                        scroll_distance = random.randint(
                            max(500, config.SCROLL_DISTANCE_MIN), 
                            max(1000, config.SCROLL_DISTANCE_MAX)
                        )
                        page.run_js(f"window.scrollBy(0, {scroll_distance})")
                        scroll_delay = random.uniform(
                            max(1.5, config.SCROLL_INTERVAL_MIN), 
                            max(3.0, config.SCROLL_INTERVAL_MAX)
                        )
                        time.sleep(scroll_delay)
                        
                        try:
                            packet = page.listen.wait(timeout=0.5)
                            if packet and packet.response:
                                logger.info(f"✅ 滚动过程中捕获到API响应（步骤 {step_idx + 1}/{scroll_steps}）")
                                break
                        except:
                            pass
                    
                    if not packet or not packet.response:
                        logger.debug("滚动到底部，等待API响应...")
                        page.run_js("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        
                        try:
                            logger.info(f"等待API响应（超时: {config.REQUEST_TIMEOUT}秒）...")
                            packet = page.listen.wait(timeout=config.REQUEST_TIMEOUT)
                            if packet and packet.response:
                                logger.info(f"✅ 成功捕获API响应")
                                break
                        except Exception as e:
                            logger.warning(f"等待API响应超时: {e}")
                            packet = None
                    
                    if packet and packet.response:
                        break
                    
                    wait_time = min(retry_count * 3, 15)
                    logger.warning(f"未捕获到响应，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                
                # 处理响应
                try:
                    if packet and packet.response:
                        response_body = packet.response.body
                        if response_body:
                            logger.info(f"✅ 捕获到API响应，长度: {len(str(response_body))}")
                            try:
                                if isinstance(response_body, str):
                                    response_data = json.loads(response_body)
                                else:
                                    response_data = response_body
                                
                                if 'data' in response_data and 'items' in response_data['data']:
                                    items = response_data['data']['items']
                                    logger.info(f"✅ 找到 {len(items)} 个笔记项")
                                    note_count = 0
                                    for idx, item in enumerate(items, 1):
                                        note_id = item.get("id")
                                        xsec_token = item.get("xsec_token")
                                        
                                        if note_id and xsec_token:
                                            infourl = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search&source=web_explore_feed"
                                            
                                            time.sleep(random.uniform(3, 6))
                                            page.get(infourl)
                                            page.wait.doc_loaded()
                                            
                                            scroll_steps = random.randint(config.SCROLL_STEPS_MIN, config.SCROLL_STEPS_MAX)
                                            for _ in range(scroll_steps):
                                                scroll_distance = random.randint(config.SCROLL_DISTANCE_MIN, config.SCROLL_DISTANCE_MAX)
                                                page.run_js(f"window.scrollBy(0, {scroll_distance})")
                                                time.sleep(random.uniform(config.SCROLL_INTERVAL_MIN, config.SCROLL_INTERVAL_MAX))
                                            
                                            img_urls = []
                                            try:
                                                swiper_elements = page.eles('.swiper-wrapper')
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
                                                logger.debug(f"获取图片失败: {e}")
                                            
                                            title = ""
                                            desc = ""
                                            try:
                                                title_ele = page.ele("#detail-title")
                                                if title_ele:
                                                    title = title_ele.text.strip()
                                                    
                                                desc_ele = page.ele("#detail-desc")
                                                if desc_ele:
                                                    desc = desc_ele.text.strip()
                                            except Exception as e:
                                                logger.debug(f"获取标题或描述失败: {e}")
                                            
                                            if title:
                                                note = {
                                                    'title': title,
                                                    'description': desc,
                                                    'images': img_urls,
                                                    'url': f"https://www.xiaohongshu.com/explore/{note_id}",
                                                    'note_id': note_id
                                                }
                                                
                                                logger.info(f"✅ 爬取到笔记: {title[:50]}...")
                                                yield note
                                                note_count += 1
                                            else:
                                                logger.warning(f"笔记 {idx} 缺少标题，跳过")
                                        else:
                                            logger.warning(f"笔记 {idx} 缺少note_id或xsec_token，跳过")
                                    
                                    logger.info(f"第 {page_num + 1} 页共提取 {note_count} 条有效笔记")
                                else:
                                    logger.warning(f"响应中未找到 data.items")
                            except Exception as e:
                                logger.warning(f"处理响应失败: {e}", exc_info=True)
                                continue
                        else:
                            logger.warning(f"第 {page_num + 1} 页：响应体为空")
                    else:
                        logger.warning(f"第 {page_num + 1} 页：未捕获到响应")
                except Exception as e:
                    logger.warning(f"第 {page_num + 1} 页处理失败: {e}", exc_info=True)
                
                if page_num < pages - 1:
                    page_delay = random.uniform(config.PAGE_DELAY_MIN, config.PAGE_DELAY_MAX)
                    time.sleep(page_delay)
                
        finally:
            try:
                logger.info("正在关闭浏览器...")
                if 'page' in locals():
                    from base.browser_cleanup import safe_close_browser
                    safe_close_browser(page, random_port if 'random_port' in locals() else None)
                logger.info("✅ 浏览器已关闭，端口已清理")
            except Exception as e:
                logger.warning(f"关闭浏览器时出错: {e}")
                # 最后尝试：强制清理进程
                try:
                    if 'random_port' in locals():
                        from base.browser_cleanup import cleanup_chrome_processes
                        cleanup_chrome_processes(random_port)
                except:
                    pass
                
    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.error("请确保已安装 DrissionPage: pip install DrissionPage")
        return
    except Exception as e:
        logger.error(f"爬取小红书失败: {e}", exc_info=True)
        return


def classify_note_type_with_ai(title: str, description: str) -> str:
    """
    使用AI判断笔记类型：活动或餐厅
    
    Args:
        title: 笔记标题
        description: 笔记描述
        
    Returns:
        'activity' - 活动
        'restaurant' - 餐厅
        'unknown' - 无法判断
    """
    try:
        ai_paraphraser = get_ai_paraphraser()
        
        # 检查AI是否可用
        is_available, error_msg = ai_paraphraser.check_model_available()
        if not is_available:
            logger.warning(f"AI服务不可用: {error_msg}，使用关键词判断")
            return classify_by_keywords(title, description)
        
        # 构建提示词
        prompt = f"""请判断以下小红书笔记的类型。

标题：{title}
描述：{description[:500]}

要求：
1. 判断这是活动还是餐厅推荐
2. 如果是活动（商家活动、同城活动、促销活动等），返回 "activity"
3. 如果是餐厅推荐、美食探店、餐厅评价等，返回 "restaurant"
4. 如果无法确定，返回 "unknown"

只返回一个单词：activity、restaurant 或 unknown"""
        
        # 调用AI
        import requests
        url = f"{ai_paraphraser.api_base}/chat/completions"
        payload = {
            "model": ai_paraphraser.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的内容分类专家，擅长判断小红书笔记是活动还是餐厅推荐。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 10,
            "temperature": 0.3,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=60)
        
        if response and response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip().lower()
            
            if 'activity' in content:
                return 'activity'
            elif 'restaurant' in content:
                return 'restaurant'
            else:
                return 'unknown'
        
        return classify_by_keywords(title, description)
        
    except Exception as e:
        logger.warning(f"AI分类失败: {e}，使用关键词判断")
        return classify_by_keywords(title, description)


def classify_by_keywords(title: str, description: str) -> str:
    """
    使用关键词判断笔记类型（备用方法）
    
    Args:
        title: 笔记标题
        description: 笔记描述
        
    Returns:
        'activity' - 活动
        'restaurant' - 餐厅
        'unknown' - 无法判断
    """
    text = (title + ' ' + description).lower()
    
    # 活动关键词
    activity_keywords = [
        '活动', '促销', '优惠', '折扣', '特价', '限时', '报名', '参与',
        '同城', '商家活动', '开业', '庆典', '节日', '福利', '抽奖',
        '活动时间', '活动地点', '报名方式', '参与条件'
    ]
    
    # 餐厅关键词
    restaurant_keywords = [
        '餐厅', '饭店', '美食', '探店', '打卡', '推荐', '好吃', '味道',
        '菜品', '招牌', '特色', '口味', '环境', '服务', '人均',
        '地址', '营业时间', '菜单', '点餐'
    ]
    
    activity_score = sum(1 for keyword in activity_keywords if keyword in text)
    restaurant_score = sum(1 for keyword in restaurant_keywords if keyword in text)
    
    if activity_score > restaurant_score and activity_score > 0:
        return 'activity'
    elif restaurant_score > activity_score and restaurant_score > 0:
        return 'restaurant'
    else:
        return 'unknown'


def extract_activity_info_with_ai(title: str, description: str, images: List[str]) -> Optional[Dict]:
    """
    使用AI从小红书内容中提取活动信息
    
    Args:
        title: 笔记标题
        description: 笔记描述
        images: 图片列表
        
    Returns:
        活动信息字典，如果提取失败返回None
    """
    try:
        ai_paraphraser = get_ai_paraphraser()
        
        # 检查AI是否可用
        is_available, error_msg = ai_paraphraser.check_model_available()
        if not is_available:
            logger.error(f"AI服务不可用: {error_msg}")
            return None
        
        # 构建提示词
        prompt = f"""请从以下小红书笔记中提取活动信息。

标题：{title}
描述：{description[:1000]}

要求：
1. 判断这是否是一个活动（商家活动或同城活动）
2. 如果是活动，提取以下信息：
   - 活动标题（简洁明了，3-16字）
   - 活动类型（1=商家活动，2=同城活动）
   - 活动地区（城市名称，如"上海"、"深圳"）
   - 活动描述（详细描述，100-500字）
   - 活动开始时间（格式：YYYY-MM-DD，如果无法确定，使用当前日期）
   - 活动结束时间（格式：YYYY-MM-DD，如果无法确定，使用开始时间+7天）
   - 参与条件（如果有，否则填写"无"）

请以JSON格式返回结果：
{{
    "is_activity": true/false,
    "act_title": "活动标题",
    "act_type": "1或2",
    "act_location": "活动地区",
    "act_describe": "活动描述",
    "act_start_date": "YYYY-MM-DD",
    "act_end_date": "YYYY-MM-DD",
    "join_condition": "参与条件"
}}

如果不是活动，is_activity设为false，其他字段可以为空。"""
        
        # 调用AI
        import requests
        url = f"{ai_paraphraser.api_base}/chat/completions"
        payload = {
            "model": ai_paraphraser.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的活动信息提取专家，擅长从小红书笔记中识别和提取活动信息。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 800,
            "temperature": 0.5,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=120)
        
        if response and response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # 解析JSON响应
            parsed = ai_paraphraser._parse_json_response(content)
            if parsed:
                if parsed.get('is_activity'):
                    return parsed
                else:
                    logger.debug("AI判断这不是活动")
                    return None
            else:
                logger.warning("无法解析AI响应")
                return None
        
        return None
        
    except Exception as e:
        logger.error(f"使用AI提取活动信息失败: {e}")
        return None


def extract_location_code(location: str) -> str:
    """
    从地区名称提取地区编码
    
    Args:
        location: 地区名称（如"上海"、"深圳"）
        
    Returns:
        地区编码（6位数字字符串）
    """
    # 常见城市编码映射（简化版，实际应该从数据库或API获取）
    city_code_map = {
        '北京': '110000',
        '上海': '310000',
        '广州': '440100',
        '深圳': '440300',
        '杭州': '330100',
        '成都': '510100',
        '南京': '320100',
        '武汉': '420100',
        '西安': '610100',
        '重庆': '500000',
        '苏州': '320500',
        '天津': '120000',
        '长沙': '430100',
        '郑州': '410100',
        '青岛': '370200',
        '大连': '210200',
        '宁波': '330200',
        '厦门': '350200',
        '福州': '350100',
        '合肥': '340100',
        '昆明': '530100',
    }
    
    # 尝试直接匹配
    for city, code in city_code_map.items():
        if city in location:
            return code
    
    # 如果找不到，返回默认值（上海）
    return '310000'


def insert_activity(activity_info: Dict, image_url: str) -> Optional[int]:
    """
    插入活动到数据库
    
    Args:
        activity_info: 活动信息字典
        image_url: 活动图片URL
        
    Returns:
        插入的活动ID，如果失败返回None
    """
    try:
        # 准备数据
        act_title = activity_info.get('act_title', '').strip()
        act_type = activity_info.get('act_type', '2')  # 默认同城活动
        act_location = activity_info.get('act_location', '上海').strip()
        act_describe = activity_info.get('act_describe', '').strip()
        act_start_date = activity_info.get('act_start_date', '')
        act_end_date = activity_info.get('act_end_date', '')
        join_condition = activity_info.get('join_condition', '无').strip()
        
        # 验证必填字段
        if not act_title or len(act_title) < 3:
            logger.warning(f"活动标题无效: {act_title}")
            return None
        
        if len(act_title) > 16:
            act_title = act_title[:16]
        
        # 提取地区编码
        act_location_code = extract_location_code(act_location)
        
        # 处理日期
        try:
            if act_start_date:
                start_date = datetime.strptime(act_start_date, '%Y-%m-%d').date()
            else:
                start_date = datetime.now().date()
            
            if act_end_date:
                end_date = datetime.strptime(act_end_date, '%Y-%m-%d').date()
            else:
                end_date = start_date + timedelta(days=7)
        except Exception as e:
            logger.warning(f"日期解析失败: {e}，使用默认日期")
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=7)
        
        # 构建INSERT语句
        sql = """
            INSERT INTO activity (
                act_title, act_type, act_location, act_location_code,
                act_img, act_describe, act_start_date, act_end_date, join_condition
            ) VALUES (
                :act_title, :act_type, :act_location, :act_location_code,
                :act_img, :act_describe, :act_start_date, :act_end_date, :join_condition
            )
        """
        
        params = {
            'act_title': act_title,
            'act_type': act_type,
            'act_location': act_location,
            'act_location_code': act_location_code,
            'act_img': image_url,
            'act_describe': act_describe,
            'act_start_date': start_date.strftime('%Y-%m-%d'),
            'act_end_date': end_date.strftime('%Y-%m-%d'),
            'join_condition': join_condition
        }
        
        with db.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            conn.commit()
            activity_id = result.lastrowid
            logger.info(f"✅ 成功插入活动: {act_title} (ID: {activity_id})")
            return activity_id
            
    except Exception as e:
        logger.error(f"插入活动失败: {e}", exc_info=True)
        return None


def crawl_and_process_all(
    keyword: str,
    pages: int = 5,
    city: str = "上海",
    headless: bool = False,
    process_activities: bool = True,
    process_restaurants: bool = True,
    activity_limit: Optional[int] = None,
    restaurant_limit: Optional[int] = None,
    generate_comments: bool = True
):
    """
    整合爬虫：同时爬取活动和餐厅
    
    Args:
        keyword: 搜索关键词
        pages: 爬取页数
        city: 城市名称（用于餐厅地址搜索）
        headless: 是否使用无头模式
        process_activities: 是否处理活动（默认：True）
        process_restaurants: 是否处理餐厅（默认：True）
        activity_limit: 最多上传的活动数量（None表示不限制）
        restaurant_limit: 最多上传的餐厅数量（None表示不限制）
        generate_comments: 是否生成评论（默认：True）
    """
    try:
        logger.info(f"开始整合爬取: 关键词={keyword}, 页数={pages}")
        logger.info(f"处理活动: {process_activities}, 处理餐厅: {process_restaurants}")
        
        stats = {
            'total_notes': 0,
            'activities': {
                'detected': 0,
                'extracted': 0,
                'uploaded': 0,
                'failed': 0
            },
            'restaurants': {
                'detected': 0,
                'extracted': 0,
                'uploaded': 0,
                'failed': 0
            },
            'unknown': 0
        }
        
        # 爬取小红书内容
        for note in crawl_xiaohongshu_generator(keyword, pages, headless):
            stats['total_notes'] += 1
            
            title = note.get('title', '')
            description = note.get('description', '')
            images = note.get('images', [])
            
            logger.info(f"\n[{stats['total_notes']}] 处理笔记: {title[:50]}...")
            
            # 使用AI判断笔记类型
            note_type = classify_note_type_with_ai(title, description)
            logger.info(f"  类型判断: {note_type}")
            
            if note_type == 'activity' and process_activities:
                stats['activities']['detected'] += 1
                
                # 检查是否达到限制
                if activity_limit and stats['activities']['uploaded'] >= activity_limit:
                    logger.info(f"已达到活动上传限制 ({activity_limit}个)，跳过活动处理")
                    if not process_restaurants:
                        break
                    continue
                
                # 提取活动信息
                activity_info = extract_activity_info_with_ai(title, description, images)
                
                if activity_info:
                    stats['activities']['extracted'] += 1
                    logger.info(f"  ✅ 提取到活动信息: {activity_info.get('act_title')}")
                    
                    # 选择第一张图片作为活动图片
                    image_url = images[0] if images else ''
                    
                    # 插入数据库
                    activity_id = insert_activity(activity_info, image_url)
                    
                    if activity_id:
                        stats['activities']['uploaded'] += 1
                    else:
                        stats['activities']['failed'] += 1
                else:
                    stats['activities']['failed'] += 1
                    
            elif note_type == 'restaurant' and process_restaurants:
                stats['restaurants']['detected'] += 1
                
                # 检查是否达到限制
                if restaurant_limit and stats['restaurants']['uploaded'] >= restaurant_limit:
                    logger.info(f"已达到餐厅上传限制 ({restaurant_limit}个)，跳过餐厅处理")
                    if not process_activities:
                        break
                    continue
                
                # 处理餐厅（使用现有的process_note函数）
                try:
                    result = process_note(
                        title=title,
                        description=description,
                        city=city,
                        images=images,
                        generate_comments=generate_comments
                    )
                    
                    if result.get('success', 0) > 0:
                        stats['restaurants']['extracted'] += result.get('total_restaurants', 0)
                        stats['restaurants']['uploaded'] += result.get('success', 0)
                        stats['restaurants']['failed'] += result.get('failed', 0)
                    else:
                        stats['restaurants']['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"处理餐厅失败: {e}")
                    stats['restaurants']['failed'] += 1
                    
            else:
                if note_type == 'unknown':
                    stats['unknown'] += 1
                    logger.debug(f"  跳过：类型未知")
                elif note_type == 'activity' and not process_activities:
                    logger.debug(f"  跳过：活动处理已禁用")
                elif note_type == 'restaurant' and not process_restaurants:
                    logger.debug(f"  跳过：餐厅处理已禁用")
        
        # 显示统计信息
        logger.info("\n" + "=" * 60)
        logger.info("处理完成！")
        logger.info("=" * 60)
        logger.info(f"总计笔记: {stats['total_notes']} 条")
        logger.info("")
        logger.info("活动统计:")
        logger.info(f"  检测到: {stats['activities']['detected']} 个")
        logger.info(f"  提取成功: {stats['activities']['extracted']} 个")
        logger.info(f"  上传成功: {stats['activities']['uploaded']} 个")
        logger.info(f"  上传失败: {stats['activities']['failed']} 个")
        logger.info("")
        logger.info("餐厅统计:")
        logger.info(f"  检测到: {stats['restaurants']['detected']} 个")
        logger.info(f"  提取成功: {stats['restaurants']['extracted']} 个")
        logger.info(f"  上传成功: {stats['restaurants']['uploaded']} 个")
        logger.info(f"  上传失败: {stats['restaurants']['failed']} 个")
        logger.info("")
        logger.info(f"未知类型: {stats['unknown']} 个")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"爬取和处理失败: {e}", exc_info=True)
        raise


def crawl_only(keyword: str, pages: int = 5, headless: bool = False, output: Optional[str] = None, limit: Optional[int] = None):
    """
    只爬取小红书内容，不进行处理（保存到文件或输出到标准输出）
    
    Args:
        keyword: 搜索关键词
        pages: 爬取页数
        headless: 是否使用无头模式
        output: 输出文件路径（JSON格式，每行一个笔记）
        limit: 限制爬取数量
    """
    try:
        logger.info("=" * 80)
        logger.info("开始爬取小红书内容（仅爬取模式）")
        logger.info("=" * 80)
        
        notes = []
        note_count = 0
        
        for note in crawl_xiaohongshu_generator(
            keyword=keyword,
            pages=pages,
            headless=headless
        ):
            if limit and note_count >= limit:
                break
            
            notes.append(note)
            note_count += 1
            logger.info(f"已爬取 {note_count} 条笔记")
        
        if note_count == 0:
            logger.warning("未爬取到任何笔记")
            return
        
        logger.info(f"\n成功爬取 {note_count} 条笔记")
        
        # 保存到文件
        if output:
            logger.info(f"保存到文件: {output}")
            with open(output, 'w', encoding='utf-8') as f:
                for note in notes:
                    f.write(json.dumps(note, ensure_ascii=False) + '\n')
            logger.info(f"✅ 已保存 {len(notes)} 条笔记到 {output}")
        else:
            # 输出到标准输出
            logger.info("\n笔记内容（JSON格式）:")
            for note in notes:
                print(json.dumps(note, ensure_ascii=False))
        
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.info("\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        raise


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='整合爬虫：同时支持爬取活动和餐厅，也支持仅爬取模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 同时爬取活动和餐厅
  python3 crawl_all.py --keyword "上海美食" --pages 3 --city 上海
  
  # 只爬取活动
  python3 crawl_all.py --keyword "上海活动" --pages 3 --no-restaurants
  
  # 只爬取餐厅
  python3 crawl_all.py --keyword "上海美食" --pages 3 --city 上海 --no-activities
  
  # 限制数量
  python3 crawl_all.py --keyword "上海" --pages 5 --activity-limit 5 --restaurant-limit 10
  
  # 仅爬取模式（不处理，保存到文件）
  python3 crawl_all.py --keyword "上海美食" --pages 5 --output notes.json
  
  # 仅爬取模式（限制数量）
  python3 crawl_all.py --keyword "上海美食" --pages 5 --output notes.json --limit 10
        """
    )
    
    parser.add_argument('--keyword', type=str, required=True, help='搜索关键词')
    parser.add_argument('--pages', type=int, default=5, help='爬取页数（默认：5）')
    parser.add_argument('--city', type=str, default='上海', help='城市名称（默认：上海）')
    parser.add_argument('--headless', action='store_true', help='使用无头模式')
    parser.add_argument('--no-activities', action='store_true', help='不处理活动')
    parser.add_argument('--no-restaurants', action='store_true', help='不处理餐厅')
    parser.add_argument('--activity-limit', type=int, help='最多上传的活动数量')
    parser.add_argument('--restaurant-limit', type=int, help='最多上传的餐厅数量')
    parser.add_argument('--no-comments', action='store_true', help='不生成评论')
    parser.add_argument('--output', type=str, help='输出文件路径（JSON格式，如果指定则仅爬取不处理）')
    parser.add_argument('--limit', type=int, help='限制爬取数量（仅爬取模式）')
    
    args = parser.parse_args()
    
    # 如果指定了output，则只爬取不处理
    if args.output:
        crawl_only(
            keyword=args.keyword,
            pages=args.pages,
            headless=args.headless,
            output=args.output,
            limit=args.limit
        )
    else:
        crawl_and_process_all(
            keyword=args.keyword,
            pages=args.pages,
            city=args.city,
            headless=args.headless,
            process_activities=not args.no_activities,
            process_restaurants=not args.no_restaurants,
            activity_limit=args.activity_limit,
            restaurant_limit=args.restaurant_limit,
            generate_comments=not args.no_comments
        )


if __name__ == '__main__':
    main()

