#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
随机用户名生成器
包含：战锤40k人物名、JOJO替身名、中药名、星体名、剑风传奇角色名
"""
import random


class RandomUsernameGenerator:
    """随机用户名生成器"""
    
    # 战锤40k人物名
    WARHAMMER_NAMES = [
        "马卡里乌斯", "罗保特·基里曼", "卡尔加", "泰伦斯", "卡托·西卡留斯",
        "马里乌斯", "但丁", "阿兹瑞尔", "贝利萨留·考尔", "西卡留斯",
        "文坦努斯", "阿巴顿", "荷鲁斯", "鲁斯", "科拉克斯",
        "伏尔甘", "费鲁斯", "多恩", "圣吉列斯", "察合台可汗",
        "康拉德·科兹", "安格朗", "莱昂·艾尔庄森", "福格瑞姆", "莫塔里安",
        "马格努斯", "洛迦", "佩图拉博", "阿尔法瑞斯", "荷鲁斯·卢佩卡尔"
    ]
    
    # JOJO替身名
    JOJO_STANDS = [
        "白金之星", "世界", "疯狂钻石", "杀手皇后", "绯红之王",
        "石之自由", "天堂制造", "黄金体验", "钢链手指", "性感手枪",
        "金属制品", "绿洲", "银战车镇魂曲", "白蛇", "天气预报",
        "石之海", "D4C", "天生完美", "软&湿", "奇迹与你",
        "护霜旅行者", "卡兹", "艾斯迪斯", "瓦姆乌", "桑塔纳",
        "迪奥", "普奇神父", "迪亚波罗", "吉良吉影", "岸边露伴"
    ]
    
    # 中药名
    TRADITIONAL_MEDICINE = [
        "人参", "黄芪", "当归", "熟地黄", "白芍", "川芎", "党参", "白术",
        "茯苓", "甘草", "陈皮", "半夏", "天麻", "杜仲", "枸杞", "灵芝",
        "三七", "何首乌", "丹参", "红花", "金银花", "菊花", "薄荷", "连翘",
        "黄芩", "黄连", "黄柏", "大黄", "芒硝", "火麻仁", "苦杏仁", "紫苏",
        "生姜", "大枣", "葛根", "柴胡", "升麻", "知母", "石膏", "淡竹叶",
        "石斛", "麦冬", "天冬", "玉竹", "沙参", "玄参", "生地黄", "牡丹皮",
        "赤芍", "地骨皮", "银柴胡", "青蒿", "白薇", "胡黄连", "秦艽", "防己"
    ]
    
    # 星体名（中国古代星名）
    STAR_NAMES = [
        "参宿", "心宿", "角宿", "亢宿", "氐宿", "房宿", "尾宿", "箕宿",
        "斗宿", "牛宿", "女宿", "虚宿", "危宿", "室宿", "壁宿", "奎宿",
        "娄宿", "胃宿", "昴宿", "毕宿", "觜宿", "井宿", "鬼宿", "柳宿",
        "星宿", "张宿", "翼宿", "轸宿", "轩辕", "太微", "紫微", "天市",
        "天枢", "天璇", "天玑", "天权", "玉衡", "开阳", "摇光", "织女",
        "牛郎", "天津", "北河", "南河", "五车", "参宿三", "心宿二",
        "角宿一", "大角", "轩辕十四", "北落师门", "南门二", "天狼", "老人", "参宿四"
    ]
    
    # 剑风传奇角色名
    BERSERK_NAMES = [
        "格斯", "格里菲斯", "卡思嘉", "佐德", "古伦贝尔特",
        "尤里乌斯", "夏洛特", "阿道尼斯", "塞尔皮科", "法尔纳塞",
        "伊斯多洛", "希瑟", "格伦", "里基特", "艾丽卡",
        "奥加", "诺艾尔", "萨尼亚", "卢卡", "西尔克",
        "斯兰", "帕克", "伊尔德娜", "多诺万", "甘比诺",
        "骷髅骑士", "魔女", "魔女弗洛拉", "史尔基", "使徒",
        "神之手", "使徒佐德", "使徒古伦贝尔特", "使徒格里菲斯", "使徒骷髅骑士",
        "使徒法尔纳塞", "使徒塞尔皮科", "使徒艾丽卡", "使徒希瑟", "使徒格伦"
    ]
    
    def __init__(self):
        """初始化生成器"""
        self.all_categories = [
            ("战锤40k", self.WARHAMMER_NAMES),
            ("JOJO替身", self.JOJO_STANDS),
            ("中药", self.TRADITIONAL_MEDICINE),
            ("星体", self.STAR_NAMES),
            ("剑风传奇", self.BERSERK_NAMES)
        ]
    
    def generate(self) -> str:
        """生成随机用户名"""
        category_name, names_list = random.choice(self.all_categories)
        base_name = random.choice(names_list)
        
        # 随机添加数字后缀（30%概率）
        if random.random() < 0.3:
            suffix = random.randint(1, 999)
            return f"{base_name}{suffix}"
        
        return base_name
    
    def generate_with_category(self) -> tuple:
        """生成随机用户名并返回类别"""
        category_name, names_list = random.choice(self.all_categories)
        base_name = random.choice(names_list)
        
        # 随机添加数字后缀（30%概率）
        if random.random() < 0.3:
            suffix = random.randint(1, 999)
            username = f"{base_name}{suffix}"
        else:
            username = base_name
        
        return username, category_name


# 全局实例
_generator = None


def get_random_username() -> str:
    """获取随机用户名"""
    global _generator
    if _generator is None:
        _generator = RandomUsernameGenerator()
    return _generator.generate()


def get_random_username_with_category() -> tuple:
    """获取随机用户名和类别"""
    global _generator
    if _generator is None:
        _generator = RandomUsernameGenerator()
    return _generator.generate_with_category()


if __name__ == '__main__':
    # 测试
    print("随机用户名生成测试：")
    print("=" * 50)
    for i in range(20):
        username, category = get_random_username_with_category()
        print(f"{i+1:2d}. [{category:8s}] {username}")
