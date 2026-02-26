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
import time
import requests
from typing import List, Dict, Optional

# 修复 Windows 控制台乱码
if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_service import get_ai_paraphraser
from app.services.address_service import AddressService
from app.services.tweet_service import prepare_tweet_data, insert_tweet
from app.services.tripcom_service import crawl_tripcom_restaurants
from app.utils.tripcom_tag_mapper import map_tripcom_tags_to_cids
from app.utils.category_utils import get_cuisine_type_cid
from base.utils import get_random_username
from base.monitors import MemoryMonitor
from base.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _launch_browser(headless: bool = False, config: Optional['Config'] = None):
    """启动Chromium浏览器，返回(page, random_port, config)"""
    try:
        from DrissionPage._pages.chromium_page import ChromiumPage
        from DrissionPage import ChromiumOptions
    except ImportError:
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            logger.error("无法导入ChromiumPage，请确保已安装DrissionPage: pip install DrissionPage")
            raise

    import random as random_module

    if config is None:
        config = Config()

    options = ChromiumOptions()
    random_port = random_module.randint(9223, 9999)
    options.set_address(f'127.0.0.1:{random_port}')
    options.set_argument(f'--remote-debugging-port={random_port}')
    logger.info(f"使用调试端口: {random_port}")

    project_root = os.path.dirname(os.path.abspath(__file__))
    user_data_dir = os.path.join(project_root, 'chrome_user_data')
    os.makedirs(user_data_dir, exist_ok=True)
    try:
        options.set_user_data_path(user_data_dir)
        logger.info(f"使用用户数据目录: {user_data_dir}（保持登录状态）")
    except Exception as e:
        logger.warning(f"设置用户数据目录失败: {e}，将使用临时会话")

    options.set_argument(f'--window-size={config.WINDOW_WIDTH},{config.WINDOW_HEIGHT}')
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-blink-features=AutomationControlled')
    options.set_argument('--disable-dev-shm-usage')

    if headless:
        options.headless(True)

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

    user_agent = random.choice(config.USER_AGENTS)
    headers = config.DEFAULT_HEADERS.copy()
    headers['User-Agent'] = user_agent

    try:
        page.set.headers(headers)
        page.set.window.size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        logger.info("✅ 浏览器参数已配置")
    except Exception as e:
        logger.warning(f"设置浏览器参数失败: {e}，继续使用默认配置")

    return page, random_port, config


def _close_browser(page, random_port: Optional[int] = None):
    """安全关闭浏览器"""
    if not page:
        return
    try:
        logger.info("正在关闭浏览器...")
        from base.browser_cleanup import safe_close_browser, cleanup_chrome_processes
        safe_close_browser(page, random_port)
        logger.info("✅ 浏览器已关闭，端口已清理")
    except Exception as e:
        logger.warning(f"关闭浏览器时出错: {e}")
        if random_port:
            try:
                cleanup_chrome_processes(random_port)
            except Exception:
                pass


def _extract_arg_value(args_list: List[str], flag: str) -> Optional[str]:
    """从命令参数列表中提取指定flag的值"""
    if not args_list:
        return None
    for idx, arg in enumerate(args_list):
        if arg == flag and idx + 1 < len(args_list):
            return args_list[idx + 1]
    return None


def _safe_int(value: Optional[str], default: Optional[int] = None) -> Optional[int]:
    """安全地将值转换为int"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_task_entry(task: Dict, default_city: str, default_pages: int) -> Optional[Dict]:
    """标准化任务配置"""
    keyword = task.get('keyword')
    city = task.get('city', default_city)
    pages = task.get('pages')
    limit = task.get('limit')

    if not keyword and isinstance(task.get('args'), list):
        args_list = task['args']
        keyword = _extract_arg_value(args_list, '--keyword')
        city = _extract_arg_value(args_list, '--city') or city
        pages = pages or _extract_arg_value(args_list, '--pages')
        limit = limit or _extract_arg_value(args_list, '--limit')

    if not keyword:
        return None

    pages = _safe_int(pages, default_pages)
    limit = _safe_int(limit)

    return {
        'keyword': keyword,
        'city': city or default_city,
        'pages': pages or default_pages,
        'limit': limit
    }


def load_batch_tasks(config_path: str, default_city: str, default_pages: int) -> List[Dict]:
    """加载批量任务配置"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"任务文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict) and 'tasks' in data:
        raw_tasks = data['tasks']
    elif isinstance(data, list):
        raw_tasks = data
    else:
        raise ValueError("任务文件格式不正确，需为列表或包含 tasks 字段的字典")

    tasks = []
    for idx, task in enumerate(raw_tasks, 1):
        if not isinstance(task, dict):
            logger.warning(f"任务 {idx} 格式无效，已跳过")
            continue
        normalized = _normalize_task_entry(task, default_city, default_pages)
        if not normalized:
            logger.warning(f"任务 {idx} 缺少关键词，已跳过")
            continue
        tasks.append(normalized)

    return tasks


def crawl_xiaohongshu_generator(keyword: str, pages: int = 5, headless: bool = False,
                                page=None, config: Optional['Config'] = None):
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
        
        owns_browser = page is None
        random_port = None
        if owns_browser:
            page, random_port, config = _launch_browser(headless=headless, config=config)
        elif config is None:
            config = Config()
        
        logger.info(f"开始爬取小红书: 关键词={keyword}, 页数={pages}")
        
        def _is_logged_in():
            """检测当前浏览器是否已登录小红书"""
            try:
                cookies = page.cookies()
                has_auth_cookie = any(
                    isinstance(cookie, dict) and any(
                        key in str(cookie.get('name', '')).lower()
                        for key in ['a1', 'web_session', 'webid', 'web_sessionid']
                    )
                    for cookie in cookies
                )
                current_url = (page.url or '').lower()
                is_login_page = any(keyword in current_url for keyword in ['login', 'passport'])
                
                # 只要不是登录页且页面可正常加载，就认为已登录，避免误报
                if not is_login_page:
                    return True
                
                # 登录页情况下仍允许通过 cookie 判断
                return has_auth_cookie and not is_login_page
            except Exception as e:
                logger.debug(f"登录状态检查异常: {e}")
                return False
        
        try:
            # 登录检测
            logger.info("正在检查登录状态...")
            page.get('https://www.xiaohongshu.com')
            page.wait.doc_loaded()
            time.sleep(3)
            
            if not _is_logged_in():
                logger.info("⚠️  未检测到登录状态，请扫码登录小红书...")
                if sys.stdin is not None and sys.stdin.isatty():
                    try:
                        input('登录完成后按回车继续...')
                    except EOFError:
                        logger.info("检测到非交互式环境，等待30秒以完成登录...")
                        time.sleep(30)
                else:
                    logger.info("非交互式环境，等待30秒以完成登录...")
                    time.sleep(30)
                
                # 再次加载主页并验证
                page.get('https://www.xiaohongshu.com')
                page.wait.doc_loaded()
                time.sleep(2)
                
                if not _is_logged_in():
                    logger.error("未检测到登录状态，请确认已成功登录小红书")
                    raise RuntimeError("小红书未登录，无法继续爬虫流程")
            
            # 搜索笔记
            encoded_keyword = quote(keyword)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_explore_feed"
            
            logger.info(f"正在访问搜索页面: {search_url}")
            page.get(search_url)
            page.wait.doc_loaded()
            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
            
            consecutive_failures = 0  # 连续失败计数
            max_consecutive_failures = 2  # 最多连续失败2页后跳过当前城市
            
            # 第一阶段：先收集所有笔记ID
            all_note_ids = []  # 存储所有笔记ID和token
            logger.info("=" * 60)
            logger.info("第一阶段：批量收集所有笔记ID")
            logger.info("=" * 60)
            
            for page_num in range(pages):
                logger.info(f"正在爬取第 {page_num + 1} 页")
                
                # 如果不是第一页，先滚动到页面顶部，然后等待一下
                if page_num > 0:
                    logger.info("滚动到页面顶部...")
                    page.run_js("window.scrollTo(0, 0)")
                    time.sleep(random.uniform(2, 4))
                    
                    # 如果上一页失败，尝试刷新页面
                    if page_num > 1:
                        logger.info("重新加载搜索页面以确保状态正常...")
                        page.get(search_url)
                        page.wait.doc_loaded()
                        time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
                
                # 使用固定的API端点
                api_url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
                
                # 重试机制：如果没有响应，重复滚动和等待，最多重试MAX_API_RETRIES次
                packet = None
                retry_count = 0
                max_retries = config.MAX_API_RETRIES
                
                while retry_count < max_retries:
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
                        logger.info(f"已启动API监听（第 {page_num + 1} 页，重试第 {retry_count}/{max_retries} 次）")
                        # 第2次重试时刷新页面
                        if retry_count == 2:
                            logger.info("第2次重试失败，刷新页面...")
                            page.get(search_url)
                            page.wait.doc_loaded()
                            time.sleep(random.uniform(config.DELAY_MIN, config.DELAY_MAX))
                        # 第3次重试时，滚动到顶部
                        elif retry_count > 2:
                            logger.info("多次重试失败，尝试滚动到顶部重新开始...")
                            page.run_js("window.scrollTo(0, 0)")
                            time.sleep(2)
                    
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
                    
                    # 如果没有捕获到且未达到最大重试次数，等待一段时间后重试
                    if retry_count < max_retries:
                        wait_time = min(retry_count * 3, 15)  # 等待时间递增，最多15秒
                        logger.warning(f"未捕获到响应，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ 达到最大重试次数（{max_retries}次），跳过第 {page_num + 1} 页")
                        consecutive_failures += 1
                        if consecutive_failures >= max_consecutive_failures:
                            logger.warning(f"⚠️  连续 {consecutive_failures} 页失败，可能触发反爬虫限制，跳过当前城市")
                            break
                        break
                
                # 处理响应
                try:
                    if packet and packet.response:
                        consecutive_failures = 0  # 成功时重置失败计数
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
                                    # 先收集所有笔记ID，不立即访问详情页
                                    page_note_ids = []
                                    for idx, item in enumerate(items, 1):
                                        note_id = item.get("id")
                                        xsec_token = item.get("xsec_token")
                                        
                                        if note_id and xsec_token:
                                            # 只收集note_id和xsec_token，暂不访问详情页
                                            page_note_ids.append({
                                                'note_id': note_id,
                                                'xsec_token': xsec_token,
                                                'url': f"https://www.xiaohongshu.com/explore/{note_id}"
                                            })
                                    
                                    all_note_ids.extend(page_note_ids)
                                    logger.info(f"第 {page_num + 1} 页共收集 {len(page_note_ids)} 个笔记ID，累计 {len(all_note_ids)} 个")
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
            
            # 第二阶段：逐个访问详情页，获取完整内容
            logger.info("=" * 60)
            logger.info(f"第二阶段：开始访问详情页，共 {len(all_note_ids)} 个笔记")
            logger.info("=" * 60)
            
            for idx, note_info in enumerate(all_note_ids, 1):
                note_id = note_info['note_id']
                xsec_token = note_info['xsec_token']
                note_url = note_info['url']
                
                logger.info(f"正在访问笔记 {idx}/{len(all_note_ids)}: {note_id}")
                
                try:
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
                            'url': note_url,
                            'note_id': note_id
                        }
                        
                        logger.info(f"✅ 爬取到笔记: {title[:50]}...")
                        # yield返回完整笔记数据
                        yield note
                    else:
                        logger.warning(f"笔记 {idx} 缺少标题，跳过")
                        
                except Exception as e:
                    logger.warning(f"访问笔记详情失败: {e}")
                    continue
                
        finally:
            if owns_browser:
                _close_browser(page, random_port)
                
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
                
                # 重试机制：如果没有响应，重复滚动和等待，最多重试MAX_API_RETRIES次
                packet = None
                retry_count = 0
                max_retries = config.MAX_API_RETRIES
                
                while retry_count < max_retries:
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
                        logger.info(f"已启动API监听（第 {page_num + 1} 页，重试第 {retry_count}/{max_retries} 次）")
                    
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
                    
                    # 如果没有捕获到且未达到最大重试次数，等待一段时间后重试
                    if retry_count < max_retries:
                        wait_time = min(retry_count * 3, 15)  # 等待时间递增，最多15秒
                        logger.warning(f"未捕获到响应，{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ 达到最大重试次数（{max_retries}次），跳过第 {page_num + 1} 页")
                        break
                
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
            # 关闭浏览器（如果是由这个函数启动的）
            try:
                if page:
                    _close_browser(page, random_port)
            except:
                pass
                
    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.error("请确保已安装 DrissionPage: pip install DrissionPage")
        return []
    except Exception as e:
        logger.error(f"爬取小红书失败: {e}", exc_info=True)
        return []


def process_tripcom_restaurant(restaurant_name: str, description: str, city: str = "上海",
                               images: List[str] = None, cuisine_type: str = "", 
                               rating: Optional[float] = None, tags: Dict = None,
                               tripcom_address: str = "", comments: List[Dict] = None,
                               price_range: str = "", review_count: Optional[int] = None) -> Dict:
    """
    处理 Trip.com 餐厅数据：默认基于 Trip.com 评分/评价做小红书风格改写（模型不可用时自动回退到旧逻辑）
    
    Args:
        restaurant_name: 餐厅名称
        description: 餐厅描述
        city: 城市名称（用于地址搜索）
        images: 图片列表（可选）
        cuisine_type: 菜系类型（可选）
        rating: 评分（可选）
        tags: 标签（可选）
        tripcom_address: Trip.com抓取的原始地址（可选）
        comments: 评论列表（可选），每个评论是包含 'content' 的字典
        review_count: Trip.com评价数（可选）
        
    Returns:
        处理结果统计字典
    """
    address_service = AddressService()
    
    stats = {
        'total_restaurants': 1,
        'success': 0,
        'failed': 0,
        'comments_generated': 0,
        'errors': []
    }
    
    try:
        logger.info(f"开始处理餐厅: {restaurant_name}")
        
        # 1. 获取地址
        # 策略：优先使用高德API，如果失败则使用Trip.com原有的地址（已转简体）
        logger.info(f"使用高德API搜索餐厅地址: {restaurant_name}")
        address = ""
        
        # 初始化城市和区域信息
        city_name = city
        district = ""
        adcode = ""
        
        try:
            # 构造搜索关键词：城市 + 餐厅名
            search_keyword = f"{city} {restaurant_name}"
            address_info = address_service.search_restaurant_address(search_keyword, city)
            
            if address_info and address_info.get('address'):
                address = address_info['address']
                city_name = address_info.get('city', city)
                if city_name and city_name.endswith('市'):
                    city_name = city_name[:-1]
                district = address_info.get('district', '')
                adcode = address_info.get('adcode', '')
                
                logger.info(f"✅ 高德API找到地址: {address}")
                logger.info(f"✅ 城市: {city_name}, 区县: {district}, 区代码: {adcode}")
            else:
                logger.warning(f"⚠️  高德API未找到地址: {restaurant_name}")
                
                # 回退使用 Trip.com 原有地址
                if tripcom_address and len(tripcom_address) > 2:
                    # 尝试对Trip.com地址进行地理编码获取adcode
                    logger.info(f"⚠️  尝试使用Trip.com地址进行地理编码: {tripcom_address}")
                    geo_result = address_service.geocode_address(tripcom_address, city)
                    
                    if geo_result and geo_result.get('address'):
                        address = geo_result['address']
                        city_name = geo_result.get('city', city)
                        if city_name and city_name.endswith('市'):
                            city_name = city_name[:-1]
                        district = geo_result.get('district', '')
                        adcode = geo_result.get('adcode', '')
                        logger.info(f"✅ Trip.com地址地理编码成功: {address} (adcode: {adcode})")
                    else:
                        address = tripcom_address
                        logger.info(f"✅ 使用Trip.com详情页地址（兜底）: {address}")
                        
                        # 尝试从地址中提取区县信息
                        if '区' in address:
                            try:
                                import re
                                district_match = re.search(r'([\u4e00-\u9fa5]{2,5}区)', address)
                                if district_match:
                                    district_candidate = district_match.group(1)
                                    if address.index(district_candidate) < 10:
                                        # 这里只更新city_name用于显示，但不更新adcode因为不知道
                                        # city_name = f"{city}·{district_candidate}" # 这种格式可能不符合新的city字段要求
                                        # 保持原样或仅记录
                                        district = district_candidate
                                        logger.info(f"✅ 从地址提取所属地区: {district}")
                            except:
                                pass
                else:
                    # 如果都没有，不跳过，使用默认值
                    logger.warning(f"❌ 无法获取地址（高德API和Trip.com均无），将使用默认地址")
                    address = "地址未知"
                
        except Exception as e:
            logger.warning(f"高德API搜索失败: {e}")
            # 发生异常时也尝试使用 Trip.com 原有地址
            if tripcom_address and len(tripcom_address) > 2:
                address = tripcom_address
                logger.info(f"✅ 使用Trip.com详情页地址（异常兜底）: {address}")
                
                # 尝试从地址中提取区县信息
                if '区' in address:
                    try:
                        import re
                        district_match = re.search(r'([\u4e00-\u9fa5]{2,5}区)', address)
                        if district_match:
                            district_candidate = district_match.group(1)
                            if address.index(district_candidate) < 10:
                                city_name = f"{city}·{district_candidate}"
                                logger.info(f"✅ 从地址提取所属地区: {city_name}")
                    except:
                        pass
            else:
                # 如果都没有，不跳过，使用默认值
                address = "地址未知"
        
        # 确定类型ID（根据菜系类型）
        from app.services.ai_service import get_ai_paraphraser
        from app.utils.tripcom_tag_mapper import map_tripcom_tags_to_cids
        
        ai_paraphraser = get_ai_paraphraser()
        
        # 构建餐厅信息用于类型判断
        restaurant_info = {
            'name': restaurant_name,
            'description': description,
            'cuisine_type': cuisine_type
        }
        type_pid = ai_paraphraser.get_parent_type_id(restaurant_info)
        
        # 使用标签映射分类（如果提供了标签）
        if tags:
            type_cid = map_tripcom_tags_to_cids(
                cuisine_tags=tags.get('cuisine', []),
                price_tags=tags.get('price', []),
                meal_tags=tags.get('meal', []),
                feature_tags=tags.get('feature', []),
                special_tags=tags.get('special', []),
                restaurant_name=restaurant_name,
                description=description
            )
            logger.info(f"使用标签映射分类: {type_cid}")
            logger.info(f"  标签: 菜系={tags.get('cuisine', [])}, 价格={tags.get('price', [])}, 用餐={tags.get('meal', [])}, 特色={tags.get('feature', [])}, 特殊={tags.get('special', [])}")
        else:
            # 如果没有标签，使用原来的方法
            type_cid = get_cuisine_type_cid(cuisine_type, description, restaurant_name)
            logger.info(f"菜系类型: {cuisine_type}, 分类ID: {type_cid}")
        
        # 处理图片：如果有图片URL则使用，否则使用占位图（数据库要求必须有图片）
        image_list = []
        if images:
            # 过滤有效的图片URL
            for img_url in images:
                if img_url and isinstance(img_url, str) and img_url.startswith('http'):
                    image_list.append(img_url)
            logger.info(f"找到 {len(image_list)} 张有效图片")
        
        # 如果没有图片，使用占位图（数据库要求必须有图片）
        if not image_list:
            logger.info("未找到图片，将使用占位图")
            image_list = ['https://via.placeholder.com/400x300?text=Restaurant']
        
        # 处理评论：清洗 Trip.com 评论，供改写与兜底拼接使用
        content_parts = []
        
        # 注意：价格标识不添加到内容中，而是更新到 tweets_type_cid（二级类目）
        # 价格标识会在 process_tripcom_restaurant 函数中通过 tags 参数传递，
        # 并在 map_tripcom_tags_to_cids 函数中映射到分类ID
        
        if description:
            content_parts.append(description)
        
        tripcom_review_texts: List[str] = []
        if comments:
            logger.info(f"处理 {len(comments)} 条评论...")
            import re
            comment_texts = []
            for comment in comments:
                comment_content = comment.get('content', '')
                if comment_content and len(comment_content.strip()) > 5:
                    # 清理评论内容
                    cleaned_content = comment_content.strip()
                    
                    # 按行分割，逐行清理
                    lines = cleaned_content.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 跳过标题行（如：在渝里·重庆火锅（解放碑好吃街店）的评价）
                        if re.search(r'的评价$|的评价\s*$', line):
                            continue
                        if re.search(r'^在.*的评价', line):
                            continue
                        
                        # 跳过提示文本（如：部分评论可能已透过 Google Translate）
                        if re.search(r'部分评论可能已透过|Google Translate|可能已透过.*翻译', line, re.IGNORECASE):
                            continue
                        if re.search(r'^部分.*翻译', line):
                            continue
                        
                        # 跳过日期行（如：评价日期 2023年12月3日、2019年6月3日）
                        if re.search(r'评价日期|^\d{4}年\d{1,2}月\d{1,2}日|^\d{4}-\d{1,2}-\d{1,2}', line):
                            continue
                        
                        # 跳过评分行（如：4.0/5极好、5.0/5完美、4.5/5 非常好）
                        if re.search(r'^\d+\.?\d*\s*/\s*5', line):
                            continue
                        
                        # 跳过只包含评分词汇的行（如：极好、完美、非常好）
                        if re.match(r'^(极好|完美|非常好|优秀|良好|一般|差|很差)$', line):
                            continue
                        
                        # 跳过用户名行（如：ScorpioF、annakeanu、_We***81、M61***33）
                        if re.match(r'^[A-Za-z0-9_*]+$', line) and len(line) < 20:
                            continue
                        
                        # 跳过只包含特殊字符的行（如：•、·等）
                        if re.match(r'^[•·▪▫\s]+$', line):
                            continue
                        
                        # 移除行内的日期模式
                        line = re.sub(r'评价日期\s*\d{4}年\d{1,2}月\d{1,2}日', '', line)
                        line = re.sub(r'\d{4}年\d{1,2}月\d{1,2}日', '', line)
                        line = re.sub(r'\d{4}-\d{1,2}-\d{1,2}', '', line)
                        
                        # 移除行内的评分模式
                        line = re.sub(r'\d+\.?\d*\s*/\s*5\s*[^\s]*', '', line)
                        line = re.sub(r'\d+\.?\d*\s*/\s*5', '', line)
                        
                        # 移除"原文"、"翻译"等标记
                        line = re.sub(r'原文\s*', '', line)
                        line = re.sub(r'翻译\s*', '', line)
                        
                        # 移除评分相关词汇
                        line = re.sub(r'\s*(极好|完美|非常好|优秀|良好|一般|差|很差)\s*', '', line)
                        
                        # 移除以特殊字符开头的行
                        line = re.sub(r'^[•·▪▫]\s*', '', line)
                        
                        # 移除用户名模式（行首）
                        line = re.sub(r'^[A-Za-z0-9_*]+\s+\d+\.?\d*/\d+', '', line)
                        line = re.sub(r'^[A-Za-z][A-Za-z0-9_*]+\s+', '', line)
                        
                        line = line.strip()
                        
                        # 只保留有实际内容的行
                        if line and len(line) > 5:
                            cleaned_lines.append(line)
                    
                    # 合并清理后的行
                    if cleaned_lines:
                        cleaned_content = '\n'.join(cleaned_lines)
                        # 移除多余的空格
                        cleaned_content = re.sub(r' +', ' ', cleaned_content)
                        cleaned_content = cleaned_content.strip()
                        
                        # 只保留有实际内容的评论
                        if cleaned_content and len(cleaned_content) > 10:
                            comment_texts.append(cleaned_content)
            
            if comment_texts:
                tripcom_review_texts = comment_texts
                logger.info(f"✅ 清洗得到 {len(tripcom_review_texts)} 条可用Trip.com评价摘录")
        
        # === 优先：基于 Trip.com 评分 + 评价摘录做小红书风格改写（可配置关闭） ===
        from base.config import Config
        rewritten_title = None
        rewritten_desc = None
        try:
            if getattr(Config, "TRIPCOM_AI_REWRITE", True):
                rewritten_title, rewritten_desc = ai_paraphraser.paraphrase_tripcom_restaurant_note(
                    restaurant_name=restaurant_name,
                    restaurant_desc=description or "",
                    tripcom_rating=rating,
                    tripcom_review_count=review_count,
                    tripcom_reviews=tripcom_review_texts,
                    include_score_line=False,
                    include_address_line=False,
                    address_text=""
                )
        except Exception as e:
            logger.warning(f"Trip.com改写失败，将回退到原始拼接内容: {e}")

        # 兜底：沿用旧逻辑（描述 + 评论拼接）
        if description:
            content_parts.append(description)
        if tripcom_review_texts:
            content_parts.append('\n'.join(tripcom_review_texts))

        # 标题保持为餐厅名（用户要求标题不变）
        final_content = rewritten_desc if rewritten_desc else ('\n'.join(content_parts) if content_parts else restaurant_name)
        final_title = restaurant_name
        
        # 限制内容长度（数据库字段可能有长度限制，通常为2000字符）
        max_content_length = 2000
        if len(final_content) > max_content_length:
            original_length = len(final_content)
            final_content = final_content[:max_content_length] + '...'
            logger.warning(f"⚠️ 内容过长，已截断（原始长度: {original_length} 字符）")
        
        # 准备推文数据
        tweet_data = {
            'tweets_title': final_title,
            'tweets_content': final_content,  # 包含描述和评论
            'tweets_describe': address,  # 使用高德API返回的地址
            'tweets_img': image_list,  # 如果有图片则使用，否则使用占位图
            'tweets_type_pid': type_pid,
            'tweets_type_cid': type_cid,
            'tweets_user': get_random_username(),
            'tweets_location': city_name,
            'tweets_location_code': adcode,
            'like_num': random.randint(10, 500),
            'collect_num': random.randint(5, 100),
            'browse_num': random.randint(50, 2000)
        }
        
        # 验证并准备数据
        try:
            prepared_data = prepare_tweet_data(tweet_data)
        except ValueError as e:
            logger.error(f"❌ 数据验证失败: {e}")
            stats['failed'] += 1
            stats['errors'].append(f"{restaurant_name}: {str(e)}")
            return stats
        
        # 插入推文到数据库（不生成评论）
        logger.info(f"插入推文到数据库...")
        tweet_id = insert_tweet(prepared_data)
        
        if tweet_id:
            logger.info(f"✅ 推文插入成功，ID: {tweet_id}")
            stats['success'] += 1
        else:
            logger.error(f"❌ 推文插入失败")
            stats['failed'] += 1
            stats['errors'].append(f"{restaurant_name}: 推文插入失败")
        
        return stats
        
    except Exception as e:
        logger.error(f"处理餐厅失败: {e}", exc_info=True)
        stats['failed'] += 1
        stats['errors'].append(f"{restaurant_name}: {str(e)}")
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
        
        logger.info("步骤1: AI提取场所信息...")
        restaurants = ai_paraphraser.extract_restaurants(title, description)
        
        if not restaurants:
            logger.warning("⚠️  未提取到餐厅信息，跳过该笔记")
            logger.warning(f"   提示：如果笔记包含多家餐厅，请检查AI是否完整提取了所有餐厅")
            stats['errors'].append("未提取到餐厅信息")
            return stats
        
        stats['total_restaurants'] = len(restaurants)
        logger.info(f"✅ 成功提取到 {len(restaurants)} 个餐厅，将逐个处理并上传")
        
        # 步骤2：对每个餐厅进行处理
        for idx, restaurant in enumerate(restaurants, 1):
            restaurant_name = restaurant.get('name', '未知')
            logger.info(f"\n处理餐厅 {idx}/{len(restaurants)}: {restaurant_name}")
            
            try:
                # 2.1 使用高德API搜索餐厅地址（必须使用高德API地址）
                logger.info(f"  使用高德API搜索餐厅地址: {restaurant_name}")
                address_result = address_service.search_restaurant_address(restaurant_name, city)
                
                if not address_result or not address_result.get('address'):
                    # 尝试使用AI提取的地址进行地理编码（Fallback机制）
                    ai_extracted_address = restaurant.get('address', '').strip()
                    if ai_extracted_address and len(ai_extracted_address) > 5:
                        logger.info(f"  ⚠️  高德POI搜索失败，尝试使用AI提取的地址进行地理编码: {ai_extracted_address}")
                        # 只有当地址不包含"未知"、"暂无"等无效词时才尝试
                        invalid_keywords = ['未知', '暂无', '待补充', '待定', 'None', 'null']
                        if not any(k in ai_extracted_address for k in invalid_keywords):
                            address_result = address_service.geocode_address(ai_extracted_address, city)
                    
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
                # 根据场所类型动态选择父类型ID
                type_pid = ai_paraphraser.get_parent_type_id(restaurant)
                
                tweet_data = {
                    'tweets_title': restaurant_name,  # 使用餐厅名字作为标题（不再限制长度）
                    'tweets_content': paraphrased_desc,  # 转述后的描述（不再限制长度）
                    'tweets_describe': restaurant['address'],  # 使用高德API返回的地址（不再限制长度）
                    'tweets_img': images or [],  # 图片列表
                    'tweets_type_pid': type_pid,  # 动态选择父类型ID
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


def run_tasks_file_mode(tasks_file: str,
                        default_city: str,
                        default_pages: int,
                        headless: bool,
                        global_limit: Optional[int],
                        total_stats: Dict):
    """
    批量任务模式：在单个浏览器会话中依次执行多个关键词
    """
    tasks = load_batch_tasks(tasks_file, default_city, default_pages)
    if not tasks:
        logger.error("任务文件中没有有效任务")
        return

    logger.info(f"批量任务模式：共加载 {len(tasks)} 个任务")

    page = None
    random_port = None
    config = None

    try:
        page, random_port, config = _launch_browser(headless=headless)

        import time

        for task_index, task in enumerate(tasks, 1):
            keyword = task['keyword']
            city = task.get('city') or default_city
            pages = task.get('pages', default_pages)
            task_limit = task.get('limit')
            if task_limit is None:
                task_limit = global_limit

            logger.info("\n" + "=" * 60)
            logger.info(f"执行任务 {task_index}/{len(tasks)}: 关键词={keyword}, 城市={city}, 页数={pages}")
            if task_limit:
                logger.info(f"本任务最多处理 {task_limit} 条笔记")
            logger.info("=" * 60)

            note_count = 0
            for note in crawl_xiaohongshu_generator(
                keyword=keyword,
                pages=pages,
                headless=headless,
                page=page,
                config=config
            ):
                if task_limit and note_count >= task_limit:
                    break

                note_count += 1
                logger.info(f"\n处理笔记 {note_count}: {note.get('title', '')[:50]}...")

                title = note.get('title', '')
                description = note.get('description', '')
                images = note.get('images', [])

                if not title or not description:
                    logger.warning(f"笔记 {note_count} 缺少标题或描述，跳过")
                    continue

                stats = process_note(title, description, city, images)

                total_stats['total_notes'] += 1
                total_stats['total_restaurants'] += stats['total_restaurants']
                total_stats['total_success'] += stats['success']
                total_stats['total_failed'] += stats['failed']
                total_stats['total_comments'] += stats['comments_generated']
                total_stats['all_errors'].extend(stats['errors'])

            if note_count == 0:
                logger.warning(f"任务 {task_index} 未爬取到任何笔记")

            # 任务间延迟
            if task_index < len(tasks):
                delay = random.uniform(config.PAGE_DELAY_MIN, config.PAGE_DELAY_MAX)
                logger.info(f"等待 {delay:.1f} 秒后执行下一个任务...")
                time.sleep(delay)

    finally:
        _close_browser(page, random_port)


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
  
  # Trip.com 爬虫模式
  python3 crawler.py --tripcom-url "https://hk.trip.com/restaurant/chongqing-158/?locale=zh-hk&curr=HKD" --city 重庆 --pages 1
  python3 crawler.py --tripcom-url "https://hk.trip.com/restaurant/chongqing-158/?locale=zh-hk&curr=HKD" --city 重庆 --pages 2 --limit 10
  
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
    parser.add_argument('--tasks-file', type=str, help='批量任务文件（JSON格式，在同一浏览器中依次执行关键词）')
    
    # 小红书爬虫参数
    parser.add_argument('--crawl', action='store_true', help='启用小红书爬虫模式')
    parser.add_argument('--keyword', type=str, help='小红书搜索关键词（爬虫模式）')
    parser.add_argument('--pages', type=int, default=5, help='爬取页数（默认：5）')
    parser.add_argument('--headless', action='store_true', help='无头模式（不显示浏览器窗口）')
    
    # Trip.com 爬虫参数
    parser.add_argument('--tripcom-url', type=str, help='Trip.com 餐厅页面URL（启用Trip.com爬虫模式）')
    
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
        
        if args.tasks_file:
            run_tasks_file_mode(
                tasks_file=args.tasks_file,
                default_city=args.city,
                default_pages=args.pages,
                headless=args.headless,
                global_limit=args.limit,
                total_stats=total_stats
            )
        
        elif args.tripcom_url:
            # Trip.com 爬虫模式
            logger.info("Trip.com 爬虫模式")
            logger.info(f"目标URL: {args.tripcom_url}")
            
            # 创建浏览器实例（用于获取餐厅详情，包括评论）
            from app.services.tripcom_service import create_browser_page, fetch_restaurant_detail_browser
            logger.info("正在启动浏览器以获取餐厅详情和评论...")
            browser_page = create_browser_page(headless=args.headless)
            if not browser_page:
                logger.error("无法创建浏览器，将只爬取基本信息（不含评论）")
                browser_page = None
            
            # 爬取 Trip.com 餐厅数据（使用 HTTP 请求方式，不需要浏览器）
            restaurant_count = 0
            seen_restaurants = set()  # 用于去重，记录已处理的餐厅名称
            duplicate_count = 0  # 统计重复的餐厅数量
            
            # 获取数据库中已有的餐厅（用于更新检查）
            from base.database import db
            existing_restaurants = {}
            try:
                existing_df = db.execute_query("SELECT id, tweets_title, tweets_img FROM tweets WHERE tweets_type_pid = 5")
                for _, row in existing_df.iterrows():
                    existing_restaurants[row['tweets_title']] = {
                        'id': row['id'],
                        'img': row['tweets_img']
                    }
            except Exception:
                pass
            
            try:
                for restaurant in crawl_tripcom_restaurants(
                    url=args.tripcom_url,
                    pages=args.pages
                ):
                    # 限制处理数量
                    if args.limit and restaurant_count >= args.limit:
                        break
                    
                    restaurant_name = restaurant.get('name', '未知')
                
                    # 检查是否已存在于数据库
                    if restaurant_name in existing_restaurants:
                        existing_info = existing_restaurants[restaurant_name]
                        tweet_id = existing_info['id']
                        current_imgs = existing_info['img']
                        
                        # 检查是否需要更新图片（例如当前没有图片，或者强制更新）
                        has_valid_imgs = False
                        if current_imgs and current_imgs != '[]':
                            try:
                                img_list = json.loads(current_imgs)
                                if img_list and len(img_list) > 0:
                                    has_valid_imgs = True
                            except:
                                pass
                        
                        if not has_valid_imgs:
                            logger.info(f"🔄 餐厅已存在但无图片，尝试更新: {restaurant_name}")
                            # 确保有图片（如果列表页没抓够，进入详情页）
                            from app.services.tripcom_service import fetch_restaurant_detail, search_restaurant_on_tripcom
                            
                            # 如果爬虫结果中没有URL，尝试站内搜索
                            detail_url = restaurant.get('url')
                            if not detail_url:
                                detail_url = search_restaurant_on_tripcom(restaurant_name, city)
                                
                            if detail_url:
                                session = requests.Session()
                                detail = fetch_restaurant_detail(session, detail_url)
                                if detail and detail.get('images'):
                                    restaurant['images'] = detail['images']
                                session.close()
                            else:
                                logger.warning(f"  ⚠️  无法找到详情页URL")
                            
                            if restaurant.get('images'):
                                # 更新数据库
                                from app.utils.image_utils import update_restaurant_images
                                if update_restaurant_images(tweet_id, restaurant['images']):
                                    logger.info(f"  ✅ 图片更新成功")
                                else:
                                    logger.warning(f"  ⚠️  图片更新失败")
                            else:
                                logger.warning(f"  ⚠️  未抓取到图片")
                        else:
                            duplicate_count += 1
                            logger.debug(f"⏭️  跳过重复餐厅: {restaurant_name} (已存在且有图片)")
                        
                        continue
                    
                    # 去重检查：如果餐厅名称已本次运行中处理过，跳过
                    if restaurant_name in seen_restaurants:
                        duplicate_count += 1
                        continue
                    
                    # 记录已处理的餐厅
                    seen_restaurants.add(restaurant_name)
                    restaurant_count += 1
                    logger.info(f"\n处理餐厅 {restaurant_count}: {restaurant_name}")
                    
                    # 使用浏览器获取餐厅详情（包括评论和图片）
                    comments = None
                    detail_images = restaurant.get('images', [])
                    detail_address = restaurant.get('address', '')
                    detail_price_range = restaurant.get('price_range', '')
                    
                    if browser_page and restaurant.get('url'):
                        try:
                            logger.info(f"  🔍 获取餐厅详情和评论: {restaurant.get('url')}")
                            detail_info = fetch_restaurant_detail_browser(browser_page, restaurant.get('url'))
                            if detail_info:
                                # 合并评论
                                if detail_info.get('comments'):
                                    comments = detail_info['comments']
                                    logger.info(f"  ✅ 获取到 {len(comments)} 条评论")
                                
                                # 合并图片（优先使用详情页的高清图）
                                if detail_info.get('images'):
                                    # 将详情页图片放在前面
                                    detail_images = detail_info['images'] + detail_images
                                    # 去重并保持顺序
                                    seen_imgs = set()
                                    unique_imgs = []
                                    for img in detail_images:
                                        if img not in seen_imgs:
                                            unique_imgs.append(img)
                                            seen_imgs.add(img)
                                    detail_images = unique_imgs[:10]  # 最多保留10张
                                    logger.info(f"  ✅ 合并后共 {len(detail_images)} 张图片")
                                
                                # 如果详情页有地址，优先使用详情页地址
                                if detail_info.get('address'):
                                    detail_address = detail_info['address']
                                    logger.info(f"  ✅ 获取到详情页地址: {detail_address}")
                                
                                # 如果详情页有价格标识，优先使用详情页价格标识
                                if detail_info.get('price_range'):
                                    detail_price_range = detail_info['price_range']
                                    logger.info(f"  ✅ 获取到价格标识: {detail_price_range}")
                        except Exception as e:
                            logger.warning(f"  ⚠️ 获取详情失败: {e}，将使用基本信息")
                    
                    # 将 Trip.com 餐厅数据转换为笔记格式
                    # 构建标题和描述
                    title = restaurant_name
                    description_parts = []
                    
                    if restaurant.get('cuisine_type'):
                        description_parts.append(f"菜系：{restaurant['cuisine_type']}")
                    if restaurant.get('rating'):
                        description_parts.append(f"评分：{restaurant['rating']}/5")
                    if restaurant.get('review_count'):
                        description_parts.append(f"评价数：{restaurant['review_count']}条")
                    if restaurant.get('price_range'):
                        description_parts.append(f"价格：{restaurant['price_range']}")
                    if restaurant.get('description'):
                        description_parts.append(restaurant['description'])
                    
                    description = "\n".join(description_parts) if description_parts else restaurant_name
                    images = detail_images if detail_images else restaurant.get('images', [])
                    
                    # 从地址中提取城市（如果未指定）
                    city = args.city
                    if detail_address and city == '上海':  # 默认城市时尝试从地址提取
                        address = detail_address
                        # 尝试提取城市名（简单匹配）
                        city_keywords = ['北京', '上海', '广州', '深圳', '重庆', '成都', '杭州', '南京', '武汉', '西安']
                        for keyword in city_keywords:
                            if keyword in address:
                                city = keyword
                                break
                    
                    if not title:
                        logger.warning(f"餐厅 {restaurant_count} 缺少名称，跳过")
                        continue
                    
                    # 处理 Trip.com 餐厅（跳过AI转写，直接使用数据）
                    # 使用标签进行映射分类
                    tags = restaurant.get('tags', {})
                    stats = process_tripcom_restaurant(
                        restaurant_name=title,
                        description=description,
                        city=city,
                        images=images,
                        cuisine_type=restaurant.get('cuisine_type', ''),
                        rating=restaurant.get('rating'),
                        tags=tags,  # 传递标签信息
                        tripcom_address=detail_address,  # 传递详情页地址
                        comments=comments,  # 传递评论
                        price_range=detail_price_range,  # 传递价格标识
                        review_count=restaurant.get('review_count')  # 传递Trip.com评价数
                    )
                    
                    total_stats['total_notes'] += 1
                    total_stats['total_restaurants'] += stats['total_restaurants']
                    total_stats['total_success'] += stats['success']
                    total_stats['total_failed'] += stats['failed']
                    total_stats['total_comments'] += stats['comments_generated']
                    total_stats['all_errors'].extend(stats['errors'])
                    
                    # 避免请求过快
                    time.sleep(2)
            
            finally:
                # 关闭浏览器
                if browser_page:
                    try:
                        logger.info("\n所有餐厅处理完成，正在关闭浏览器...")
                        browser_page.quit()
                        logger.info("浏览器已关闭")
                    except Exception as e:
                        logger.warning(f"关闭浏览器时出错: {e}")
            
            if restaurant_count == 0:
                logger.warning("未爬取到任何餐厅")
                sys.exit(1)
            
            # 显示去重统计
            if duplicate_count > 0:
                logger.info(f"\n去重统计: 共发现 {duplicate_count} 个重复餐厅，已自动跳过")
                logger.info(f"实际处理: {restaurant_count} 个餐厅")
        
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

