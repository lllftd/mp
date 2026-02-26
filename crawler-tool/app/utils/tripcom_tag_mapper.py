#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trip.com 标签到分类ID的映射工具

根据 Trip.com 页面上的标签，映射到 DATA_FORMAT.md 中定义的分类ID
参考页面：https://hk.trip.com/restaurant/chongqing-158/?locale=zh-hk&curr=HKD
"""
import logging
from typing import List, Set, Optional, Dict

logger = logging.getLogger(__name__)

# 1. 映射菜系标签
CUISINE_MAPPING = {
    # 菜系分类（ID: 6-40）
    '川菜': '6',
    '淮揚菜': '8', '淮扬菜': '8',
    '杭幫菜': '9', '杭帮菜': '9',
    '潮汕菜': '10',
    '燒烤': '11', '烧烤': '11',
    '粵菜': '12', '粤菜': '12', '廣東菜': '12', '广东菜': '12',
    '德國菜': '13', '德国菜': '13',
    '日本料理': '14', '日式': '14', '日料': '14',
    '法國菜': '15', '法国菜': '15', '法式': '15',
    '韓國料理': '16', '韩国料理': '16', '韓式': '16', '韩式': '16',
    '新疆菜': '17',
    '湘菜': '18',
    '農家菜': '19', '农家菜': '19',
    '火鍋': '20', '火锅': '20',
    '咖啡': '21', '咖啡廳': '21', '咖啡厅': '21', '咖啡店': '21',
    '自助餐': '22',
    '魚鮮': '23', '鱼鲜': '23', '海鮮': '23', '海鲜': '23',
    '東北菜': '24', '东北菜': '24',
    '私房菜': '25',
    '東南亞菜': '26', '东南亚菜': '26',
    '特色菜': '27',
    '創意菜': '28', '创意菜': '28',
    '北京菜': '29', '京菜': '29',
    '家常菜': '30',
    '茶餐廳': '31', '茶餐厅': '31', '茶館': '31', '茶馆': '31', '茶室': '31',
    '小龍蝦': '32', '小龙虾': '32',
    '素食': '33', '素食友善': '33',
    '小吃': '34', '小食': '34', '快餐': '34',
    '麵包': '35', '面包': '35', '甜點': '35', '甜点': '35', '甜品': '35',
    '麵館': '36', '面馆': '36', '小麵': '36', '小面': '36',
    '大排檔': '37', '大排档': '37',
    '西餐': '38', '西式': '38',
    '雲南菜': '39', '云南菜': '39',
    '西北菜': '40',
    
    # 补充菜系（ID: 46-64）
    '意大利菜': '46', '意式': '46',
    '泰國菜': '47', '泰国菜': '47', '泰式': '47',
    '越南菜': '48', '越式': '48',
    '印度菜': '49', '印式': '49',
    '墨西哥菜': '50',
    '西班牙菜': '51',
    '土耳其菜': '52',
    '希臘菜': '53', '希腊菜': '53',
    '巴西菜': '54',
    '徽菜': '55',
    '魯菜': '56', '鲁菜': '56',
    '閩菜': '57', '闽菜': '57',
    '豫菜': '58',
    '贛菜': '59', '赣菜': '59',
    '鄂菜': '60',
    '桂菜': '61',
    '瓊菜': '62', '琼菜': '62',
    '貴菜': '63', '贵菜': '63',
    '藏菜': '64',
    
    # 特殊菜式
    '串串香': '20',  # 串串香属于火锅
    '回鍋肉': '6',   # 回锅肉属于川菜
    '冰粉': '34',    # 冰粉属于小吃
}

# 2. 映射价格标签
PRICE_MAPPING = {
    '廉價美食': '45', '廉价美食': '45', '低價': '45', '低价': '45', '$': '45',
    '中價': '42', '中价': '42', '$$': '42', '$$-$$$': '42',
    '高級餐廳': '43', '高级餐厅': '43', '$$$': '43', '$$$-$$$$': '44',
}

# 3. 映射用餐时间标签
MEAL_MAPPING = {
    '早餐': '65',
    '早午餐': '66',  # 早午餐归类为午餐
    '午餐': '66',
    '晚餐': '67',
    '夜宵': '68', '深夜營業': '68', '深夜营业': '68',
    '下午茶': '69',
}

# 4. 映射特色标签
FEATURE_MAPPING = {
    '景觀餐廳': '92', '景观餐厅': '92', '景觀': '92',
    '下午茶': '69',
    '絕佳打卡點': '75', '绝佳打卡点': '75', '打卡': '75',  # 网红餐厅
    '高級餐廳': '77', '高级餐厅': '77',  # 可能是米其林
    '必試美食': '79', '必试美食': '79', '必吃榜': '79',
    '酒吧': '95', '酒館': '95', '酒馆': '95',
    '音樂餐廳': '94', '音乐餐厅': '94',
    '主題餐廳': '93', '主题餐厅': '93',
}

# 5. 映射特殊标签
SPECIAL_MAPPING = {
    '素食友善': '33', '素食': '33',
    '清真食品': '97', '清真': '97',
    '外賣': '84', '外卖': '84',
    '網上預約': '85', '网上预约': '85',  # 堂食
}

CUISINE_CIDS = ['6', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '46', '47', '48', '49', '50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '60', '61', '62', '63', '64']


def _match_tags(tags: List[str], mapping: Dict[str, str], cids: Set[str]):
    """辅助函数：匹配标签列表到映射"""
    for tag in tags:
        # 精确匹配
        if tag in mapping:
            cids.add(mapping[tag])
        # 模糊匹配
        else:
            for key, cid in mapping.items():
                if key in tag or tag in key:
                    cids.add(cid)
                    break

def map_tripcom_tags_to_cids(
    cuisine_tags: List[str] = None,
    price_tags: List[str] = None,
    meal_tags: List[str] = None,
    feature_tags: List[str] = None,
    special_tags: List[str] = None,
    restaurant_name: str = "",
    description: str = ""
) -> str:
    """
    将 Trip.com 标签映射到分类ID
    """
    cuisine_tags = cuisine_tags or []
    price_tags = price_tags or []
    meal_tags = meal_tags or []
    feature_tags = feature_tags or []
    special_tags = special_tags or []
    
    cids = set()
    
    _match_tags(cuisine_tags, CUISINE_MAPPING, cids)
    _match_tags(price_tags, PRICE_MAPPING, cids)
    _match_tags(meal_tags, MEAL_MAPPING, cids)
    _match_tags(feature_tags, FEATURE_MAPPING, cids)
    _match_tags(special_tags, SPECIAL_MAPPING, cids)
    
    # 6. 如果没有匹配到任何菜系分类，使用餐厅名称和描述进行辅助分类
    if not any(cid in cids for cid in CUISINE_CIDS):
        # 使用名称和描述辅助分类
        full_text = f"{restaurant_name} {description}".lower()
        
        # 简单的关键词匹配
        if '火锅' in full_text or '火鍋' in full_text or '串串' in full_text:
            cids.add('20')
        elif '川菜' in full_text or '四川' in full_text or '麻辣' in full_text:
            cids.add('6')
        elif '粤菜' in full_text or '粵菜' in full_text or '广东' in full_text or '廣東' in full_text:
            cids.add('12')
        elif '西餐' in full_text or '西式' in full_text or '牛排' in full_text:
            cids.add('38')
        elif '日料' in full_text or '日本' in full_text or '寿司' in full_text:
            cids.add('14')
        elif '烧烤' in full_text or '燒烤' in full_text or '烤肉' in full_text:
            cids.add('11')
        elif '咖啡' in full_text:
            cids.add('21')
        elif '小吃' in full_text or '小食' in full_text or '快餐' in full_text:
            cids.add('34')
        elif '面' in full_text or '麵' in full_text:
            cids.add('36')
        else:
            # 默认使用特色菜
            cids.add('27')
    
    # 7. 确保至少有一个菜系分类
    if not cids:
        cids.add('27')  # 默认特色菜
    
    # 排序并返回（菜系在前，其他在后）
    cuisine_cids_list = [cid for cid in sorted(cids) if cid in CUISINE_CIDS]
    other_cids_list = [cid for cid in sorted(cids) if cid not in cuisine_cids_list]
    
    result = ','.join(cuisine_cids_list + other_cids_list)
    return result


def generate_cids_from_text(text: str) -> str:
    """
    从文本中生成分类ID列表（通过全文关键词匹配）
    
    Args:
        text: 包含标题、内容、描述的文本
        
    Returns:
        分类ID字符串
    """
    if not text:
        return ""
        
    cids = set()
    text = text.lower()
    
    # 遍历所有映射
    mappings = [CUISINE_MAPPING, PRICE_MAPPING, MEAL_MAPPING, FEATURE_MAPPING, SPECIAL_MAPPING]
    
    for mapping in mappings:
        for key, cid in mapping.items():
            if key in text:
                cids.add(cid)
                
    # 排序并返回
    cuisine_cids_list = [cid for cid in sorted(cids) if cid in CUISINE_CIDS]
    other_cids_list = [cid for cid in sorted(cids) if cid not in cuisine_cids_list]
    
    # 如果没有菜系，添加默认
    if not cuisine_cids_list and not other_cids_list:
        # 再次尝试基本的
        if '火锅' in text or '火鍋' in text: cids.add('20')
        elif '川菜' in text or '四川' in text: cids.add('6')
        elif '粤菜' in text or '广东' in text: cids.add('12')
        elif '西餐' in text: cids.add('38')
        elif '日料' in text or '日本' in text: cids.add('14')
        else:
            cids.add('27') # 特色菜
            
        cuisine_cids_list = [cid for cid in sorted(cids) if cid in CUISINE_CIDS]
        other_cids_list = [cid for cid in sorted(cids) if cid not in cuisine_cids_list]
    
    return ','.join(cuisine_cids_list + other_cids_list)


def extract_tags_from_text(text: str) -> dict:
    """
    从文本中提取标签（简化版，实际应该从HTML中提取）
    """
    tags = {
        'cuisine': [],
        'price': [],
        'meal': [],
        'feature': [],
        'special': []
    }
    return tags
