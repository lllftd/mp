import json
import logging
import os
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 行政区划代码数据文件路径
# 数据来源参考：https://github.com/modood/Administrative-divisions-of-China
# 或者高德地图的行政区划代码下载

_county_code_map: Optional[Dict[str, str]] = None
_city_code_map: Optional[Dict[str, str]] = None


def _load_division_data():
    """加载行政区划数据"""
    global _county_code_map, _city_code_map
    
    if _county_code_map is not None:
        return

    _county_code_map = {}
    _city_code_map = {}
    
    # 尝试从本地 JSON 文件加载
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_file = os.path.join(base_dir, 'base', 'data', 'amap_adcodes.json')
    
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 递归处理嵌套结构 (针对 pcas-code.json 格式: [{code, name, children: [...]}, ...])
                def process_items(items):
                    for item in items:
                        name = item.get('name')
                        code = item.get('code')
                        children = item.get('children', [])
                        
                        if name and code:
                            # 城市级别 (通常第3-4位是数字，后面是00，或者是直辖市的区)
                            # 这里简单点：只要有 code 和 name 就都存起来
                            # 如果是区县级别（children为空或者在特定层级），放入 county_map
                            
                            # 放入 city_map (包含省、市)
                            _city_code_map[name] = code
                            if name.endswith('市'):
                                _city_code_map[name[:-1]] = code
                            
                            # 放入 county_map (包含区、县)
                            _county_code_map[name] = code
                            if name.endswith('区') or name.endswith('县'):
                                _county_code_map[name[:-1]] = code
                        
                        # 递归处理子节点
                        if children:
                            process_items(children)

                process_items(data)
                                
            logger.info(f"已加载本地行政区划数据: {len(_county_code_map)} 个条目")
        except Exception as e:
            logger.warning(f"加载行政区划数据失败: {e}")
    else:
        logger.debug("未找到本地行政区划数据文件，将依赖 API 动态学习")


def _get_county_code_map() -> Dict[str, str]:
    """获取区代码映射（延迟加载，只加载一次）"""
    if _county_code_map is None:
        _load_division_data()
    return _county_code_map

def _get_city_code_map() -> Dict[str, str]:
    """获取城市代码映射"""
    if _city_code_map is None:
        _load_division_data()
    return _city_code_map


def update_county_code_from_amap(district_name: str, adcode: str) -> None:
    """
    从高德API返回结果中更新区代码映射
    
    Args:
        district_name: 区县名称（如"南山区"、"黄浦区"）
        adcode: 高德API返回的行政区划代码（6位数字字符串）
    """
    global _county_code_map
    if not district_name or not adcode:
        return
    
    # 确保映射已初始化
    if _county_code_map is None:
        _load_division_data()
    
    adcode_str = str(adcode).strip()
    if adcode_str and len(adcode_str) >= 6: 
        _county_code_map[district_name] = adcode_str
        # 同时存储无后缀版本
        if district_name.endswith('区') or district_name.endswith('县'):
             _county_code_map[district_name[:-1]] = adcode_str
             
        logger.debug(f"更新区代码映射: {district_name} -> {adcode_str}")


def extract_district_from_address(address: str) -> Optional[str]:
    """
    从地址中提取区县名称
    
    Args:
        address: 完整地址字符串
        
    Returns:
        区县名称，如果未找到则返回None
    """
    if not address or not address.strip():
        return None
    
    address = address.strip()
    
    # 优先匹配常见的区县后缀
    patterns = [
        r'([^省市区县]+区)',  # 匹配"XX区"
        r'([^省市区县]+县)',  # 匹配"XX县"
        r'([^省市区县]+市)',  # 匹配"XX市"（可能是县级市）
        r'([^省市区县]+旗)',  # 匹配"XX旗"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, address)
        if matches:
            # 取最后一个匹配（通常地址格式是：省+市+区+详细地址）
            district = matches[-1].strip()
            # 过滤掉太短的匹配
            if len(district) >= 2:
                return district
    
    return None


def find_county_code(district_name: str, city_name: Optional[str] = None) -> Optional[str]:
    """
    根据区县名称查找对应的区代码
    
    Args:
        district_name: 区县名称（如"南山区"、"黄浦区"）
        city_name: 城市名称（可选，用于更精确匹配，暂未深入实现）
        
    Returns:
        区代码（6位数字字符串），如果未找到则返回None
    """
    if not district_name:
        return None
    
    county_map = _get_county_code_map()
    
    # 1. 直接匹配
    if district_name in county_map:
        return county_map[district_name]
    
    # 2. 如果区名包含"区"或"县"，尝试去掉后缀匹配
    district_clean = district_name.replace('区', '').replace('县', '').replace('市', '').replace('旗', '')
    
    if district_clean in county_map:
        return county_map[district_clean]
        
    # 3. 尝试添加后缀匹配
    suffixes = ['区', '县', '市', '旗']
    for suffix in suffixes:
        if f"{district_clean}{suffix}" in county_map:
            return county_map[f"{district_clean}{suffix}"]
    
    return None

def find_city_code(city_name: str) -> Optional[str]:
    """查找城市代码"""
    if not city_name:
        return None
        
    city_map = _get_city_code_map()
    
    if city_name in city_map:
        return city_map[city_name]
        
    city_clean = city_name.replace('市', '')
    if city_clean in city_map:
        return city_map[city_clean]
        
    return None

def extract_city_from_address(address: str) -> Optional[str]:
    if not address:
        return None
    
    address = address.strip()
    
    # 匹配模式：XX市（城市名）
    # 优先匹配"XX市"格式
    pattern = r'([^省市区县]{2,4}市)'
    match = re.search(pattern, address)
    if match:
        city_with_suffix = match.group(1)
        # 去掉"市"后缀，返回城市名
        city_name = city_with_suffix.replace('市', '')
        if len(city_name) >= 2:  # 城市名至少2个字符
            return city_name
    
    return None


def remove_duplicate_city_in_address(address: str) -> str:
    if not address or not address.strip():
        return address
    
    address = address.strip()
    
    # 匹配连续重复的城市名（如"XX市XX市"）
    pattern = r'([^省市区县]{2,4}市)\1'
    address = re.sub(pattern, r'\1', address)
    
    # 匹配连续重复的城市名（不带"市"后缀，如"上海上海"）
    # 注意：这个模式可能会误匹配，所以只在城市名后面跟着"市"、"区"、"县"等时才处理
    pattern = r'([^省市区县]{2,4})(?=\1[市区县])'
    address = re.sub(pattern, '', address, count=1)  # 只替换第一个匹配
    
    return address.strip()
