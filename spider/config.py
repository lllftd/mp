# 小红书爬虫配置文件
# 用于调整速率限制和反检测参数

# 基础延迟设置
DELAY_MIN = 5  # 最小延迟秒数
DELAY_MAX = 12  # 最大延迟秒数
PAGE_DELAY_MIN = 8  # 页面间最小延迟
PAGE_DELAY_MAX = 15  # 页面间最大延迟

# 请求控制
MAX_RETRIES = 3  # 最大重试次数
REQUEST_TIMEOUT = 30  # 请求超时时间
BATCH_SIZE = 3  # 每批处理的数据量
MIN_REQUEST_INTERVAL = 5  # 请求间最小间隔（秒）
EXTRA_DELAY_INTERVAL = 10  # 每多少个请求后增加额外延迟
EXTRA_DELAY_MIN = 10  # 额外延迟最小值
EXTRA_DELAY_MAX = 20  # 额外延迟最大值

# 阻止检测关键词
BLOCKING_INDICATORS = [
    "访问频次异常",
    "请勿频繁访问", 
    "访问过于频繁",
    "系统繁忙",
    "请稍后再试",
    "验证码",
    "访问受限",
    "请求过于频繁"
]

# 用户代理池
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
]

# 浏览器参数 - 简化版本，避免兼容性问题
BROWSER_ARGUMENTS = [
    '--no-sandbox',
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-web-security',
    '--disable-extensions',
    '--disable-plugins'
]

# 请求头设置
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
    'DNT': '1',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
}

# 窗口大小
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# 滚动设置
SCROLL_STEPS_MIN = 2
SCROLL_STEPS_MAX = 4
SCROLL_DISTANCE_MIN = 200
SCROLL_DISTANCE_MAX = 600
SCROLL_INTERVAL_MIN = 1.0
SCROLL_INTERVAL_MAX = 2.0

# 阻止处理设置
BLOCKING_WAIT_MIN = 60  # 检测到阻止时等待时间最小值（秒）
BLOCKING_WAIT_MAX = 120  # 检测到阻止时等待时间最大值（秒）

# 建议设置
RECOMMENDED_MAX_PAGES = 5  # 建议最大页数
RECOMMENDED_INTERVAL_MINUTES = 30  # 建议运行间隔（分钟） 