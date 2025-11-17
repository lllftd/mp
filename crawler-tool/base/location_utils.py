#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
区代码工具模块
提供区代码映射、地址解析等功能
"""
import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_county_code_map: Optional[Dict[str, str]] = None


def _get_county_code_map() -> Dict[str, str]:
    """获取区代码映射（延迟加载，只加载一次）"""
    global _county_code_map
    if _county_code_map is not None:
        return _county_code_map
    
    _county_code_map = {}
    return _county_code_map


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
        _get_county_code_map()
    
    adcode_str = str(adcode).strip()
    if adcode_str and len(adcode_str) == 6:  # 验证adcode格式（6位数字）
        _county_code_map[district_name] = adcode_str
        logger.debug(f"更新区代码映射: {district_name} -> {adcode_str}")
    else:
        logger.warning(f"无效的区代码格式: {adcode} (区县: {district_name})")


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
    
    patterns = [
        r'([^省市区县]+区)',  # 匹配"XX区"
        r'([^省市区县]+县)',  # 匹配"XX县"
        r'([^省市区县]+市)',  # 匹配"XX市"（可能是县级市）
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
        city_name: 城市名称（可选，用于更精确匹配）
        
    Returns:
        区代码（6位数字字符串），如果未找到则返回None
    """
    if not district_name:
        return None
    
    county_map = _get_county_code_map()
    
    # 直接匹配
    if district_name in county_map:
        return county_map[district_name]
    
    # 如果区名包含"区"或"县"，尝试去掉后缀匹配
    district_clean = district_name.replace('区', '').replace('县', '').replace('市', '')
    
    # 尝试匹配：区名 + "区"
    if f"{district_clean}区" in county_map:
        return county_map[f"{district_clean}区"]
    
    # 尝试匹配：区名 + "县"
    if f"{district_clean}县" in county_map:
        return county_map[f"{district_clean}县"]
    
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

