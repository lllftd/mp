#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本：从小红书搜索餐厅，爬取评论，并使用DeepSeek生成种草文案
"""
import os
import sys
import time
import argparse
import logging
import random
from typing import List, Dict, Optional, Tuple
from sqlalchemy import text

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from DrissionPage import ChromiumPage, ChromiumOptions
from app.services.ai_service import get_ai_paraphraser
from base.database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_browser_page(headless: bool = False):
    """创建浏览器页面对象"""
    co = ChromiumOptions()
    if headless:
        co.headless(True)
    
    # 尝试复用已有的用户数据目录（如果存在），以保持登录状态
    user_data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'chrome_user_data')
    if os.path.exists(user_data_path):
        co.set_user_data_path(user_data_path)
    
    # 尝试自动查找浏览器路径
    try:
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

def search_xhs_and_get_comments(keyword: str, max_comments: int = 20, max_notes: int = 5, headless: bool = False) -> Tuple[str, str, List[str]]:
    """
    在小红书搜索关键词，随机点击几个笔记，爬取评论
    
    Returns:
        (note_title, note_desc, comments_list)
    """
    page = create_browser_page(headless)
    all_comments = []
    collected_contents = []  # 收集所有笔记的正文内容
    first_title = ""
    
    try:
        # 1. 搜索
        # 改为通过首页搜索框搜索，避免直接访问URL被限频
        logger.info(f"正在访问小红书首页...")
        page.get("https://www.xiaohongshu.com/explore")
        
        # 等待加载
        time.sleep(random.uniform(3, 5))
        
        # 尝试查找搜索框
        search_input = page.ele('css:#search-input', timeout=5)
        if not search_input:
            search_input = page.ele('css:input.search-input', timeout=2)
        if not search_input:
            search_input = page.ele('css:input[type="text"]', timeout=2)
            
        if search_input:
            logger.info(f"找到搜索框，输入关键词: {keyword}")
            search_input.clear()
            search_input.input(keyword)
            time.sleep(random.uniform(0.5, 1.5))
            
            # 点击搜索按钮或回车
            search_btn = page.ele('css:.search-icon', timeout=2)
            if search_btn:
                search_btn.click()
            else:
                logger.info("未找到搜索按钮，尝试按回车...")
                page.actions.key_down('ENTER').key_up('ENTER')
        else:
            logger.warning("未找到搜索框，降级为直接访问搜索URL...")
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
            page.get(search_url)
        
        # 等待结果加载
        time.sleep(random.uniform(5, 8))
        
        # 随机滚动一下，模拟真人浏览
        page.scroll.down(random.randint(100, 300))
        time.sleep(random.uniform(1, 2))
        
        # 2. 获取所有笔记卡片元素
        note_items = []
        try:
            # 等待列表加载
            try:
                page.wait.ele('css:.note-item, css:section.note-item, css:a[href*="/explore/"]', timeout=10)
            except:
                pass

            logger.info("正在获取页面笔记元素...")
            # 优先找笔记卡片元素
            note_items = page.eles('css:.note-item')
            if not note_items:
                 note_items = page.eles('css:section .note-item')
            
            # 如果找不到 .note-item，尝试找封面图容器
            if not note_items:
                 note_items = page.eles('xpath://a[contains(@href, "/explore/")]')

            # 截取需要的数量
            targets = note_items[:max_notes]
            
            if not targets:
                logger.error("未找到任何笔记元素")
                return "", "", []
                
            logger.info(f"找到 {len(targets)} 个笔记，准备逐个点击...")
            
            for i, item in enumerate(targets):
                try:
                    logger.info(f"正在处理第 {i+1}/{len(targets)} 个笔记...")
                    
                    # --- 1. 模拟点击进入 ---
                    # 尝试点击图片，成功率更高
                    click_target = item
                    try:
                        cover = item.ele('tag:img')
                        if cover:
                            click_target = cover
                    except:
                        pass
                    
                    # 滚动到可见区域
                    # page.scroll.to_ele(click_target)
                    time.sleep(1)
                    
                    logger.info("点击笔记...")
                    click_target.click()
                    
                    # --- 2. 等待详情页加载 ---
                    time.sleep(random.uniform(3, 5))
                    
                    # 判断是弹窗还是新标签页
                    is_new_tab = len(page.tab_ids) > 1
                    current_ctx = page
                    
                    if is_new_tab:
                        logger.info("检测到新标签页，切换...")
                        current_ctx = page.get_tab(page.tab_ids[-1])
                    
                    # --- 3. 提取内容 ---
                    # 提取标题
                    current_title = ""
                    try:
                        title_ele = current_ctx.ele('css:.note-content .title', timeout=5) or current_ctx.ele('css:#detail-title', timeout=2)
                        current_title = title_ele.text if title_ele else ""
                        logger.info(f"笔记标题: {current_title}")
                        
                        if i == 0:
                            first_title = current_title
                    except Exception as e:
                        logger.warning(f"提取标题失败: {e}")

                    # 提取正文
                    current_desc = ""
                    try:
                        desc_ele = current_ctx.ele('css:.note-content .desc', timeout=2) or current_ctx.ele('css:#detail-desc', timeout=2)
                        current_desc = desc_ele.text if desc_ele else ""
                        if current_desc:
                            logger.info(f"提取到正文，长度: {len(current_desc)}")
                            collected_contents.append(f"【笔记{i+1}参考内容】\n标题：{current_title}\n正文：{current_desc}")
                    except Exception as e:
                        logger.warning(f"提取正文失败: {e}")

                    # 提取评论
                    logger.info("提取评论...")
                    # 滚动加载
                    try:
                        # 尝试在评论容器内滚动，或者整个页面滚动
                        comment_container = current_ctx.ele('css:.comments-container')
                        if comment_container:
                             comment_container.scroll.down(1000)
                        else:
                             current_ctx.scroll.down(1000)
                        time.sleep(1)
                    except:
                        pass
                        
                    comment_eles = current_ctx.eles('css:.comment-item .content')
                    if not comment_eles:
                        comment_eles = current_ctx.eles('css:.comment-content')
                        
                    count = 0
                    for ele in comment_eles:
                        text = ele.text.strip()
                        if text and len(text) > 5 and text not in all_comments:
                            all_comments.append(text)
                            count += 1
                            if len(all_comments) >= max_comments:
                                break
                    logger.info(f"  - 抓取到 {count} 条评论")
                    
                    # --- 4. 退出/关闭详情页 ---
                    if is_new_tab:
                        logger.info("关闭新标签页...")
                        current_ctx.close()
                    else:
                        logger.info("直接点击左上角退出弹窗...")
                        # 直接点击屏幕左上角区域 (坐标 30, 30)
                        try:
                            page.actions.move_to((30, 30)).click()
                        except Exception as e:
                            logger.warning(f"点击左上角失败: {e}")
                            # 兜底：按ESC
                            page.actions.key_down('ESCAPE').key_up('ESCAPE')
                        
                        time.sleep(2)
                    
                    if len(all_comments) >= max_comments:
                        break
                    
                    # 随机停顿
                    time.sleep(random.uniform(2, 5))
                        
                except Exception as e:
                    logger.warning(f"处理笔记 {i+1} 失败: {e}")
                    # 如果出错，尝试按 ESC 恢复
                    try:
                        page.actions.key_down('ESCAPE').key_up('ESCAPE')
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"处理搜索结果失败: {e}")
            return "", "", []

        logger.info(f"总计提取 {len(all_comments)} 条评论")
        
        # 组合所有抓取到的内容
        combined_desc = "\n\n------------------\n\n".join(collected_contents)
        if not combined_desc and first_title:
             combined_desc = f"标题：{first_title}"
             
        return first_title, combined_desc, all_comments

    except Exception as e:
        logger.error(f"爬取过程出错: {e}")
        return "", "", []
    finally:
        if headless:
            page.quit()

def find_tweet_id_by_name(name: str) -> Optional[int]:
    """根据餐厅名称查找数据库中的tweet_id"""
    try:
        # 1. 精确匹配
        sql = "SELECT id FROM tweets WHERE tweets_title = :name LIMIT 1"
        df = db.execute_query(sql, {'name': name})
        if not df.empty:
            return df.iloc[0]['id']
            
        # 2. 模糊匹配 (如果精确匹配失败)
        sql = "SELECT id FROM tweets WHERE tweets_title LIKE :name LIMIT 1"
        df = db.execute_query(sql, {'name': f"%{name}%"})
        if not df.empty:
            return df.iloc[0]['id']
            
        return None
    except Exception as e:
        logger.error(f"查找Tweet ID失败: {e}")
        return None

def generate_xhs_note(restaurant_name: str, headless: bool = False, upload_comments: bool = False):
    """
    生成小红书种草文案流程
    """
    logger.info(f"=== 开始处理: {restaurant_name} ===")
    
    # 1. 爬取
    note_title, note_desc, comments = search_xhs_and_get_comments(restaurant_name, headless=headless)
    
    if not comments:
        logger.warning("未抓取到评论，将仅基于餐厅名称生成")
        # 也可以选择退出
        # return
    
    # 2. 调用DeepSeek生成
    logger.info("正在调用DeepSeek生成种草文案...")
    ai = get_ai_paraphraser()
    
    # 直接设置正确的模型配置
    ai.model = "deepseek-chat"
    ai.api_base = "https://api.deepseek.com"
    logger.info(f"模型配置: {ai.model}, API Base: {ai.api_base}")
    
    # 构造餐厅信息
    restaurant_info = {
        'name': restaurant_name,
        'description': note_desc, # 使用抓取到的笔记内容作为背景
        'address': '', # 暂无地址
        'price_range': '' # 暂无价格
    }
    
    # 使用 paraphrase_restaurant 方法
    # 注意：我们把抓取到的评论传进去
    new_title, new_desc, _, _ = ai.paraphrase_restaurant(
        restaurant_info=restaurant_info,
        original_title=note_title,
        original_description=note_desc,
        comments=comments,
        auto_generate_comments=False # 不自动生成评论，使用我们传入的
    )
    
    if new_desc:
        # 去除正文中的星号
        new_desc = new_desc.replace('*', '')

    if new_title and new_desc:
        print("\n" + "="*50)
        print("【生成结果】")
        print("="*50)
        # print(f"标题：\n{new_title}\n")
        print(f"正文：\n{new_desc}")
        print("="*50)
    else:
        logger.error("生成失败")

    # 3. 上传评论 (如果需要)
    if upload_comments:
        logger.info("正在查找数据库中的对应餐厅...")
        tweet_id = find_tweet_id_by_name(restaurant_name)
        if tweet_id:
            if new_desc:
                logger.info(f"找到餐厅 ID: {tweet_id}，开始更新正文（tweets_content）...")
                try:
                    update_sql = "UPDATE tweets SET tweets_content = :content WHERE id = :id"
                    db.execute_update(update_sql, {'content': new_desc, 'id': tweet_id})
                    logger.info(f"成功更新 tweets_content，长度: {len(new_desc)}")
                except Exception as e:
                    logger.error(f"更新正文失败: {e}")
            else:
                logger.warning("生成的内容为空，不执行更新")
        else:
            logger.warning(f"未在数据库中找到餐厅 '{restaurant_name}'，跳过更新")

def get_all_restaurants() -> List[Dict]:
    """获取数据库中所有餐厅的名称和ID"""
    try:
        sql = "SELECT id, tweets_title FROM tweets WHERE tweets_title IS NOT NULL AND tweets_title != ''"
        df = db.execute_query(sql)
        if not df.empty:
            return df[['id', 'tweets_title']].to_dict('records')
        return []
    except Exception as e:
        logger.error(f"获取所有餐厅失败: {e}")
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='搜索小红书并生成种草文案')
    parser.add_argument('name', type=str, nargs='?', help='餐厅名称（如果未指定--all）')
    parser.add_argument('--headless', action='store_true', help='使用无头模式')
    parser.add_argument('--upload-comments', action='store_true', help='将爬取的评论上传到数据库（需数据库中存在该餐厅）')
    parser.add_argument('--all', action='store_true', help='爬取数据库中所有餐厅')
    parser.add_argument('--start-id', type=int, default=0, help='从指定ID开始爬取（仅配合--all使用）')
    
    args = parser.parse_args()
    
    if args.all:
        logger.info("开始爬取数据库中所有餐厅...")
        restaurants = get_all_restaurants()
        logger.info(f"共找到 {len(restaurants)} 个餐厅")
        
        # 排序，确保按ID顺序处理
        restaurants.sort(key=lambda x: x['id'])
        
        for i, item in enumerate(restaurants):
            r_id = item['id']
            name = item['tweets_title']
            
            if r_id < args.start_id:
                continue
                
            logger.info(f"进度: {i+1}/{len(restaurants)} | ID: {r_id} | 餐厅: {name}")
            try:
                generate_xhs_note(name, headless=args.headless, upload_comments=args.upload_comments)
                # 随机休眠防止封控，增加时长
                sleep_time = random.uniform(20, 40)
                logger.info(f"休眠 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"处理餐厅 {name} 失败: {e}")
                time.sleep(10)
                continue
    elif args.name:
        generate_xhs_note(args.name, headless=args.headless, upload_comments=args.upload_comments)
    else:
        parser.print_help()
        sys.exit(1)

