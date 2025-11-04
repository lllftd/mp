import datetime
import time

from DrissionPage._pages.chromium_page import ChromiumPage

id= "67f8dbe4000000001c01ce02"
token = "AB-0o86otpj60m1Eez5ZzvmbY2ZB-CWczR2vx0pe732pY="

page = ChromiumPage()
def get_info(id, token):
    infourl = f"https://www.xiaohongshu.com/explore/{id}?xsec_token={token}&xsec_source=pc_search&source=web_explore_feed"
    print(f"正在获取详情：{infourl}")
    page.get(infourl)
    page.wait.doc_loaded()
    img_url = []
    try:
        images = page.eles('.swiper-wrapper')[0].eles("tag:img")
        for img in images:
            try:
                imgurl = img.attr("src")
                if imgurl not in img_url:
                    img_url.append(img.attr("src"))
            except:
                pass
    except:
        pass
    title = ""
    desc = ""
    titleele = page.ele("#detail-title")
    if titleele:
        title = titleele.text
    descele = page.ele("#detail-desc")
    if descele:
        desc = descele.text
    return title, desc, ",".join(img_url)

def get_homepage_content(keyword, pages):
    """获取首页内容并下载图片"""
    page.listen.start("https://edith.xiaohongshu.com/api/sns/web/v1/search/notes")
    # 滑动页面加载更多内容（模拟用户滚动）
    page.get(f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_explore_feed")
    time.sleep(1)
    for _ in range(pages):
        page.scroll.to_bottom()
        print("正在爬取第{0}页".format(_ + 1))
        time.sleep(1)
    responses = []
    try:
        # 循环监听直到达到所需数量或超时
        for _ in range(pages):
            # 等待网络请求包到达
            packet = page.listen.wait(timeout=10)
            # 停止加载页面（这步可以根据需求调整）
            page.stop_loading()
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
        for response in responses:
            try:
                if 'data' in response:
                    if 'items' in response['data']:
                        datas = response['data']['items']
                        total_comments += len(datas)
                        for data in datas:
                            source_note_id = data.get("id")
                            xsec_token = data.get("xsec_token")
                            if source_note_id and xsec_token:
                                title, desc, img = get_info(source_note_id, xsec_token)
                                if title:
                                    file.write(f"{title},{desc},{img}")
                                    file.write('\n')
                    else:
                        print(f"响应中缺少'items'键，跳过此响应")
                else:
                    print(f"响应中缺少'data'键，跳过此响应")

            except KeyError as e:
                print(f"处理响应时出现错误: {e}")
            except Exception as e:
                print(f"处理响应时出现未知错误: {e}")
    page.close()

if __name__ == '__main__':
    def login_xhs():
        """手动登录小红书（扫码）"""
        page.get('https://www.xiaohongshu.com')
        print('请扫码登录小红书（20秒等待）...')
        time.sleep(1)  # 留出扫码时间‌:ml-citation{ref="5" data="citationList"}


    login_xhs()
    # 抓取数据
    keyword = input("请输入你要抓取的关键词：")
    pages = input("请输入要抓取的页数：")
    pages = int(pages)
    print(f"您输入的关键词是：{keyword},正在准备抓取")
    get_homepage_content(keyword, pages)