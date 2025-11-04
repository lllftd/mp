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
from urllib.parse import quote
from DrissionPage._pages.chromium_page import ChromiumPage

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spider_config import *
from ai_paraphrase import get_ai_paraphraser
from database import db
from config import Config
from batch_upload_tweets import batch_insert_tweets

try:
    from PIL import Image
    import numpy as np
    import cv2
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False
    print("警告: PIL/OpenCV未安装，水印清洗功能将使用AI方式")


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
    
    def remove_watermark_image(self, image_url: str, save_path: str = None) -> str:
        """使用图像处理清洗水印"""
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
            
            # 简单的去水印处理：检测并移除常见的水印区域
            # 方法1: 边缘检测 + 形态学操作
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            # 方法2: 检测水印区域（通常在右下角或左下角）
            h, w = img_cv.shape[:2]
            
            # 检测右下角区域（常见水印位置）
            corner_region = img_cv[int(h*0.8):h, int(w*0.8):w]
            corner_gray = cv2.cvtColor(corner_region, cv2.COLOR_BGR2GRAY)
            
            # 使用inpainting填充水印区域
            mask = np.zeros(corner_gray.shape[:2], np.uint8)
            # 检测白色/半透明区域（常见水印特征）
            _, thresh = cv2.threshold(corner_gray, 200, 255, cv2.THRESH_BINARY)
            mask = thresh
            
            # 扩展mask到全图
            full_mask = np.zeros((h, w), np.uint8)
            full_mask[int(h*0.8):h, int(w*0.8):w] = mask
            
            # 使用inpainting去除水印
            result = cv2.inpaint(img_cv, full_mask, 3, cv2.INPAINT_TELEA)
            
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
        self.watermark_remover = WatermarkRemover()
        
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
        user_agent = random.choice(USER_AGENTS)
        headers = DEFAULT_HEADERS.copy()
        headers['User-Agent'] = user_agent
        self.page.set.headers(headers)
        self.page.set.window.size(WINDOW_WIDTH, WINDOW_HEIGHT)
    
    def enforce_rate_limit(self):
        """强制速率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.request_count += 1
        
        if self.request_count % EXTRA_DELAY_INTERVAL == 0:
            extra_delay = random.uniform(EXTRA_DELAY_MIN, EXTRA_DELAY_MAX)
            time.sleep(extra_delay)
    
    def random_delay(self, min_delay=None, max_delay=None):
        """随机延迟"""
        if min_delay is None:
            min_delay = DELAY_MIN
        if max_delay is None:
            max_delay = DELAY_MAX
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def human_like_scroll(self):
        """模拟人类滚动"""
        scroll_steps = random.randint(SCROLL_STEPS_MIN, SCROLL_STEPS_MAX)
        for i in range(scroll_steps):
            scroll_distance = random.randint(SCROLL_DISTANCE_MIN, SCROLL_DISTANCE_MAX)
            self.page.run_js(f"window.scrollBy(0, {scroll_distance})")
            time.sleep(random.uniform(SCROLL_INTERVAL_MIN, SCROLL_INTERVAL_MAX))
    
    def check_for_blocking(self):
        """检查是否被阻止"""
        try:
            page_text = self.page.html.lower()
            for indicator in BLOCKING_INDICATORS:
                if indicator in page_text:
                    return True
            return False
        except:
            return False
    
    def handle_blocking(self):
        """处理被阻止的情况"""
        wait_time = random.uniform(BLOCKING_WAIT_MIN, BLOCKING_WAIT_MAX)
        time.sleep(wait_time)
        try:
            self.page.refresh()
            self.page.wait.doc_loaded()
            time.sleep(random.uniform(3, 5))
        except:
            pass
    
    def get_note_detail(self, note_id, xsec_token, retry_count=0):
        """获取笔记详情"""
        try:
            self.enforce_rate_limit()
            infourl = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search&source=web_explore_feed"
            print(f"正在获取详情：{note_id}")
            
            self.random_delay(3, 6)
            self.page.get(infourl)
            self.page.wait.doc_loaded()
            
            if self.check_for_blocking():
                self.handle_blocking()
                if retry_count < MAX_RETRIES:
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
                
            return title, desc, ",".join(img_urls)
            
        except Exception as e:
            print(f"获取详情失败: {e}")
            if retry_count < MAX_RETRIES:
                self.random_delay(8, 15)
                return self.get_note_detail(note_id, xsec_token, retry_count + 1)
            else:
                return "", "", ""
    
    def search_notes(self, keyword, pages):
        """搜索笔记"""
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
                print(f"正在爬取第 {page_num + 1} 页")
                
                if self.check_for_blocking():
                    self.handle_blocking()
                    continue
                
                self.human_like_scroll()
                
                try:
                    packet = self.page.listen.wait(timeout=REQUEST_TIMEOUT)
                    if packet and packet.response:
                        response_body = packet.response.body
                        if response_body:
                            responses.append(response_body)
                            print(f"成功捕获第 {page_num + 1} 页数据")
                except Exception as e:
                    print(f"第 {page_num + 1} 页捕获失败: {e}")
                
                if page_num < pages - 1:
                    page_delay = random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX)
                    time.sleep(page_delay)
            
            return responses
            
        except Exception as e:
            print(f"搜索笔记失败: {e}")
            return []
    
    def process_and_upload(self, responses, keyword):
        """处理数据并上传"""
        total_notes = 0
        processed_count = 0
        ai_paraphrased_count = 0
        
        tweets_data = []
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
            writer.writerow(["标题", "描述", "图片链接", "笔记ID", "转述标题", "转述描述", "内容类型", "清洗后图片"])
            
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
                                    cleaned_images = []
                                    saved_image_paths = []
                                    
                                    # AI转述
                                    print(f"正在AI转述: {title[:30]}...")
                                    paraphrased_title, paraphrased_desc, content_type = self.ai_paraphraser.paraphrase_and_classify(title, desc)
                                    if paraphrased_title:
                                        final_title = paraphrased_title
                                        final_desc = paraphrased_desc
                                        ai_paraphrased_count += 1
                                        print(f"✅ 转述完成: {final_title[:30]}...")
                                    
                                    # 保存原文
                                    original_filename = os.path.join(original_dir, f"{processed_count:04d}_{note_id}.txt")
                                    with open(original_filename, 'w', encoding='utf-8') as f:
                                        f.write(f"标题: {title}\n\n")
                                        f.write(f"描述: {desc}\n")
                                    print(f"已保存原文: {original_filename}")
                                    
                                    # 保存转述内容
                                    paraphrased_filename = os.path.join(paraphrased_dir, f"{processed_count:04d}_{note_id}.txt")
                                    with open(paraphrased_filename, 'w', encoding='utf-8') as f:
                                        f.write(f"标题: {final_title}\n\n")
                                        f.write(f"描述: {final_desc}\n")
                                        if content_type:
                                            f.write(f"\n内容类型: {content_type}\n")
                                    print(f"已保存转述: {paraphrased_filename}")
                                    
                                    # 下载并清洗图片
                                    if img:
                                        img_list = img.split(',')
                                        for idx, img_url in enumerate(img_list):
                                            if img_url.strip():
                                                print(f"正在处理图片 {idx+1}/{len(img_list)}: {img_url[:50]}...")
                                                
                                                # 生成图片文件名
                                                img_ext = os.path.splitext(img_url.split('?')[0])[1] or '.jpg'
                                                img_filename = f"{processed_count:04d}_{note_id}_{idx+1}{img_ext}"
                                                img_path = os.path.join(images_dir, img_filename)
                                                
                                                # 清洗水印并保存
                                                if Config.REMOVE_WATERMARK and IMAGE_PROCESSING_AVAILABLE:
                                                    cleaned_img = self.watermark_remover.remove_watermark_image(img_url.strip(), img_path)
                                                    if cleaned_img and os.path.exists(cleaned_img):
                                                        saved_image_paths.append(cleaned_img)
                                                        print(f"✅ 水印清洗完成: {img_filename}")
                                                else:
                                                    # 直接下载原图
                                                    saved_path = self.watermark_remover.download_image(img_url.strip(), img_path)
                                                    if saved_path:
                                                        saved_image_paths.append(saved_path)
                                                        print(f"✅ 图片下载完成: {img_filename}")
                                    
                                    cleaned_img_str = ",".join(saved_image_paths) if saved_image_paths else img
                                    
                                    # 写入CSV
                                    writer.writerow([title, desc, img, note_id, final_title, final_desc, content_type or "", cleaned_img_str])
                                    
                                    # 准备数据库数据
                                    tweet = {
                                        'tweets_title': final_title,
                                        'tweets_content': final_desc,
                                        'tweets_describe': final_desc[:200] if len(final_desc) > 200 else final_desc,
                                        'tweets_img': json.dumps(saved_image_paths) if saved_image_paths else json.dumps(img.split(',') if img else []),
                                        'tweets_type_pid': Config.DEFAULT_TYPE_PID,
                                        'tweets_type_cid': Config.DEFAULT_TYPE_CID,
                                        'tweets_user': Config.DEFAULT_USER,
                                    }
                                    tweets_data.append(tweet)
                                    
                                    processed_count += 1
                                    
                                    if processed_count % BATCH_SIZE == 0:
                                        file.flush()
                                        print(f"已处理 {processed_count} 条数据")
                                        self.random_delay(3, 6)
                except Exception as e:
                    print(f"处理响应时出现错误: {e}")
        
        print(f"\n总共处理了 {total_notes} 条数据，成功保存 {processed_count} 条")
        print(f"保存位置: {base_dir}")
        print(f"AI转述成功: {ai_paraphrased_count} 条")
        
        # 自动上传到数据库
        if tweets_data:
            print(f"\n开始上传 {len(tweets_data)} 条数据到数据库...")
            try:
                result = batch_insert_tweets(tweets_data)
                print(f"✅ 上传完成: 成功 {result['success']} 条, 失败 {result['failed']} 条")
            except Exception as e:
                print(f"❌ 自动上传失败: {e}")
        
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
            self.login()
            
            print(f"\n开始抓取关键词：{keyword}")
            print(f"预计抓取 {pages} 页数据")
            print("=" * 60)
            
            responses = self.search_notes(keyword, pages)
            if responses:
                filename = self.process_and_upload(responses, keyword)
                print(f"\n✅ 全部完成！数据已保存到：{filename}")
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
    
    spider = IntegratedSpider()
    spider.run(keyword, pages)


if __name__ == '__main__':
    main()

