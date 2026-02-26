
import time
import random
import logging
import re
from typing import Optional, List, Dict
from urllib.parse import quote

from DrissionPage import ChromiumPage, ChromiumOptions

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DianpingService:
    def __init__(self, headless: bool = False):
        """初始化大众点评爬虫服务"""
        self.page = self._create_page(headless)
        self.base_url = "https://www.dianping.com"
        self.current_city_url = None
        
        logger.info("初始化浏览器，请在弹出的浏览器中完成登录...")
        self.page.get(self.base_url)
        input("请在浏览器中手动完成登录（扫码等），登录成功后在此处按回车继续...")
        logger.info("用户确认已登录，开始执行任务")

    def _create_page(self, headless: bool) -> ChromiumPage:
        """创建浏览器页面"""
        co = ChromiumOptions()
        co.headless(headless)
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        try:
            import os
            chrome_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    co.set_browser_path(path)
                    break
        except:
            pass

        return ChromiumPage(co)

    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.quit()

    def _random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 2.0):
        """随机等待，模拟人类行为"""
        time.sleep(random.uniform(min_seconds, max_seconds))

    def _handle_popups(self):
        """处理常见的弹窗（登录、验证码等）"""
        try:
            close_btn = self.page.ele('css:.close-btn', timeout=1) or \
                        self.page.ele('css:.icon-close', timeout=1)
            if close_btn:
                logger.info("检测到弹窗关闭按钮，尝试关闭...")
                close_btn.click()
                
            if "verify" in self.page.url:
                logger.warning("检测到验证码页面，等待...")
                time.sleep(5)
        except:
            pass

    def select_city(self, city_name: str) -> bool:
        """
        在左上角选择城市
        """
        try:
            short_city_name = city_name.replace("市", "") if len(city_name) > 2 else city_name
            
            logger.info(f"正在切换城市: {city_name} (关键词: {short_city_name})")
            
            try:
                from pypinyin import lazy_pinyin
                city_pinyin = ''.join(lazy_pinyin(short_city_name))
                city_url = f"https://www.dianping.com/{city_pinyin}"
                logger.info(f"尝试访问城市URL: {city_url}")
                self.page.get(city_url)
                self._random_sleep(2, 3)
                if short_city_name in self.page.title or self.page.ele(f'xpath://span[@class="city-name" and contains(text(), "{short_city_name}")]'):
                    logger.info(f"成功通过URL跳转到城市: {short_city_name}")
                    self.current_city_url = self.page.url
                    return True
                else:
                    logger.warning(f"URL跳转后未检测到城市确认信息: {self.page.title}")
            except ImportError:
                logger.warning("未安装 pypinyin，无法自动构造URL")
            except Exception as e:
                logger.warning(f"直接构造URL访问失败: {e}")

            logger.warning("URL方式失败，尝试访问城市列表页...")
            self.page.get("https://www.dianping.com/citylist")
            self._random_sleep(2, 3)
            
            city_link = self.page.ele(f'xpath://a[contains(text(), "{short_city_name}")]', timeout=5)
            if city_link:
                logger.info(f"在城市列表页找到: {short_city_name}，点击跳转")
                city_link.click()
                self._random_sleep(2, 3)
                self.current_city_url = self.page.url
                return True
            else:
                logger.error(f"在城市列表页也未找到城市: {short_city_name}")
                return False

        except Exception as e:
            logger.error(f"选择城市失败: {e}")
            return False

    def search_restaurant(self, keyword: str) -> Optional[str]:
        """
        搜索餐厅并返回详情页URL
        """
        try:
            logger.info(f"正在搜索餐厅: {keyword}")
            current_url = self.page.url
            if '/search/' in current_url or '/shop/' in current_url:
                logger.info("当前页面可能影响搜索，正在跳转回首页重置状态...")
                target_url = self.current_city_url if self.current_city_url else self.base_url
                self.page.get(target_url)
                self._random_sleep(1, 2)
            city_id = None
            try:
                html_content = self.page.html
                city_id_match = re.search(r'["\']cityId["\']\s*[:=]\s*(\d+)', html_content) or \
                                re.search(r'G_CITY_ID\s*=\s*(\d+)', html_content) or \
                                re.search(r'cityId\s*:\s*(\d+)', html_content)
                
                if city_id_match:
                    city_id = city_id_match.group(1)
            except:
                pass
            if not city_id:
                 if '/beijing' in self.page.url:
                     city_id = "2"
                 elif '/shanghai' in self.page.url:
                     city_id = "1"
                 elif '/guangzhou' in self.page.url:
                     city_id = "4"
                 elif '/shenzhen' in self.page.url:
                     city_id = "7"
                 else:
                     # 尝试从 cookie 获取
                     # ChromiumPage.cookies() 返回的是 List[dict]
                     # DrissionPage >= 4.0 移除了 as_dict 参数
                     cookies_list = self.page.cookies()
                     cookies = {c['name']: c['value'] for c in cookies_list}
                     if 'cy' in cookies:
                         city_id = cookies['cy']
            
            if city_id:
                logger.info(f"获取到城市ID: {city_id}，尝试直接构造搜索URL")
                
                encoded_keyword = quote(keyword)
                direct_search_url = f"https://www.dianping.com/search/keyword/{city_id}/0_{encoded_keyword}"
                
                logger.info(f"访问直连搜索URL: {direct_search_url}")
                self.page.get(direct_search_url)
                self._random_sleep(2, 3)
                
                # 检查是否跳转到搜索结果页
                if '/search/' in self.page.url and 'dianping.com' in self.page.url:
                    logger.info("直连搜索访问成功，开始解析结果...")
                    # 显式等待列表容器出现，如果超时则说明可能被反爬拦截了
                    try:
                        # 等待列表出现
                        self.page.wait.ele_display('#shop-all-list', timeout=8)
                        logger.info("商户列表加载完成")
                    except:
                        # 检查是否有验证码
                        if "verify" in self.page.url or "验证" in self.page.title:
                            logger.warning("访问被拦截，出现验证码...")
                            time.sleep(10)
                        else:
                            logger.warning("等待商户列表超时，可能是空结果或页面结构改变")
                    
                    # 无论是否找到列表，只要URL是对的，就继续尝试解析
                    # 不抛出异常，让它继续往下走去解析
                else:
                    logger.warning("直连搜索似乎未生效（可能被重定向回首页）")
                    # 以前这里会抛出异常去UI搜索，现在直接返回None或尝试解析（如果可能）
                    # 如果跳转回首页，说明搜索失败
                    if self.page.url == self.base_url:
                        return None
            else:
                logger.error("未找到城市ID，且已禁用UI搜索，无法继续")
                return None
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return None

        try:
             # 解析搜索结果
            logger.info("正在解析搜索结果链接...")
            
            # 1. 提取关键词的核心部分和分店名
            import re
            match = re.match(r'([^\(（]+)[\(（]([^\)）]+)[\)）]', keyword)
            if match:
                core_name = match.group(1).strip()
                branch_name = match.group(2).strip()
            else:
                core_name = keyword.strip()
                branch_name = ""
            
            logger.info(f"搜索关键词分析: 核心店名='{core_name}', 分店名='{branch_name}'")
            
            # 2. 获取所有搜索结果项
            # 使用更精确的 XPath 定位，基于您提供的 HTML 结构
            # 结构: div#shop-all-list -> ul -> li
            potential_items = self.page.eles('xpath://div[@id="shop-all-list"]/ul/li', timeout=5)
            
            if not potential_items:
                # 备用：尝试其他常见结构
                potential_items = self.page.eles('css:.shop-list li', timeout=2) or \
                                  self.page.eles('css:.content-wrap li', timeout=2)
            
            if not potential_items:
                logger.warning("未找到任何潜在的商户链接元素，尝试放宽选择器...")
                potential_links = self.page.eles('xpath://a[contains(@href, "/shop/")]', timeout=2)
            else:
                potential_links = potential_items

            # DEBUG: 打印所有找到的链接
            logger.info(f"找到 {len(potential_links)} 个潜在链接，开始匹配...")
            for i, item in enumerate(potential_links):
                try:
                    # item 可能是 li 里的 a，也可能直接是 a，或者 li
                    link = None
                    if item.tag == 'a':
                        link = item
                    else:
                        link = item.ele('tag:a', timeout=0.1)
                    
                    if link: # 移除 is_displayed 检查，有时候元素虽然不可见但存在
                        l_text = link.text or link.attr('title')
                        l_href = link.attr('href')
                        logger.info(f"  [{i}] 文本: '{l_text}', URL: {l_href}")
                except Exception as e:
                    pass

            candidates = []

            # 1. 优先尝试匹配关键词
            for item in potential_links:
                try:
                    link = None
                    if item.tag == 'li':
                        # 精确查找
                        link = item.ele('xpath:.//a[@data-click-name="shop_title_click"]', timeout=0.1) or \
                               item.ele('css:.tit a', timeout=0.1)
                    elif item.tag == 'a':
                        link = item
                    
                    if not link:
                        continue
                        
                    href = link.attr('href')
                    # 优先取 title 属性，因为 HTML 中 text 是 h4 标签，attr('title') 直接在 a 标签上
                    title = link.attr('title') or link.text 
                    text = link.text or title
                    
                    if not href or '/shop/' not in href:
                        continue
                    
                    # 排除非详情页
                    if any(x in href for x in ['/review/', '/photos/', '/map', '/bigmap']):
                        continue
                        
                    # 评分
                    score = 0
                    title_clean = title.replace('(', '').replace(')', '').replace('（', '').replace('）', '')
                    core_name_clean = core_name.replace(' ', '')
                    
                    # 规则1: 核心店名必须匹配
                    # 放宽匹配条件：只要核心词包含在标题中即可
                    if core_name_clean in title_clean:
                        score += 50
                    elif title_clean in core_name_clean and len(title_clean) > 2:
                        # 反向匹配：标题是关键词的一部分（例如关键词多了修饰语）
                        score += 40
                    else:
                        # 尝试分词匹配
                        common_chars = set(core_name_clean) & set(title_clean)
                        if len(common_chars) / len(core_name_clean) > 0.8:
                            score += 30
                        else:
                            # 确实不匹配，跳过
                            continue
                        
                    # 规则2: 分店名匹配加分
                    if branch_name:
                        branch_clean = branch_name.replace('店', '')
                        if branch_clean and branch_clean in title_clean:
                            score += 30
                            logger.info(f"  [匹配] 分店名命中: {branch_clean} in {title}")
                    
                    candidates.append({
                        'href': href,
                        'title': title,
                        'score': score
                    })
                    logger.info(f"  候选: {title} (得分: {score})")
                    
                except Exception as e:
                    # logger.warning(f"解析列表项失败: {e}")
                    continue
            
            # 3. 选择最佳结果
            if candidates:
                # 按得分降序排序
                candidates.sort(key=lambda x: x['score'], reverse=True)
                best_match = candidates[0]
                
                logger.info(f"✅ 最佳匹配: {best_match['title']} (得分: {best_match['score']}) -> {best_match['href']}")
                return best_match['href']
            
            # 兜底策略：如果上面都失败了，但页面确实有唯一的商户结果，直接返回
            # 这种情况下通常是因为店名匹配过于严格
            if potential_links: # 使用 potential_links 而不是 potential_items，因为 potential_items 可能是 li 列表
                 first_valid_link = None
                 for item in potential_links:
                    try:
                        if item.tag == 'a':
                            href = item.attr('href')
                            text = item.text
                        else:
                            link = item.ele('tag:a', timeout=0.1)
                            href = link.attr('href') if link else None
                            text = link.text if link else ""
                            
                        if href and '/shop/' in href and not any(x in href for x in ['/review/', '/photos/', '/map']):
                            first_valid_link = href
                            logger.warning(f"⚠️ 强制兜底使用第一个找到的商户链接: {text} ({href})")
                            return href
                    except:
                        pass

            logger.warning("未找到符合条件的商户链接")
            return None

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return None

    def crawl_images(self, detail_url: str, max_images: int = 10) -> List[str]:
        """
        爬取餐厅详情页的图片
        """
        images = []
        try:
            logger.info(f"正在访问详情页: {detail_url}")
            self.page.get(detail_url)
            self._random_sleep(2, 4)

            # 检查是否需要登录
            if "login" in self.page.url:
                logger.warning("需要登录，尝试跳转到照片页...")
            
            # 尝试直接进入"全部图片"页面
            # 通常是在详情页URL后加 /photos，或者查找"所有图片"链接
            # 示例: http://www.dianping.com/shop/12345678/photos
            
            photos_url = detail_url.split('?')[0].rstrip('/') + "/photos"
            logger.info(f"尝试访问相册页: {photos_url}")
            self.page.get(photos_url)
            self._random_sleep(2, 3)

            # 检查验证码
            if "verify" in self.page.url:
                logger.warning("检测到验证码，等待手动处理...")
                time.sleep(10)

            # 提取图片
            # 大众点评相册页图片通常在 .photo-list-item img 或类似结构
            photo_items = self.page.eles('css:.photo-list-item img', timeout=5) or \
                          self.page.eles('css:.album-list img', timeout=2) or \
                          self.page.eles('xpath://img[contains(@src, "dpfile")]', timeout=2)

            logger.info(f"找到 {len(photo_items)} 个可能的图片元素")

            for item in photo_items:
                if len(images) >= max_images:
                    break
                
                src = item.attr('src') or item.attr('data-src')
                if src:
                    # 过滤 banner 或图标等无关图片
                    if any(x in src for x in ['icon', 'logo', 'avatar', 'banner', 'mask']):
                        continue

                    # 处理缩略图转大图
                    # 大众点评图片通常是 .../240c180/...jpg 这样的格式，240c180 是尺寸
                    # 或者以 .thumb.jpg 结尾
                    # 尝试去除尺寸限制获取原图，或者替换为大尺寸
                    
                    # 策略1: 移除 .thumb. 或 .m. 等后缀
                    # 示例: http://p0.meituan.net/deal/xxx.jpg@240w_180h_1e_1c -> http://p0.meituan.net/deal/xxx.jpg
                    if '@' in src:
                        src = src.split('@')[0]
                    
                    # 策略2: 如果是缩略图路径，尝试替换
                    # 有些图片可能是 .240.180.jpg 结尾
                    
                    if src not in images:
                        images.append(src)
                        logger.info(f"提取图片(已处理为原图): {src}")

            # 如果图片太少，尝试滚动
            if len(images) < max_images:
                self.page.scroll.to_bottom()
                self._random_sleep(1, 2)
                more_items = self.page.eles('css:.photo-list-item img')
                for item in more_items:
                    if len(images) >= max_images:
                        break
                    src = item.attr('src') or item.attr('data-src')
                    if src:
                        # 过滤 banner 或图标等无关图片
                        if any(x in src for x in ['icon', 'logo', 'avatar', 'banner', 'mask']):
                            continue
                            
                        # 处理缩略图转大图
                        if '@' in src:
                            src = src.split('@')[0]

                        if src not in images:
                            images.append(src)
                            logger.info(f"提取图片(已处理为原图): {src}")

            return images

        except Exception as e:
            logger.error(f"爬取图片失败: {e}")
            return images


