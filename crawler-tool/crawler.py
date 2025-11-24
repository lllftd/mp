#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫主入口脚本
完整流程：小红书爬虫 → 提取餐厅 → AI转述内容及评论 → 上传数据库
"""
import os
import sys
import logging
import argparse
import random
import json
from typing import List, Dict, Optional

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_service import get_ai_paraphraser
from app.services.address_service import AddressService
from app.services.tweet_service import prepare_tweet_data, insert_tweet
from base.utils import get_random_username
from base.monitors import MemoryMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def crawl_xiaohongshu_generator(keyword: str, pages: int = 5, headless: bool = False):
    """
    爬取小红书笔记（生成器模式，逐条返回，爬取一条立即yield）
    
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
        
        from base.config import Config
        
        config = Config()
        
        logger.info(f"开始爬取小红书: 关键词={keyword}, 页数={pages}")
        
        # 初始化浏览器
        logger.info("正在启动浏览器...")
        
        options = ChromiumOptions()
        # 设置随机端口，避免端口冲突
        import random as random_module
        random_port = random_module.randint(9223, 9999)
        # 使用 set_address 方法设置地址和端口
        options.set_address(f'127.0.0.1:{random_port}')
        # 同时设置启动参数
        options.set_argument(f'--remote-debugging-port={random_port}')
        logger.info(f"使用调试端口: {random_port}")
        
        # 不使用用户数据目录，确保每次都是全新的浏览器实例
        # 如果需要保持登录状态，可以取消下面的注释
        # user_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'chrome_user_data')
        # if os.path.exists(user_data_dir):
        #     options.set_argument(f'--user-data-dir={user_data_dir}')
        #     logger.info(f"使用用户数据目录: {user_data_dir}")
        
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
        
        try:
            # 登录
            logger.info("请扫码登录小红书...")
            page.get('https://www.xiaohongshu.com')
            input('登录完成后按回车继续...')
            time.sleep(3)
            
            # 搜索笔记
            encoded_keyword = quote(keyword)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_explore_feed"
            
            logger.info(f"正在访问搜索页面: {search_url}")
            page.get(search_url)
            page.wait.doc_loaded()
            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
            
            for page_num in range(pages):
                logger.info(f"正在爬取第 {page_num + 1} 页")
                
                # 使用固定的API端点
                api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
                
                # 重试机制：如果没有响应，一直重复滚动和等待，直到成功
                packet = None
                retry_count = 0
                
                while True:  # 无限循环，直到成功捕获响应
                    retry_count += 1
                    
                    # 每次重试重新启动监听
                    try:
                        page.listen.stop()  # 先停止之前的监听
                    except:
                        pass
                    
                    page.listen.start(api_url)
                    if retry_count == 1:
                        logger.info(f"已启动API监听（第 {page_num + 1} 页）")
                    else:
                        logger.info(f"已启动API监听（第 {page_num + 1} 页，重试第 {retry_count} 次）")
                    
                    # 等待一小段时间，确保监听已启动
                    time.sleep(2)
                    
                    # 模拟人类滚动（滚动会触发API请求）
                    scroll_steps = random.randint(max(5, config.SCROLL_STEPS_MIN), max(8, config.SCROLL_STEPS_MAX))
                    logger.info(f"开始滚动，步骤数: {scroll_steps}")
                    
                    for step_idx in range(scroll_steps):
                        # 增加滚动距离，确保能滚动到页面底部触发加载更多
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
                        
                        # 在滚动过程中检查是否有响应（非阻塞）
                        try:
                            packet = page.listen.wait(timeout=0.5)  # 短暂等待，不阻塞
                            if packet and packet.response:
                                logger.info(f"✅ 滚动过程中捕获到API响应（步骤 {step_idx + 1}/{scroll_steps}）")
                                break
                        except:
                            pass  # 超时是正常的，继续滚动
                    
                    # 如果滚动过程中没有捕获到，滚动到底部并等待
                    if not packet or not packet.response:
                        logger.debug("滚动到底部，等待API响应...")
                        page.run_js("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        
                        # 等待API响应
                        try:
                            logger.info(f"等待API响应（超时: {config.REQUEST_TIMEOUT}秒）...")
                            packet = page.listen.wait(timeout=config.REQUEST_TIMEOUT)
                            if packet and packet.response:
                                logger.info(f"✅ 成功捕获API响应")
                                break
                        except Exception as e:
                            logger.warning(f"等待API响应超时: {e}")
                            packet = None
                    
                    # 如果捕获到响应，跳出重试循环
                    if packet and packet.response:
                        break
                    
                    # 如果没有捕获到，等待一段时间后重试
                    wait_time = min(retry_count * 3, 15)  # 等待时间递增，最多15秒
                    logger.warning(f"未捕获到响应，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                
                # 处理响应
                try:
                    if packet and packet.response:
                        response_body = packet.response.body
                        if response_body:
                            logger.info(f"✅ 捕获到API响应，长度: {len(str(response_body))}")
                            # 处理响应，提取笔记信息
                            try:
                                if isinstance(response_body, str):
                                    response_data = json.loads(response_body)
                                else:
                                    response_data = response_body
                                
                                logger.info(f"响应数据结构: {list(response_data.keys()) if isinstance(response_data, dict) else '非字典类型'}")
                                
                                if 'data' in response_data and 'items' in response_data['data']:
                                    items = response_data['data']['items']
                                    logger.info(f"✅ 找到 {len(items)} 个笔记项")
                                    note_count = 0
                                    for idx, item in enumerate(items, 1):
                                        note_id = item.get("id")
                                        xsec_token = item.get("xsec_token")
                                        
                                        logger.debug(f"笔记 {idx}: note_id={note_id}, xsec_token={'有' if xsec_token else '无'}")
                                        
                                        if note_id and xsec_token:
                                            # 获取笔记详情
                                            infourl = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search&source=web_explore_feed"
                                            
                                            time.sleep(random.uniform(3, 6))
                                            page.get(infourl)
                                            page.wait.doc_loaded()
                                            
                                            # 模拟滚动
                                            scroll_steps = random.randint(config.SCROLL_STEPS_MIN, config.SCROLL_STEPS_MAX)
                                            for _ in range(scroll_steps):
                                                scroll_distance = random.randint(config.SCROLL_DISTANCE_MIN, config.SCROLL_DISTANCE_MAX)
                                                page.run_js(f"window.scrollBy(0, {scroll_distance})")
                                                time.sleep(random.uniform(config.SCROLL_INTERVAL_MIN, config.SCROLL_INTERVAL_MAX))
                                            
                                            # 获取图片链接
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
                                            
                                            # 获取标题和描述
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
                                                # 立即yield返回，让主函数立即处理（提取餐厅 → AI转述 → 上传）
                                                yield note
                                                note_count += 1
                                            else:
                                                logger.warning(f"笔记 {idx} 缺少标题，跳过")
                                        else:
                                            logger.warning(f"笔记 {idx} 缺少note_id或xsec_token，跳过")
                                    
                                    logger.info(f"第 {page_num + 1} 页共提取 {note_count} 条有效笔记")
                                else:
                                    logger.warning(f"响应中未找到 data.items，响应结构: {list(response_data.keys()) if isinstance(response_data, dict) else type(response_data)}")
                                    logger.info(f"响应内容前500字符: {str(response_body)[:500]}")
                            except Exception as e:
                                logger.warning(f"处理响应失败: {e}", exc_info=True)
                                logger.debug(f"响应内容前500字符: {str(response_body)[:500]}")
                                continue
                        else:
                            logger.warning(f"第 {page_num + 1} 页：响应体为空")
                    else:
                        logger.warning(f"第 {page_num + 1} 页：未捕获到响应或响应无效（超时或packet为None）")
                except Exception as e:
                    logger.warning(f"第 {page_num + 1} 页处理失败: {e}", exc_info=True)
                
                # 页面间延迟
                if page_num < pages - 1:
                    page_delay = random.uniform(config.PAGE_DELAY_MIN, config.PAGE_DELAY_MAX)
                    time.sleep(page_delay)
                
        finally:
            # 确保退出时关闭浏览器并清理端口
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


def crawl_xiaohongshu(keyword: str, pages: int = 5, headless: bool = False) -> List[Dict]:
    """
    爬取小红书笔记
    
    Args:
        keyword: 搜索关键词
        pages: 爬取页数
        headless: 是否使用无头模式
        
    Returns:
        笔记列表，每个笔记包含 title, description, images, url
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
                return []
        
        from base.config import Config
        
        config = Config()
        
        logger.info(f"开始爬取小红书: 关键词={keyword}, 页数={pages}")
        
        # 初始化浏览器（参考远程仓库实现：使用ChromiumOptions配置，然后创建ChromiumPage）
        logger.info("正在启动浏览器...")
        
        # 创建浏览器选项（让DrissionPage自动启动浏览器）
        options = ChromiumOptions()
        # 设置随机端口，避免端口冲突
        import random as random_module
        random_port = random_module.randint(9223, 9999)
        # 使用 set_address 方法设置地址和端口
        options.set_address(f'127.0.0.1:{random_port}')
        # 同时设置启动参数
        options.set_argument(f'--remote-debugging-port={random_port}')
        logger.info(f"使用调试端口: {random_port}")
        
        # 不使用用户数据目录，确保每次都是全新的浏览器实例
        # 如果需要保持登录状态，可以取消下面的注释
        # user_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'chrome_user_data')
        # if os.path.exists(user_data_dir):
        #     options.set_argument(f'--user-data-dir={user_data_dir}')
        #     logger.info(f"使用用户数据目录: {user_data_dir}")
        
        # 设置窗口大小
        options.set_argument(f'--window-size={config.WINDOW_WIDTH},{config.WINDOW_HEIGHT}')
        
        # 添加其他必要的浏览器参数
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--disable-dev-shm-usage')
        
        # 无头模式
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
        
        # 创建浏览器页面（DrissionPage会自动启动浏览器）
        try:
            page = ChromiumPage(options)
            logger.info("✅ 浏览器启动成功")
        except Exception as e:
            logger.warning(f"使用配置启动失败: {e}，尝试使用默认配置...")
            # 如果失败，尝试使用默认配置（参考远程仓库实现）
            try:
                page = ChromiumPage()
                logger.info("✅ 使用默认配置启动浏览器成功")
            except Exception as e2:
                logger.error(f"浏览器启动失败: {e2}")
                raise
        
        # 设置浏览器参数（参考远程仓库实现）
        user_agent = random.choice(config.USER_AGENTS)
        headers = config.DEFAULT_HEADERS.copy()
        headers['User-Agent'] = user_agent
        
        try:
            page.set.headers(headers)
            page.set.window.size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
            logger.info("✅ 浏览器参数已配置")
        except Exception as e:
            logger.warning(f"设置浏览器参数失败: {e}，继续使用默认配置")
        
        notes = []
        
        try:
            # 登录
            logger.info("请扫码登录小红书...")
            page.get('https://www.xiaohongshu.com')
            input('登录完成后按回车继续...')
            time.sleep(3)
            
            # 搜索笔记
            encoded_keyword = quote(keyword)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_explore_feed"
            
            logger.info(f"正在访问搜索页面: {search_url}")
            page.get(search_url)
            page.wait.doc_loaded()
            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
            
            responses = []
            
            for page_num in range(pages):
                logger.info(f"正在爬取第 {page_num + 1} 页")
                
                # 使用固定的API端点
                api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
                
                # 重试机制：如果没有响应，一直重复滚动和等待，直到成功
                packet = None
                retry_count = 0
                
                while True:  # 无限循环，直到成功捕获响应
                    retry_count += 1
                    
                    # 每次重试重新启动监听
                    try:
                        page.listen.stop()  # 先停止之前的监听
                    except:
                        pass
                    
                    page.listen.start(api_url)
                    if retry_count == 1:
                        logger.info(f"已启动API监听（第 {page_num + 1} 页）")
                    else:
                        logger.info(f"已启动API监听（第 {page_num + 1} 页，重试第 {retry_count} 次）")
                    
                    # 等待一小段时间，确保监听已启动
                    time.sleep(2)
                    
                    # 模拟人类滚动（滚动会触发API请求）
                    scroll_steps = random.randint(max(5, config.SCROLL_STEPS_MIN), max(8, config.SCROLL_STEPS_MAX))
                    logger.info(f"开始滚动，步骤数: {scroll_steps}")
                    
                    for step_idx in range(scroll_steps):
                        # 增加滚动距离，确保能滚动到页面底部触发加载更多
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
                        
                        # 在滚动过程中检查是否有响应（非阻塞）
                        try:
                            packet = page.listen.wait(timeout=0.5)  # 短暂等待，不阻塞
                            if packet and packet.response:
                                logger.info(f"✅ 滚动过程中捕获到API响应（步骤 {step_idx + 1}/{scroll_steps}）")
                                break
                        except:
                            pass  # 超时是正常的，继续滚动
                    
                    # 如果滚动过程中没有捕获到，滚动到底部并等待
                    if not packet or not packet.response:
                        logger.debug("滚动到底部，等待API响应...")
                        page.run_js("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(2)
                        
                        # 等待API响应
                        try:
                            logger.info(f"等待API响应（超时: {config.REQUEST_TIMEOUT}秒）...")
                            packet = page.listen.wait(timeout=config.REQUEST_TIMEOUT)
                            if packet and packet.response:
                                logger.info(f"✅ 成功捕获API响应")
                                break
                        except Exception as e:
                            logger.warning(f"等待API响应超时: {e}")
                            packet = None
                    
                    # 如果捕获到响应，跳出重试循环
                    if packet and packet.response:
                        break
                    
                    # 如果没有捕获到，等待一段时间后重试
                    wait_time = min(retry_count * 3, 15)  # 等待时间递增，最多15秒
                    logger.warning(f"未捕获到响应，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                
                # 处理响应
                if packet and packet.response:
                    response_body = packet.response.body
                    if response_body:
                        responses.append(response_body)
                        logger.info(f"✅ 成功捕获第 {page_num + 1} 页数据")
                    else:
                        logger.warning(f"第 {page_num + 1} 页：响应体为空")
                else:
                    logger.warning(f"第 {page_num + 1} 页：未捕获到响应")
                
                # 页面间延迟
                if page_num < pages - 1:
                    page_delay = random.uniform(config.PAGE_DELAY_MIN, config.PAGE_DELAY_MAX)
                    time.sleep(page_delay)
            
            # 处理响应，提取笔记信息
            for response in responses:
                try:
                    if isinstance(response, str):
                        response_data = json.loads(response)
                    else:
                        response_data = response
                    
                    if 'data' in response_data and 'items' in response_data['data']:
                        items = response_data['data']['items']
                        for item in items:
                            note_id = item.get("id")
                            xsec_token = item.get("xsec_token")
                            
                            if note_id and xsec_token:
                                # 获取笔记详情
                                infourl = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search&source=web_explore_feed"
                                
                                time.sleep(random.uniform(3, 6))
                                page.get(infourl)
                                page.wait.doc_loaded()
                                
                                # 模拟滚动
                                scroll_steps = random.randint(config.SCROLL_STEPS_MIN, config.SCROLL_STEPS_MAX)
                                for _ in range(scroll_steps):
                                    scroll_distance = random.randint(config.SCROLL_DISTANCE_MIN, config.SCROLL_DISTANCE_MAX)
                                    page.run_js(f"window.scrollBy(0, {scroll_distance})")
                                    time.sleep(random.uniform(config.SCROLL_INTERVAL_MIN, config.SCROLL_INTERVAL_MAX))
                                
                                # 获取图片链接
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
                                
                                # 获取标题和描述
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
                                    notes.append({
                                        'title': title,
                                        'description': desc,
                                        'images': img_urls,
                                        'url': f"https://www.xiaohongshu.com/explore/{note_id}",
                                        'note_id': note_id
                                    })
                                    
                                    logger.info(f"✅ 提取笔记: {title[:50]}...")
                except Exception as e:
                    logger.warning(f"处理响应失败: {e}")
                    continue
            
            logger.info(f"成功爬取 {len(notes)} 条笔记")
            return notes
            
        finally:
            # 确保退出时关闭浏览器并清理端口
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
        return []
    except Exception as e:
        logger.error(f"爬取小红书失败: {e}", exc_info=True)
        return []


def process_restaurant(restaurant_data: Dict, city: str = "上海") -> Dict:
    """
    处理一条 Trip.com 餐厅数据，完整流程：转述内容及评论 → 上传数据库
    
    Args:
        restaurant_data: 餐厅数据字典，包含 name, address, rating, price_range, cuisine, images, description 等
        city: 城市名称（用于地址搜索）
        
    Returns:
        处理结果统计字典
    """
    ai_paraphraser = get_ai_paraphraser()
    address_service = AddressService()
    
    stats = {
        'total_restaurants': 1,
        'success': 0,
        'failed': 0,
        'comments_generated': 0,
        'errors': []
    }
    
    try:
        restaurant_name = restaurant_data.get('name', '未知')
        logger.info(f"开始处理餐厅: {restaurant_name}")
        
        # 如果已有地址，使用已有地址；否则使用高德API搜索
        address = restaurant_data.get('address', '')
        if not address:
            logger.info(f"  使用高德API搜索餐厅地址: {restaurant_name}")
            address_result = address_service.search_restaurant_address(restaurant_name, city)
            
            if address_result and address_result.get('address'):
                address = address_result['address']
                city_name = address_result.get('city', city)
                if city_name and city_name.endswith('市'):
                    city_name = city_name[:-1]
                restaurant_data['city'] = city_name
                restaurant_data['district'] = address_result.get('district', '')
                restaurant_data['adcode'] = address_result.get('adcode', '')
                restaurant_data['province'] = address_result.get('province', '')
                logger.info(f"  ✅ 高德API返回地址: {address}")
            else:
                logger.warning(f"  ⚠️  高德API未找到地址")
                stats['failed'] += 1
                stats['errors'].append(f"{restaurant_name}: 高德API未找到地址")
                return stats
        else:
            # 使用已有地址，尝试从地址中提取城市
            from base.location_utils import extract_city_from_address
            extracted_city = extract_city_from_address(address)
            if extracted_city:
                restaurant_data['city'] = extracted_city
            else:
                restaurant_data['city'] = city
        
        # 构建餐厅信息
        restaurant_info = {
            'name': restaurant_name,
            'address': address,
            'city': restaurant_data.get('city', city),
            'district': restaurant_data.get('district', ''),
            'adcode': restaurant_data.get('adcode', ''),
            'province': restaurant_data.get('province', ''),
            'rating': restaurant_data.get('rating'),
            'price_range': restaurant_data.get('price_range'),
            'cuisine': restaurant_data.get('cuisine')
        }
        
        # 构建描述文本（用于AI转述）
        description_parts = []
        if restaurant_data.get('description'):
            description_parts.append(restaurant_data['description'])
        if restaurant_data.get('rating'):
            description_parts.append(f"评分: {restaurant_data['rating']}")
        if restaurant_data.get('price_range'):
            description_parts.append(f"价格: {restaurant_data['price_range']}")
        if restaurant_data.get('cuisine'):
            description_parts.append(f"菜系: {restaurant_data['cuisine']}")
        if restaurant_data.get('review_count'):
            description_parts.append(f"评价数: {restaurant_data['review_count']}")
        
        description = ' | '.join(description_parts) if description_parts else f"这是一家位于{address}的餐厅"
        
        # AI转述内容并生成评论
        logger.info(f"  步骤1: AI转述内容并生成评论...")
        paraphrased_title, paraphrased_desc, type_cid, comments = ai_paraphraser.paraphrase_restaurant(
            restaurant_info=restaurant_info,
            original_title=restaurant_name,
            original_description=description,
            tweet_id=None,
            auto_generate_comments=True
        )
        
        if not paraphrased_title or not paraphrased_desc or not type_cid:
            logger.error(f"  ❌ AI转述失败")
            stats['failed'] += 1
            stats['errors'].append(f"{restaurant_name}: 转述失败")
            return stats
        
        logger.info(f"  ✅ AI转述成功")
        logger.info(f"    转述标题: {paraphrased_title[:50]}...")
        logger.info(f"    转述描述: {paraphrased_desc[:100]}...")
        logger.info(f"    类型ID: {type_cid}")
        logger.info(f"    生成评论数: {len(comments)} 条")
        stats['comments_generated'] += len(comments)
        
        # 准备推文数据
        images = restaurant_data.get('images', [])
        tweet_data = {
            'tweets_title': restaurant_name,
            'tweets_content': paraphrased_desc,
            'tweets_describe': address,
            'tweets_img': images,
            'tweets_type_pid': 5,  # 美食类型
            'tweets_type_cid': type_cid,
            'tweets_user': get_random_username(),
            'tweets_location': restaurant_info['city'],
            'tweets_location_code': restaurant_info.get('adcode', ''),
            'like_num': random.randint(10, 500),
            'collect_num': random.randint(5, 100),
            'browse_num': random.randint(50, 2000)
        }
        
        # 验证并准备数据
        try:
            prepared_data = prepare_tweet_data(tweet_data)
        except ValueError as e:
            logger.error(f"  ❌ 数据验证失败: {e}")
            stats['failed'] += 1
            stats['errors'].append(f"{restaurant_name}: {str(e)}")
            return stats
        
        # 插入推文到数据库
        logger.info(f"  插入推文到数据库...")
        tweet_id = insert_tweet(prepared_data)
        
        if tweet_id:
            logger.info(f"  ✅ 推文插入成功，ID: {tweet_id}")
            
            # 插入评论到数据库
            if comments:
                inserted_count = ai_paraphraser.insert_comments_to_db(tweet_id, comments)
                logger.info(f"  ✅ 评论插入成功: {inserted_count}/{len(comments)} 条")
            
            stats['success'] += 1
        else:
            logger.error(f"  ❌ 推文插入失败")
            stats['failed'] += 1
            stats['errors'].append(f"{restaurant_name}: 推文插入失败")
        
        return stats
        
    except Exception as e:
        logger.error(f"处理餐厅失败: {e}", exc_info=True)
        stats['errors'].append(f"处理餐厅失败: {str(e)}")
        stats['failed'] += 1
        return stats


def process_note(title: str, description: str, city: str = "上海", images: List[str] = None) -> Dict:
    """
    处理一条小红书笔记，完整流程：提取餐厅 → 转述内容及评论 → 上传数据库
    
    Args:
        title: 笔记标题
        description: 笔记描述
        city: 城市名称（用于地址搜索）
        images: 图片列表（可选）
        
    Returns:
        处理结果统计字典
    """
    ai_paraphraser = get_ai_paraphraser()
    address_service = AddressService()
    
    stats = {
        'total_restaurants': 0,
        'success': 0,
        'failed': 0,
        'comments_generated': 0,
        'errors': []
    }
    
    try:
        logger.info(f"开始处理笔记: {title[:50]}...")
        
        logger.info("步骤1: AI提取餐厅信息...")
        restaurants = ai_paraphraser.extract_restaurants(title, description)
        
        if not restaurants:
            logger.warning("⚠️  未提取到餐厅信息，跳过该笔记")
            stats['errors'].append("未提取到餐厅信息")
            return stats
        
        stats['total_restaurants'] = len(restaurants)
        logger.info(f"✅ 成功提取到 {len(restaurants)} 个餐厅")
        
        # 步骤2：对每个餐厅进行处理
        for idx, restaurant in enumerate(restaurants, 1):
            restaurant_name = restaurant.get('name', '未知')
            logger.info(f"\n处理餐厅 {idx}/{len(restaurants)}: {restaurant_name}")
            
            try:
                # 2.1 使用高德API搜索餐厅地址（必须使用高德API地址）
                logger.info(f"  使用高德API搜索餐厅地址: {restaurant_name}")
                address_result = address_service.search_restaurant_address(restaurant_name, city)
                
                if not address_result or not address_result.get('address'):
                    logger.warning(f"  ⚠️  高德API未找到地址，跳过该餐厅")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: 高德API未找到地址")
                    continue
                
                # 使用高德API返回的地址、城市和区代码
                restaurant['address'] = address_result['address']
                # 处理城市名称（去掉"市"后缀，如"上海市" -> "上海"）
                city_name = address_result.get('city', city)
                if city_name and city_name.endswith('市'):
                    city_name = city_name[:-1]
                restaurant['city'] = city_name
                restaurant['district'] = address_result.get('district', '')
                restaurant['adcode'] = address_result.get('adcode', '')
                restaurant['province'] = address_result.get('province', '')
                
                logger.info(f"  ✅ 高德API返回地址: {restaurant['address']}")
                logger.info(f"  ✅ 城市: {restaurant['city']}, 区县: {restaurant['district']}, 区代码: {restaurant['adcode']}")
                
                # 2.2 AI转述内容并生成评论（先不插入数据库，等获取tweet_id后再插入）
                logger.info(f"  步骤2: AI转述内容并生成评论...")
                logger.info(f"    原始标题: {title[:50]}...")
                logger.info(f"    原始描述: {description[:100]}...")
                
                paraphrased_title, paraphrased_desc, type_cid, comments = ai_paraphraser.paraphrase_restaurant(
                    restaurant_info=restaurant,
                    original_title=title,
                    original_description=description,  # 传入原始笔记的完整描述
                    tweet_id=None,  # 先不提供tweet_id，等插入推文后再插入评论
                    auto_generate_comments=True  # 自动生成评论
                )
                
                if not paraphrased_title or not paraphrased_desc or not type_cid:
                    logger.error(f"  ❌ AI转述失败")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: 转述失败")
                    continue
                
                logger.info(f"  ✅ AI转述成功")
                logger.info(f"    转述标题: {paraphrased_title[:50]}...")
                logger.info(f"    转述描述: {paraphrased_desc[:100]}...")
                logger.info(f"    类型ID: {type_cid}")
                logger.info(f"    生成评论数: {len(comments)} 条")
                stats['comments_generated'] += len(comments)
                
                # 2.3 准备推文数据
                tweet_data = {
                    'tweets_title': restaurant_name,  # 使用餐厅名字作为标题（不再限制长度）
                    'tweets_content': paraphrased_desc,  # 转述后的描述（不再限制长度）
                    'tweets_describe': restaurant['address'],  # 使用高德API返回的地址（不再限制长度）
                    'tweets_img': images or [],  # 图片列表
                    'tweets_type_pid': 5,  # 美食类型
                    'tweets_type_cid': type_cid,
                    'tweets_user': get_random_username(),
                    'tweets_location': restaurant['city'],  # 使用高德API返回的城市
                    'tweets_location_code': restaurant['adcode'],  # 使用高德API返回的区代码
                    'like_num': random.randint(10, 500),
                    'collect_num': random.randint(5, 100),
                    'browse_num': random.randint(50, 2000)
                }
                
                # 验证并准备数据
                try:
                    prepared_data = prepare_tweet_data(tweet_data)
                except ValueError as e:
                    logger.error(f"  ❌ 数据验证失败: {e}")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: {str(e)}")
                    continue
                
                # 2.4 插入推文到数据库
                logger.info(f"  插入推文到数据库...")
                tweet_id = insert_tweet(prepared_data)
                
                if tweet_id:
                    logger.info(f"  ✅ 推文插入成功，ID: {tweet_id}")
                    
                    # 2.5 插入评论到数据库
                    if comments:
                        inserted_count = ai_paraphraser.insert_comments_to_db(tweet_id, comments)
                        logger.info(f"  ✅ 评论插入成功: {inserted_count}/{len(comments)} 条")
                    
                    stats['success'] += 1
                else:
                    logger.error(f"  ❌ 推文插入失败")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: 推文插入失败")
                    
            except Exception as e:
                logger.error(f"  ❌ 处理餐厅失败: {e}", exc_info=True)
                stats['failed'] += 1
                stats['errors'].append(f"{restaurant_name}: {str(e)}")
        
        return stats
        
    except Exception as e:
        logger.error(f"处理笔记失败: {e}", exc_info=True)
        stats['errors'].append(f"处理笔记失败: {str(e)}")
        return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='爬虫主入口 - 完整流程：爬虫提取 → AI转述内容及评论 → 上传数据库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Trip.com 爬虫模式
  python3 crawler.py --crawl-trip --trip-url "https://hk.trip.com/restaurant/shanghai-2/" --city 上海
  python3 crawler.py --crawl-trip --trip-url "https://hk.trip.com/restaurant/shanghai-2/" --city 上海 --trip-max 10
  
  # 小红书爬虫模式（推荐）
  python3 crawler.py --crawl --keyword "上海美食" --city 上海 --pages 5
  python3 crawler.py --crawl --keyword "北京美食" --city 北京 --pages 3 --limit 10
  
  # 使用位置参数（简化版）
  python3 crawler.py "北京美食" "今天去了xxx餐厅..." --city 北京
  python3 crawler.py "北京美食" --city 北京 --limit 10
  
  # 使用命名参数（完整版）
  python3 crawler.py --title "上海美食推荐" --description "今天去了xxx餐厅..." --city 上海
  
  # 从文件读取笔记（JSON格式）
  python3 crawler.py --file notes.json --city 上海
  
  # 批量处理多条笔记
  python3 crawler.py --file notes.json --city 上海 --limit 10
        """
    )
    
    # 位置参数（可选）
    parser.add_argument('title', nargs='?', type=str, help='笔记标题（位置参数）')
    parser.add_argument('description', nargs='?', type=str, help='笔记描述（位置参数）')
    
    # 命名参数
    parser.add_argument('--title', type=str, dest='title_arg', help='笔记标题（命名参数）')
    parser.add_argument('--description', type=str, dest='description_arg', help='笔记描述（命名参数）')
    parser.add_argument('--city', type=str, default='上海', help='城市名称（默认：上海）')
    parser.add_argument('--images', type=str, nargs='+', help='图片URL列表（空格分隔）')
    parser.add_argument('--file', type=str, help='笔记文件路径（JSON格式，每行一个JSON对象）')
    parser.add_argument('--limit', type=int, help='处理数量限制（仅用于文件模式或单条笔记模式）')
    
    # 小红书爬虫参数
    parser.add_argument('--crawl', action='store_true', help='启用小红书爬虫模式')
    parser.add_argument('--keyword', type=str, help='小红书搜索关键词（爬虫模式）')
    parser.add_argument('--pages', type=int, default=5, help='爬取页数（默认：5）')
    parser.add_argument('--headless', action='store_true', help='无头模式（不显示浏览器窗口）')
    
    # Trip.com 爬虫参数
    parser.add_argument('--crawl-trip', action='store_true', help='启用 Trip.com 爬虫模式')
    parser.add_argument('--trip-url', type=str, help='Trip.com 餐厅列表页面URL（如：https://hk.trip.com/restaurant/shanghai-2/）')
    parser.add_argument('--trip-pages', type=int, default=1, help='Trip.com 爬取页数（默认：1）')
    parser.add_argument('--trip-max', type=int, help='Trip.com 最大爬取餐厅数量')
    
    args = parser.parse_args()
    
    # 处理位置参数和命名参数的优先级
    title = args.title_arg or args.title
    description = args.description_arg or args.description
    
    try:
        total_stats = {
            'total_notes': 0,
            'total_restaurants': 0,
            'total_success': 0,
            'total_failed': 0,
            'total_comments': 0,
            'all_errors': []
        }
        
        # 启动内存监控（静默监控，不输出日志）
        memory_monitor = MemoryMonitor()
        memory_monitor.start_monitoring()
        
        if args.crawl_trip:
            # Trip.com 爬虫模式
            if not args.trip_url:
                logger.error("Trip.com 爬虫模式需要指定 --trip-url 参数")
                parser.print_help()
                sys.exit(1)
            
            logger.info("Trip.com 爬虫模式")
            
            # 导入 Trip.com 爬虫
            from app.scripts.crawl_trip_com import crawl_trip_com_restaurants
            
            # 爬取餐厅列表
            logger.info("开始爬取 Trip.com 餐厅...")
            restaurants = crawl_trip_com_restaurants(
                url=args.trip_url,
                pages=args.trip_pages,
                headless=args.headless,
                max_restaurants=args.trip_max or args.limit
            )
            
            if not restaurants:
                logger.warning("未爬取到任何餐厅")
                sys.exit(1)
            
            logger.info(f"成功爬取 {len(restaurants)} 个餐厅，开始处理...")
            
            # 处理每个餐厅
            for idx, restaurant in enumerate(restaurants, 1):
                logger.info(f"\n处理餐厅 {idx}/{len(restaurants)}: {restaurant.get('name', '未知')}")
                
                # 限制处理数量
                if args.limit and idx > args.limit:
                    break
                
                # 处理餐厅（转述、上传）
                stats = process_restaurant(restaurant, city=args.city)
                
                total_stats['total_notes'] += 1
                total_stats['total_restaurants'] += stats['total_restaurants']
                total_stats['total_success'] += stats['success']
                total_stats['total_failed'] += stats['failed']
                total_stats['total_comments'] += stats['comments_generated']
                total_stats['all_errors'].extend(stats['errors'])
        
        elif args.crawl:
            # 小红书爬虫模式
            if not args.keyword:
                logger.error("爬虫模式需要指定 --keyword 参数")
                parser.print_help()
                sys.exit(1)
            
            logger.info("小红书爬虫模式")
            
            # 爬取并逐条处理笔记：爬取一条 → 立即处理（提取餐厅 → AI转述 → 上传）
            logger.info("开始爬取并逐条处理笔记...")
            
            # 修改crawl_xiaohongshu为生成器模式，逐条返回笔记
            note_count = 0
            for note in crawl_xiaohongshu_generator(
                keyword=args.keyword,
                pages=args.pages,
                headless=args.headless
            ):
                # 限制处理数量
                if args.limit and note_count >= args.limit:
                    break
                
                note_count += 1
                logger.info(f"\n处理笔记 {note_count}: {note.get('title', '')[:50]}...")
                
                title = note.get('title', '')
                description = note.get('description', '')
                images = note.get('images', [])
                city = args.city
                
                if not title or not description:
                    logger.warning(f"笔记 {note_count} 缺少标题或描述，跳过")
                    continue
                
                # 立即处理这条笔记（包含提取、转述、上传的完整流程）
                stats = process_note(title, description, city, images)
                
                total_stats['total_notes'] += 1
                total_stats['total_restaurants'] += stats['total_restaurants']
                total_stats['total_success'] += stats['success']
                total_stats['total_failed'] += stats['failed']
                total_stats['total_comments'] += stats['comments_generated']
                total_stats['all_errors'].extend(stats['errors'])
            
            if note_count == 0:
                logger.warning("未爬取到任何笔记")
                sys.exit(1)
        
        elif args.file:
            # 从文件读取笔记
            import json
            
            logger.info(f"从文件读取笔记: {args.file}")
            
            notes = []
            with open(args.file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        note = json.loads(line)
                        notes.append(note)
                    except json.JSONDecodeError as e:
                        logger.warning(f"第 {line_num} 行JSON解析失败: {e}")
                        continue
            
            if args.limit:
                notes = notes[:args.limit]
            
            logger.info(f"共读取 {len(notes)} 条笔记")
            
            # 处理每条笔记
            for idx, note in enumerate(notes, 1):
                logger.info(f"\n处理笔记 {idx}/{len(notes)}")
                
                title = note.get('title', note.get('tweets_title', ''))
                description = note.get('description', note.get('tweets_content', note.get('content', '')))
                city = note.get('city', note.get('tweets_location', args.city))
                images = note.get('images', note.get('tweets_img', []))
                
                if isinstance(images, str):
                    # 如果是JSON字符串，解析它
                    try:
                        images = json.loads(images)
                    except:
                        images = [images]
                
                if not title or not description:
                    logger.warning(f"笔记 {idx} 缺少标题或描述，跳过")
                    continue
                
                stats = process_note(title, description, city, images)
                
                total_stats['total_notes'] += 1
                total_stats['total_restaurants'] += stats['total_restaurants']
                total_stats['total_success'] += stats['success']
                total_stats['total_failed'] += stats['failed']
                total_stats['total_comments'] += stats['comments_generated']
                total_stats['all_errors'].extend(stats['errors'])
        
        elif title:
            # 处理单条笔记（使用位置参数或命名参数）
            # 如果没有描述，使用标题作为描述
            if not description:
                description = title
                logger.info("未提供描述，使用标题作为描述")
            
            images = args.images or []
            
            # 如果指定了limit，只处理第一个餐厅（如果有多个）
            # 注意：这里limit的含义是限制处理的餐厅数量，而不是笔记数量
            stats = process_note(title, description, args.city, images)
            
            # 如果指定了limit，限制处理的餐厅数量
            if args.limit and stats['total_restaurants'] > args.limit:
                logger.info(f"限制处理数量为 {args.limit} 个餐厅")
                # 注意：process_note内部已经处理了所有餐厅，这里只是记录
            
            total_stats['total_notes'] = 1
            total_stats['total_restaurants'] = stats['total_restaurants']
            total_stats['total_success'] = stats['success']
            total_stats['total_failed'] = stats['failed']
            total_stats['total_comments'] = stats['comments_generated']
            total_stats['all_errors'] = stats['errors']
        
        else:
            parser.print_help()
            sys.exit(1)
        
        # 打印最终统计
        logger.info("\n处理完成！统计信息：")
        logger.info(f"处理笔记数: {total_stats['total_notes']}")
        logger.info(f"提取餐厅数: {total_stats['total_restaurants']}")
        logger.info(f"成功插入: {total_stats['total_success']}")
        logger.info(f"失败数量: {total_stats['total_failed']}")
        logger.info(f"生成评论数: {total_stats['total_comments']}")
        
        if total_stats['all_errors']:
            logger.warning(f"\n错误列表（共 {len(total_stats['all_errors'])} 个）:")
            for error in total_stats['all_errors'][:10]:  # 只显示前10个错误
                logger.warning(f"  - {error}")
            if len(total_stats['all_errors']) > 10:
                logger.warning(f"  ... 还有 {len(total_stats['all_errors']) - 10} 个错误未显示")
        
        # 停止内存监控
        try:
            memory_monitor.stop_monitoring()
        except:
            pass
        
    except KeyboardInterrupt:
        logger.info("\n\n程序被用户中断 (Ctrl+C)")
        # 清理所有Chrome进程
        try:
            from base.browser_cleanup import cleanup_drissionpage_processes
            cleanup_drissionpage_processes()
        except:
            pass
        try:
            memory_monitor.stop_monitoring()
        except:
            pass
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n程序执行出错: {e}", exc_info=True)
        # 清理所有Chrome进程
        try:
            from base.browser_cleanup import cleanup_drissionpage_processes
            cleanup_drissionpage_processes()
        except:
            pass
        try:
            memory_monitor.stop_monitoring()
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()

