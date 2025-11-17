#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
餐厅地址查询模块 - 使用高德地图API获取餐厅地址（无需爬虫）

也可以作为命令行工具使用，批量更新数据库中的餐厅地址：
    python3 address_service.py [--city 城市名] [--limit 数量] [--dry-run]
"""
import os
import sys
import time
import argparse
import logging
import pandas as pd
from typing import Optional, Dict, Tuple

import requests

# 添加项目根目录到路径（用于命令行模式）
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from base.location_utils import remove_duplicate_city_in_address, extract_city_from_address
from base.database import db

logger = logging.getLogger(__name__)


class AddressService:
    """餐厅地址查询服务（API方式）"""
    
    def __init__(self):
        # 高德地图API配置
        self.amap_api_key = os.getenv('AMAP_API_KEY', '')
        self.amap_api_secret = os.getenv('AMAP_API_SECRET', '')  # 私钥（用于数字签名）
        self.amap_api_enabled = bool(self.amap_api_key)
        
        if not self.amap_api_enabled:
            logger.warning("⚠️  未配置高德地图API密钥，将只能使用AI提取方式")
    
    def search_restaurant_address(self, restaurant_name: str, city: str = "上海") -> Optional[Dict]:
        """
        搜索餐厅地址（使用高德地图API）
        
        Args:
            restaurant_name: 餐厅名称
            city: 城市名称（必需，用于限制搜索范围）
            
        Returns:
            餐厅信息字典，包含 name, address, city, location(lng, lat) 等
        """
        if not restaurant_name or not restaurant_name.strip():
            return None
        
        # 使用高德地图API
        if self.amap_api_enabled:
            result = self._search_amap_api(restaurant_name, city)
            if result and result.get('address'):
                logger.info(f"✅ 通过高德地图API获取到地址: {result.get('address')}")
                return result
        
        # 如果API未配置或失败，返回None（调用方可以使用AI方式）
        logger.debug(f"高德地图API未返回结果，餐厅: {restaurant_name}")
        return None
    
    
    def _search_amap_api(self, restaurant_name: str, city: str) -> Optional[Dict]:
        """使用高德地图API搜索"""
        try:
            url = "https://restapi.amap.com/v3/place/text"
            params = {
                'key': self.amap_api_key,
                'keywords': restaurant_name,
                'city': city,
                'types': '050000',  # 餐饮服务
                'output': 'json',
                'offset': 1,
                'page': 1,
                'extensions': 'all'  # 返回详细信息
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', '')
                info = data.get('info', '')
                
                # 如果返回IP白名单错误，记录但不抛出异常（让调用方回退到爬虫方式）
                if status == '0' and ('INVALID_USER_IP' in info or 'IP' in info or '白名单' in info):
                    logger.warning(f"高德地图API IP白名单错误: {info}，将回退到爬虫方式")
                    return None
                
                # 如果返回平台类型不匹配错误
                if status == '0' and 'USERKEY_PLAT_NOMATCH' in info:
                    logger.warning(f"高德地图API平台类型不匹配: {info}，请检查服务平台设置，将回退到爬虫方式")
                    return None
                
                if status == '1' and data.get('count') != '0':
                    pois = data.get('pois', [])
                    if pois:
                        # 遍历所有结果，找到第一个匹配指定城市的餐厅
                        poi = None
                        for p in pois:
                            cityname = p.get('cityname', '').strip()  # 城市
                            # 检查城市是否匹配（支持"深圳"匹配"深圳市"）
                            city_normalized = city.replace('市', '')  # 去掉"市"后缀
                            cityname_normalized = cityname.replace('市', '')
                            
                            if cityname_normalized == city_normalized or cityname == city:
                                poi = p
                                break
                        
                        # 如果没有找到匹配城市的餐厅，返回None
                        if not poi:
                            logger.debug(f"高德API未找到指定城市({city})的餐厅，返回结果在其他城市")
                            return None
                        
                        # 获取地址组件
                        pname = poi.get('pname', '').strip()  # 省份
                        cityname = poi.get('cityname', '').strip()  # 城市
                        adname = poi.get('adname', '').strip()  # 区县
                        detail_address = poi.get('address', '').strip()  # 详细地址（街道+门牌号）
                        
                        # 构建完整地址：省 + 市 + 区县 + 详细地址
                        # 避免重复（如果详细地址已包含省市信息）
                        address_parts = []
                        
                        # 如果详细地址不包含省名，添加省
                        if pname and pname not in detail_address:
                            address_parts.append(pname)
                        
                        # 如果详细地址不包含市名，添加市
                        # 需要检查多种情况：完整城市名（如"上海市"）和简化城市名（如"上海"）
                        cityname_normalized = cityname.replace('市', '') if cityname else ''
                        if cityname:
                            # 检查详细地址中是否已包含城市名（完整或简化）
                            if cityname not in detail_address and cityname_normalized not in detail_address:
                                address_parts.append(cityname)
                        
                        # 如果详细地址不包含区县名，添加区县
                        if adname and adname not in detail_address:
                            address_parts.append(adname)
                        
                        # 拼接完整地址
                        if address_parts:
                            full_address = ''.join(address_parts) + detail_address
                        else:
                            # 如果详细地址已包含省市信息，直接使用
                            full_address = detail_address
                        
                        # 清理可能的重复城市名（防止出现"上海市上海市"）
                        full_address = remove_duplicate_city_in_address(full_address)
                        
                        # 如果地址为空，使用原始地址字段或至少返回省市区
                        if not full_address or not full_address.strip():
                            fallback_parts = [p for p in [pname, cityname, adname, detail_address] if p]
                            full_address = ''.join(fallback_parts) if fallback_parts else ''
                        
                        # 从高德API返回结果中提取区代码并更新映射
                        adcode = poi.get('adcode', '').strip()
                        if adname and adcode:
                            from base.location_utils import update_county_code_from_amap
                            update_county_code_from_amap(adname, adcode)
                        
                        return {
                            'name': poi.get('name', restaurant_name),
                            'address': full_address.strip(),
                            'city': cityname,  # 城市名（直接使用API返回的cityname）
                            'province': pname,  # 省份
                            'district': adname,  # 区县
                            'adcode': adcode,  # 区代码（高德API返回）
                            'location': {
                                'lng': float(poi.get('location', '0,0').split(',')[0]),
                                'lat': float(poi.get('location', '0,0').split(',')[1])
                            },
                            'tel': poi.get('tel', ''),
                            'type': poi.get('type', ''),
                            'source': 'amap_api'
                        }
        except Exception as e:
            logger.debug(f"高德地图API搜索失败: {e}")
        return None


# 全局单例
_address_service = None


def get_address_service() -> AddressService:
    """获取地址服务实例（单例模式）"""
    global _address_service
    if _address_service is None:
        _address_service = AddressService()
    return _address_service


def extract_address_from_text(text: str, restaurant_name: str = "") -> Optional[str]:
    """
    从文本中提取地址信息（纯AI方式，无需API）
    
    Args:
        text: 包含地址信息的文本
        restaurant_name: 餐厅名称（可选，用于上下文）
        
    Returns:
        提取到的地址字符串，如果未找到则返回None
    """
    if not text:
        return None
    
    # 简单的地址模式匹配（可以作为基础，实际应该用AI提取）
    import re
    
    # 常见的地址模式
    address_patterns = [
        r'地址[：:]\s*([^\n]+)',
        r'位置[：:]\s*([^\n]+)',
        r'([^，。\n]+(?:路|街|道|巷|弄|号|区|市|省)[^，。\n]*)',
        r'([^，。\n]*[区县][^，。\n]*(?:路|街|道)[^，。\n]*)',
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text)
        if match:
            address = match.group(1).strip()
            # 过滤掉太短或明显不是地址的内容
            if len(address) > 5 and '地址' not in address.lower():
                return address
    
    return None


# ==================== 批量更新功能 ====================

def is_address_detailed(address: str) -> bool:
    """
    判断地址是否详细
    
    Args:
        address: 地址字符串
        
    Returns:
        True表示地址详细，False表示需要补充
    """
    if not address or not address.strip():
        return False
    
    address = address.strip()
    
    # 地址太短（少于10个字符）认为不详细
    if len(address) < 10:
        return False
    
    # 检查是否包含地址关键词（省、市、区、路、街、道等）
    address_keywords = ['省', '市', '区', '县', '路', '街', '道', '巷', '弄', '号']
    has_keywords = any(keyword in address for keyword in address_keywords)
    
    if not has_keywords:
        return False
    
    # 如果地址包含"未知"、"暂无"等，认为不详细
    invalid_keywords = ['未知', '暂无', '待补充', '待定']
    if any(keyword in address for keyword in invalid_keywords):
        return False
    
    return True


def needs_update(address: Optional[str], city: Optional[str]) -> Tuple[bool, str]:
    """
    判断是否需要更新地址和城市信息
    
    Args:
        address: 当前地址
        city: 当前城市
        
    Returns:
        (是否需要更新, 原因)
    """
    # 地址为空
    if not address or not address.strip():
        return True, "地址为空"
    
    # 城市为空
    if not city or not city.strip():
        return True, "城市为空"
    
    # 地址不详细
    if not is_address_detailed(address):
        return True, "地址不详细"
    
    # 从地址中提取城市，如果提取不到或与现有城市不一致，可能需要更新
    extracted_city = extract_city_from_address(address)
    if not extracted_city and not city:
        return True, "无法从地址提取城市"
    
    return False, ""


def update_restaurant_address_in_db(
    restaurant_id: int,
    restaurant_name: str,
    current_address: Optional[str],
    current_city: Optional[str],
    search_city: Optional[str] = None,
    dry_run: bool = False,
    update_city: bool = True
) -> Dict:
    """
    更新餐厅地址和城市信息到数据库
    
    Args:
        restaurant_id: 餐厅ID
        restaurant_name: 餐厅名称
        current_address: 当前地址
        current_city: 当前城市
        search_city: 搜索城市（用于高德API，如果为空则使用current_city或从地址提取）
        dry_run: 是否为试运行（不实际更新数据库）
        
    Returns:
        更新结果字典
    """
    try:
        address_service = get_address_service()
        
        # 确定搜索城市
        api_city = search_city or current_city
        if not api_city:
            # 尝试从地址中提取城市
            api_city = extract_city_from_address(current_address) if current_address else None
        
        # 如果仍然没有城市，使用默认城市列表尝试
        if not api_city:
            # 常见城市列表，按顺序尝试
            default_cities = ['上海', '北京', '深圳', '广州', '杭州', '成都', '南京', '武汉', '西安', '重庆']
            api_city = default_cities[0]  # 默认使用第一个城市
            logger.warning(f"餐厅 {restaurant_name} 无法确定城市，使用默认城市: {api_city}")
        
        # 调用高德API获取地址
        logger.info(f"正在查询: {restaurant_name} (城市: {api_city})")
        api_result = address_service.search_restaurant_address(restaurant_name, city=api_city)
        
        if not api_result or not api_result.get('address'):
            return {
                'success': False,
                'reason': '高德API未返回结果',
                'updated': False
            }
        
        new_address = api_result.get('address', '').strip()
        new_city = api_result.get('city', '').strip()
        
        # 如果新地址为空，不更新
        if not new_address:
            return {
                'success': False,
                'reason': 'API返回的地址为空',
                'updated': False
            }
        
        # 去掉城市名中的"市"后缀（如果存在）
        if new_city and new_city.endswith('市'):
            new_city = new_city[:-1]
        
        # 如果地址没有变化，跳过更新
        if new_address == current_address and new_city == current_city:
            return {
                'success': True,
                'reason': '地址和城市已是最新',
                'updated': False,
                'address': new_address,
                'city': new_city
            }
        
        # 更新数据库
        if not dry_run:
            if update_city:
                # 同时更新地址和城市
                update_sql = """
                    UPDATE tweets 
                    SET tweets_describe = :address,
                        tweets_location = :city
                    WHERE id = :id
                """
                params = {
                    'id': restaurant_id,
                    'address': new_address,  # 不再限制长度
                    'city': new_city[:50] if new_city else None  # 限制50字符
                }
            else:
                # 只更新地址
                update_sql = """
                    UPDATE tweets 
                    SET tweets_describe = :address
                    WHERE id = :id
                """
                params = {
                    'id': restaurant_id,
                    'address': new_address[:400]  # 限制400字符
                }
            
            db.execute_update(update_sql, params)
            logger.info(f"✅ 已更新: {restaurant_name}")
            logger.info(f"   地址: {current_address} -> {new_address}")
            if new_city:
                logger.info(f"   城市: {current_city or '无'} -> {new_city}")
        else:
            logger.info(f"[试运行] 将更新: {restaurant_name}")
            logger.info(f"   地址: {current_address} -> {new_address}")
            if new_city:
                logger.info(f"   城市: {current_city or '无'} -> {new_city}")
        
        return {
            'success': True,
            'reason': '更新成功',
            'updated': True,
            'address': new_address,
            'city': new_city,
            'old_address': current_address,
            'old_city': current_city
        }
        
    except Exception as e:
        logger.error(f"更新失败: {restaurant_name} - {e}")
        return {
            'success': False,
            'reason': f'更新异常: {str(e)}',
            'updated': False
        }


def batch_update_addresses(
    city: Optional[str] = None,
    limit: Optional[int] = None,
    search_city: Optional[str] = None,
    dry_run: bool = False,
    update_existing: bool = False,
    tweets_type_pid: Optional[int] = None,
    update_city: bool = True
) -> Dict:
    """
    批量更新数据库中的餐厅地址和城市信息
    
    Args:
        city: 筛选城市（只处理该城市的餐厅）
        limit: 限制处理数量
        search_city: 搜索城市（用于高德API，如果为空则使用餐厅的城市）
        dry_run: 是否为试运行
        update_existing: 是否更新已有地址的记录（False表示只更新空值）
        tweets_type_pid: 推文类型父ID（如果指定，只处理该类型的推文）
        update_city: 是否同时更新城市字段（True表示更新tweets_describe和tweets_location，False表示只更新tweets_describe）
        
    Returns:
        处理结果统计
    """
    try:
        # 查询所有餐厅
        sql = """
            SELECT 
                id,
                tweets_title AS 餐厅名称,
                tweets_describe AS 地址,
                tweets_location AS 城市
            FROM tweets
            WHERE 1=1
        """
        
        params = {}
        
        # 如果指定了推文类型，添加类型筛选条件
        if tweets_type_pid is not None:
            sql += " AND tweets_type_pid = :type_pid"
            params['type_pid'] = tweets_type_pid
        
        # 如果指定了城市，添加城市筛选条件
        if city:
            sql += " AND tweets_location = :city"
            params['city'] = city
        
        # 如果不更新已有地址，只处理空值
        if not update_existing:
            sql += " AND (tweets_describe IS NULL OR tweets_describe = '')"
        
        # 添加排序
        sql += " ORDER BY create_time DESC"
        
        # 如果指定了限制数量
        if limit:
            sql += " LIMIT :limit"
            params['limit'] = limit
        
        logger.info("正在查询餐厅信息...")
        if city:
            logger.info(f"筛选城市: {city}")
        if limit:
            logger.info(f"限制数量: {limit}")
        if dry_run:
            logger.info("⚠️  试运行模式，不会实际更新数据库")
        
        df = db.execute_query(sql, params if params else None)
        
        if df.empty:
            logger.warning("没有找到任何餐厅记录")
            return {
                'total': 0,
                'needs_update': 0,
                'updated': 0,
                'failed': 0,
                'skipped': 0
            }
        
        logger.info(f"✅ 查询完成，共找到 {len(df)} 条餐厅记录")
        
        # 统计信息
        stats = {
            'total': len(df),
            'needs_update': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0
        }
        
        # 处理每条记录
        for idx, row in df.iterrows():
            restaurant_id = row['id']
            restaurant_name = row['餐厅名称']
            current_address = row['地址'] if pd.notna(row['地址']) else None
            current_city = row['城市'] if pd.notna(row['城市']) else None
            
            # 如果 update_existing=False，已经在SQL中过滤了空值，这里不需要再判断
            # 如果 update_existing=True，使用 needs_update 判断是否需要更新
            if update_existing:
                needs, reason = needs_update(current_address, current_city)
                if not needs:
                    logger.debug(f"跳过: {restaurant_name} - {reason if reason else '地址和城市已完整'}")
                    stats['skipped'] += 1
                    continue
                stats['needs_update'] += 1
                logger.info(f"\n[{idx + 1}/{len(df)}] 需要更新: {restaurant_name}")
                logger.info(f"   原因: {reason}")
            else:
                stats['needs_update'] += 1
                logger.info(f"\n[{idx + 1}/{len(df)}] 处理: {restaurant_name}")
            
            logger.info(f"   当前地址: {current_address or '无'}")
            logger.info(f"   当前城市: {current_city or '无'}")
            
            # 更新地址
            result = update_restaurant_address_in_db(
                restaurant_id=restaurant_id,
                restaurant_name=restaurant_name,
                current_address=current_address,
                current_city=current_city,
                search_city=search_city or current_city,
                dry_run=dry_run,
                update_city=update_city
            )
            
            if result['success']:
                if result['updated']:
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1
            else:
                stats['failed'] += 1
            
            # 添加延迟，避免API请求过快
            time.sleep(0.5)
        
        return stats
        
    except Exception as e:
        logger.error(f"处理失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='餐厅地址查询服务（API方式）或批量更新数据库中的餐厅地址',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 批量更新所有餐厅地址（试运行）
  python3 address_service.py --dry-run
  
  # 批量更新所有餐厅地址
  python3 address_service.py
  
  # 只处理特定城市的餐厅
  python3 address_service.py --city 上海
  
  # 限制数量并指定搜索城市
  python3 address_service.py --limit 100 --search-city 深圳
  
  # 更新已有地址的记录（默认只更新空值）
  python3 address_service.py --update-existing
  
  # 只更新地址字段，不更新城市字段
  python3 address_service.py --address-only
  
  # 只处理特定类型的推文
  python3 address_service.py --type-pid 5
        """
    )
    
    parser.add_argument(
        '--city', '-c',
        type=str,
        help='筛选城市（只处理该城市的餐厅，如：上海、深圳、北京）'
    )
    
    parser.add_argument(
        '--search-city', '-s',
        type=str,
        help='搜索城市（用于高德API搜索，如果为空则使用餐厅的城市）'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='限制处理数量'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不会实际更新数据库'
    )
    
    parser.add_argument(
        '--update-existing',
        action='store_true',
        help='更新已有地址的记录（默认：只更新空值）'
    )
    
    parser.add_argument(
        '--type-pid',
        type=int,
        help='推文类型父ID（如果指定，只处理该类型的推文）'
    )
    
    parser.add_argument(
        '--address-only',
        action='store_true',
        help='只更新地址字段，不更新城市字段'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 批量更新地址
        stats = batch_update_addresses(
            city=args.city,
            limit=args.limit,
            search_city=args.search_city,
            dry_run=args.dry_run,
            update_existing=args.update_existing,
            tweets_type_pid=args.type_pid,
            update_city=not args.address_only
        )
        
        # 打印统计信息
        print("\n" + "=" * 80)
        print("处理结果统计")
        print("=" * 80)
        print(f"总记录数: {stats['total']}")
        print(f"需要更新: {stats['needs_update']}")
        print(f"成功更新: {stats['updated']}")
        print(f"更新失败: {stats['failed']}")
        print(f"跳过记录: {stats['skipped']}")
        print("=" * 80)
        
        if args.dry_run:
            print("\n⚠️  这是试运行模式，数据库未实际更新")
            print("   去掉 --dry-run 参数以实际更新数据库")
        
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

