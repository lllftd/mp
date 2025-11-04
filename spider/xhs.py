import csv
import datetime
import json

from DrissionPage import ChromiumPage
from urllib.parse import urljoin
import time
import os
import requests

# 初始化浏览器（配置浏览器路径若有需要）
page = ChromiumPage()
# 创建图片保存目录
save_dir = 'xiaohongshu_images'
os.makedirs(save_dir, exist_ok=True)


def login_xhs():
    """手动登录小红书（扫码）"""
    page.get('https://www.xiaohongshu.com')
    print('请扫码登录小红书（20秒等待）...')
    time.sleep(1)  # 留出扫码时间‌:ml-citation{ref="5" data="citationList"}


def get_homepage_content(keyword, pages):
    """获取首页内容并下载图片"""
    page.listen.start("https://edith.xiaohongshu.com/api/sns/web/v1/search/notes")
    # 滑动页面加载更多内容（模拟用户滚动）
    page.get(f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_explore_feed")
    time.sleep(2)
    for _ in range(pages):
        page.scroll.to_bottom()
        print("正在爬取第{0}页".format(_ + 1))
        time.sleep(2)
    responses = []
    # headers = None
    try:
        # 循环监听直到达到所需数量或超时
        for _ in range(pages):
            # 等待网络请求包到达
            packet = page.listen.wait(timeout=10)
            # 停止加载页面（这步可以根据需求调整）
            page.stop_loading()
            # headers = packet.request.headers
            # 接收 HTTP 响应内容
            response_body = packet.response.body
            # 将响应内容存储到列表中
            responses.append(response_body)
            time.sleep(1)
    except Exception as e:
        print(f"解析出现错误: {e}")
    # 处理和打印捕获到的所有响应
    total_comments = 0
    nowt = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    with open(f"{keyword}{nowt}.csv", 'a', encoding='utf-8') as file:
        file.write("标题,图片")
        file.write('\n')
        for response in responses:
            try:
                if 'data' in response:
                    datas = response['data']['items']
                    total_comments += len(datas)
                    for data in datas:
                        #source_note_id = data.get("id")
                        # xsec_token = data.get("xsec_token")
                        note_card = data.get("note_card")
                        #desc = get_note_detail(headers, source_note_id, xsec_token)
                        if note_card:
                            title = note_card.get("display_title")
                            img = note_card.get("cover").get("url_default")
                            #print(f"标题:{title}, 内容:{desc}, 图片: {img}\n")
                            file.write(f"{title},{img}")
                            file.write('\n')

            except KeyError as e:
                print(f"处理响应时出现错误: {e}")

    #page.close()



def get_note_detail(headers, source_note_id, xsec_token):
    """获取笔记详情内容"""
    jsondata = {"source_note_id": source_note_id,
     "image_formats": ["jpg", "webp", "avif"],
     "extra": {"need_body_topic": "1"},
     "xsec_source": "pc_search",
     "xsec_token": xsec_token
     }
    newheaders = {}
    newheaders['content-type'] = "application/json;charset=UTF-8"
    newheaders['cookie'] = headers.get("cookie")
    newheaders['user-agent'] = headers.get("user-agent")
    newheaders['x-s-common'] = headers.get("x-s-common")
    jsond = requests.post("https://edith.xiaohongshu.com/api/sns/web/v1/feed", headers=newheaders, json=jsondata)
    print(jsond.status_code)
    print(jsond.content.decode())
    return jsond.json().get("data").get("items")[0].get("note_card").get("desc")
    try:
        pass
        # jsond = requests.post("https://edith.xiaohongshu.com/api/sns/web/v1/feed", headers=headers, json=jsondata)
        # print(jsond.status_code)
        # print(jsond.content.decode())
        # return jsond.json().get("data").get("items")[0].get("note_card").get("desc")
    except Exception as e:

        print("详情获取失败！")
        return ""

def download_image(url):
    """下载图片到本地"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            filename = os.path.join(save_dir, url.split('/')[-1])
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return filename
    except Exception as e:
        print(f'下载失败：{url} - {str(e)}')
        return ''


if __name__ == '__main__':
    login_xhs()
    # 抓取数据
    keyword = input("请输入你要抓取的关键词：")
    pages = input("请输入要抓取的页数：")
    pages = int(pages)
    print(f"您输入的关键词是：{keyword},正在准备抓取")
    get_homepage_content(keyword, pages)
    # 可选：保存数据到 Excel（需安装 pandas）
    # import pandas as pd
    # pd.DataFrame(data).to_excel('xhs_homepage.xlsx', index=False)
