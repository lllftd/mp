import datetime
import time
import random
import json
import csv
import os
import sys
from urllib.parse import quote
from DrissionPage._pages.chromium_page import ChromiumPage
from spider_config import *

# 添加当前目录到路径以导入其他模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from ai_paraphrase import get_ai_paraphraser
    from database import db
    from config import Config
    AI_AVAILABLE = True
except ImportError as e:
    print(f"警告: AI或数据库模块导入失败: {e}")
    print("将跳过AI转述和自动上传功能")
    AI_AVAILABLE = False

class XHSSpider:
    def __init__(self, use_ai_paraphrase=False, auto_upload=False):
        self.page = ChromiumPage()
        self.setup_browser()
        self.request_count = 0
        self.last_request_time = 0
        self.use_ai_paraphrase = use_ai_paraphrase and AI_AVAILABLE
        self.auto_upload = auto_upload and AI_AVAILABLE
        self.ai_paraphraser = None
        
        if self.use_ai_paraphrase:
            try:
                self.ai_paraphraser = get_ai_paraphraser()
                # 检查Ollama连接
                if not self.ai_paraphraser.check_ollama_connection():
                    print("⚠️  警告: Ollama服务未运行，AI转述功能将被禁用")
                    print("请运行 python setup_ollama.py 设置Ollama")
                    self.use_ai_paraphrase = False
                elif not self.ai_paraphraser.check_model_exists():
                    print(f"⚠️  警告: 模型 {Config.LLM_MODEL} 未下载")
                    print("请运行 python setup_ollama.py 下载模型")
                    self.use_ai_paraphrase = False
                else:
                    print("✅ AI转述功能已启用")
            except Exception as e:
                print(f"⚠️  AI转述初始化失败: {e}")
                self.use_ai_paraphrase = False
        
    def setup_browser(self):
        """设置浏览器参数"""
        # 随机选择用户代理
        user_agent = random.choice(USER_AGENTS)
        
        # 设置更真实的请求头
        headers = DEFAULT_HEADERS.copy()
        headers['User-Agent'] = user_agent
        self.page.set.headers(headers)
        
        # 设置浏览器窗口大小
        self.page.set.window.size(WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # 注意：浏览器参数设置已移除以避免兼容性问题
        # 程序将在默认浏览器设置下运行，这不会影响主要功能
        
    def enforce_rate_limit(self):
        """强制速率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # 确保请求间隔至少指定秒数
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last
            print(f"强制等待 {sleep_time:.2f} 秒以遵守速率限制...")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        # 每指定个请求后增加额外延迟
        if self.request_count % EXTRA_DELAY_INTERVAL == 0:
            extra_delay = random.uniform(EXTRA_DELAY_MIN, EXTRA_DELAY_MAX)
            print(f"已发送 {self.request_count} 个请求，额外等待 {extra_delay:.2f} 秒...")
            time.sleep(extra_delay)
        
    def random_delay(self, min_delay=None, max_delay=None):
        """随机延迟，模拟人类行为"""
        if min_delay is None:
            min_delay = DELAY_MIN
        if max_delay is None:
            max_delay = DELAY_MAX
            
        delay = random.uniform(min_delay, max_delay)
        print(f"等待 {delay:.2f} 秒...")
        time.sleep(delay)
        
    def human_like_scroll(self):
        """模拟人类滚动行为"""
        scroll_steps = random.randint(SCROLL_STEPS_MIN, SCROLL_STEPS_MAX)
        for i in range(scroll_steps):
            # 使用JavaScript滚动，更兼容
            scroll_distance = random.randint(SCROLL_DISTANCE_MIN, SCROLL_DISTANCE_MAX)
            self.page.run_js(f"window.scrollBy(0, {scroll_distance})")
            time.sleep(random.uniform(SCROLL_INTERVAL_MIN, SCROLL_INTERVAL_MAX))
            
    def check_for_blocking(self):
        """检查是否被阻止访问"""
        try:
            page_text = self.page.html.lower()
            for indicator in BLOCKING_INDICATORS:
                if indicator in page_text:
                    print(f"检测到阻止页面: {indicator}")
                    return True
                    
            return False
        except:
            return False
            
    def handle_blocking(self):
        """处理被阻止的情况"""
        print("检测到访问限制，等待更长时间...")
        wait_time = random.uniform(BLOCKING_WAIT_MIN, BLOCKING_WAIT_MAX)
        print(f"等待 {wait_time:.2f} 秒后重试...")
        time.sleep(wait_time)
        
        # 刷新页面
        try:
            self.page.refresh()
            self.page.wait.doc_loaded()
            time.sleep(random.uniform(3, 5))
        except:
            pass
        
    def get_note_detail(self, note_id, xsec_token, retry_count=0):
        """获取笔记详情信息，带重试机制"""
        try:
            # 强制速率限制
            self.enforce_rate_limit()
            
            infourl = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search&source=web_explore_feed"
            print(f"正在获取详情：{note_id}")
            
            # 随机延迟
            self.random_delay(3, 6)  # 增加延迟
            
            self.page.get(infourl)
            self.page.wait.doc_loaded()
            
            # 检查是否被阻止
            if self.check_for_blocking():
                self.handle_blocking()
                if retry_count < MAX_RETRIES:
                    return self.get_note_detail(note_id, xsec_token, retry_count + 1)
                else:
                    return "", "", ""
            
            # 模拟人类滚动行为
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
                
            return title, desc, ",".join(img_urls)
            
        except Exception as e:
            print(f"获取详情失败: {e}")
            if retry_count < MAX_RETRIES:
                print(f"第 {retry_count + 1} 次重试...")
                self.random_delay(8, 15)  # 重试时增加延迟
                return self.get_note_detail(note_id, xsec_token, retry_count + 1)
            else:
                print(f"重试 {MAX_RETRIES} 次后仍然失败")
                return "", "", ""
                
    def search_notes(self, keyword, pages):
        """搜索笔记"""
        try:
            # 监听API请求
            self.page.listen.start("https://edith.xiaohongshu.com/api/sns/web/v1/search/notes")
            
            # 编码关键词
            encoded_keyword = quote(keyword)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&source=web_explore_feed"
            
            print(f"正在访问搜索页面: {search_url}")
            self.page.get(search_url)
            
            # 等待页面加载
            self.page.wait.doc_loaded()
            self.random_delay(5, 8)  # 增加初始延迟
            
            responses = []
            
            for page_num in range(pages):
                print(f"正在爬取第 {page_num + 1} 页")
                
                # 检查是否被阻止
                if self.check_for_blocking():
                    self.handle_blocking()
                    continue
                
                # 模拟人类滚动行为
                self.human_like_scroll()
                
                # 等待网络请求
                try:
                    packet = self.page.listen.wait(timeout=REQUEST_TIMEOUT)
                    if packet and packet.response:
                        response_body = packet.response.body
                        if response_body:
                            responses.append(response_body)
                            print(f"成功捕获第 {page_num + 1} 页数据")
                        else:
                            print(f"第 {page_num + 1} 页响应为空")
                    else:
                        print(f"第 {page_num + 1} 页未捕获到有效响应")
                except Exception as e:
                    print(f"第 {page_num + 1} 页捕获失败: {e}")
                
                # 页面间延迟 - 使用更长的延迟
                if page_num < pages - 1:
                    page_delay = random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
                    print(f"页面间等待 {page_delay:.2f} 秒...")
                    time.sleep(page_delay)
            
            return responses
            
        except Exception as e:
            print(f"搜索笔记失败: {e}")
            return []
            
    def process_responses(self, responses, keyword):
        """处理响应数据"""
        total_notes = 0
        processed_count = 0
        ai_paraphrased_count = 0
        
        nowt = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{keyword}_{nowt}.csv"
        
        # 准备用于数据库上传的数据
        tweets_data = []
        
        with open(filename, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file)
            # 写入CSV头部
            if self.use_ai_paraphrase:
                writer.writerow(["标题", "描述", "图片链接", "笔记ID", "转述标题", "转述描述", "内容类型"])
            else:
                writer.writerow(["标题", "描述", "图片链接", "笔记ID"])
            
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
                            note_id = note.get("id")
                            xsec_token = note.get("xsec_token")
                            
                            if note_id and xsec_token:
                                title, desc, img = self.get_note_detail(note_id, xsec_token)
                                if title:
                                    final_title = title
                                    final_desc = desc
                                    content_type = None
                                    
                                    # AI转述
                                    if self.use_ai_paraphrase and self.ai_paraphraser:
                                        print(f"正在AI转述: {title[:30]}...")
                                        paraphrased_title, paraphrased_desc, content_type = self.ai_paraphraser.paraphrase_and_classify(title, desc)
                                        if paraphrased_title:
                                            final_title = paraphrased_title
                                            final_desc = paraphrased_desc
                                            ai_paraphrased_count += 1
                                            print(f"✅ 转述完成: {final_title[:30]}...")
                                        else:
                                            print(f"⚠️  转述失败，使用原文")
                                    
                                    # 写入CSV
                                    if self.use_ai_paraphrase:
                                        writer.writerow([title, desc, img, note_id, final_title, final_desc, content_type or ""])
                                    else:
                                        writer.writerow([title, desc, img, note_id])
                                    
                                    # 准备数据库数据
                                    if self.auto_upload:
                                        tweet = {
                                            'tweets_title': final_title,
                                            'tweets_content': final_desc,
                                            'tweets_describe': final_desc[:200] if len(final_desc) > 200 else final_desc,
                                            'tweets_img': json.dumps(img.split(',') if img else []),
                                            'tweets_type_pid': Config.DEFAULT_TYPE_PID,
                                            'tweets_type_cid': Config.DEFAULT_TYPE_CID,
                                            'tweets_user': '爬虫',
                                        }
                                        tweets_data.append(tweet)
                                    
                                    processed_count += 1
                                    
                                    # 每处理一定数量后保存
                                    if processed_count % BATCH_SIZE == 0:
                                        file.flush()
                                        print(f"已处理 {processed_count} 条数据")
                                        self.random_delay(3, 6)  # 批量处理后延迟
                    else:
                        print("响应中缺少必要的数据结构")
                        
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}")
                except Exception as e:
                    print(f"处理响应时出现错误: {e}")
        
        print(f"\n总共处理了 {total_notes} 条数据，成功保存 {processed_count} 条到 {filename}")
        if self.use_ai_paraphrase:
            print(f"AI转述成功: {ai_paraphrased_count} 条")
        
        # 自动上传到数据库
        if self.auto_upload and tweets_data:
            print(f"\n开始上传 {len(tweets_data)} 条数据到数据库...")
            try:
                from batch_upload_tweets import batch_insert_tweets
                result = batch_insert_tweets(tweets_data)
                print(f"✅ 上传完成: 成功 {result['success']} 条, 失败 {result['failed']} 条")
            except Exception as e:
                print(f"❌ 自动上传失败: {e}")
                print("可以稍后手动使用 batch_upload_tweets.py 上传")
        
        return filename
        
    def login(self):
        """手动登录小红书"""
        self.page.get('https://www.xiaohongshu.com')
        print('请扫码登录小红书')
        print('登录完成后按回车继续...')
        input()  # 等待用户确认登录完成
        time.sleep(3)  # 增加等待时间
        
    def run(self, keyword, pages):
        """运行爬虫"""
        try:
            self.login()
            
            print(f"开始抓取关键词：{keyword}")
            print(f"预计抓取 {pages} 页数据")
            print("注意：程序已优化以降低被限频的风险")
            print("建议：")
            print(f"1. 每次运行间隔至少{RECOMMENDED_INTERVAL_MINUTES}分钟")
            print(f"2. 单次抓取页数不超过{RECOMMENDED_MAX_PAGES}页")
            print("3. 如遇到限制，请等待更长时间后重试")
            
            responses = self.search_notes(keyword, pages)
            if responses:
                filename = self.process_responses(responses, keyword)
                print(f"抓取完成！数据已保存到：{filename}")
            else:
                print("未获取到任何数据")
                
        except KeyboardInterrupt:
            print("\n用户中断程序")
        except Exception as e:
            print(f"程序执行出错: {e}")
        finally:
            try:
                self.page.close()
            except:
                pass

def main():
    """主函数"""
    use_ai = False
    auto_upload = False
    
    if AI_AVAILABLE:
        print("=" * 60)
        print("爬虫配置选项")
        print("=" * 60)
        ai_choice = input("是否启用AI转述功能？(y/n，默认n): ").strip().lower()
        use_ai = ai_choice == 'y'
        
        if use_ai:
            upload_choice = input("是否自动上传到数据库？(y/n，默认n): ").strip().lower()
            auto_upload = upload_choice == 'y'
        print()
    
    spider = XHSSpider(use_ai_paraphrase=use_ai, auto_upload=auto_upload)
    
    try:
        keyword = input("请输入你要抓取的关键词：")
        pages = input(f"请输入要抓取的页数（建议不超过{RECOMMENDED_MAX_PAGES}页）：")
        pages = int(pages)
        
        if pages > RECOMMENDED_MAX_PAGES * 2:
            print("警告：页数过多可能导致被限制，建议减少页数")
            confirm = input("是否继续？(y/n): ")
            if confirm.lower() != 'y':
                return
        
        spider.run(keyword, pages)
        
    except ValueError:
        print("页数必须是数字！")
    except Exception as e:
        print(f"程序出错: {e}")

if __name__ == '__main__':
    main() 