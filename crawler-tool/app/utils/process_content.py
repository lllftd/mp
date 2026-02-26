#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立内容处理脚本 - 处理笔记内容，提取餐厅，AI转述，上传数据库
可以独立运行，也可以与其他模块组合使用
"""
import os
import sys
import logging
import argparse
import random
import json
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.ai_service import get_ai_paraphraser
from app.services.address_service import AddressService
from app.services.tweet_service import prepare_tweet_data, insert_tweet
from base.utils import get_random_username
from base.monitors import MemoryMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_note(title: str, description: str, city: str = "上海", images: List[str] = None, 
                generate_comments: bool = True) -> Dict:
    """
    处理一条小红书笔记，完整流程：提取餐厅 → 转述内容及评论 → 上传数据库
    
    Args:
        title: 餐厅名或笔记标题
        description: 笔记描述
        city: 城市名称（用于地址搜索）
        images: 图片列表（可选）
        generate_comments: 是否生成评论（默认：True）
        
    Returns:
        处理结果统计字典
    """
    ai_paraphraser = get_ai_paraphraser()
    address_service = AddressService()
    
    stats = {
        'total_restaurants': 0,
        'success': 0,
        'failed': 0,
        'comments_generated': 0,
        'errors': []
    }
    
    try:
        logger.info(f"开始处理笔记: {title[:50]}...")
        
        logger.info("步骤1: AI提取场所信息...")
        restaurants = ai_paraphraser.extract_restaurants(title, description)
        
        if not restaurants:
            logger.warning("⚠️  未提取到餐厅信息，跳过该笔记")
            logger.warning(f"   提示：如果笔记包含多家餐厅，请检查AI是否完整提取了所有餐厅")
            stats['errors'].append("未提取到餐厅信息")
            return stats
        
        stats['total_restaurants'] = len(restaurants)
        logger.info(f"✅ 成功提取到 {len(restaurants)} 个餐厅，将逐个处理并上传")
        
        # 步骤2：对每个餐厅进行处理
        for idx, restaurant in enumerate(restaurants, 1):
            restaurant_name = restaurant.get('name', '未知')
            logger.info(f"\n处理餐厅 {idx}/{len(restaurants)}: {restaurant_name}")
            
            try:
                # 2.1 使用高德API搜索餐厅地址
                logger.info(f"  使用高德API搜索餐厅地址: {restaurant_name}")
                address_result = address_service.search_restaurant_address(restaurant_name, city)
                
                if not address_result or not address_result.get('address'):
                    logger.warning(f"  ⚠️  高德API未找到地址，跳过该餐厅")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: 高德API未找到地址")
                    continue
                
                restaurant['address'] = address_result['address']
                city_name = address_result.get('city', city)
                if city_name and city_name.endswith('市'):
                    city_name = city_name[:-1]
                restaurant['city'] = city_name
                restaurant['district'] = address_result.get('district', '')
                restaurant['adcode'] = address_result.get('adcode', '')
                restaurant['province'] = address_result.get('province', '')
                
                logger.info(f"  ✅ 高德API返回地址: {restaurant['address']}")
                
                # 2.2 AI转述内容并生成评论
                logger.info(f"  步骤2: AI转述内容并生成评论...")
                
                paraphrased_title, paraphrased_desc, type_cid, comments = ai_paraphraser.paraphrase_restaurant(
                    restaurant_info=restaurant,
                    original_title=title,
                    original_description=description,
                    tweet_id=None,
                    auto_generate_comments=generate_comments
                )
                
                if not paraphrased_title or not paraphrased_desc or not type_cid:
                    logger.error(f"  ❌ AI转述失败")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: 转述失败")
                    continue
                
                logger.info(f"  ✅ AI转述成功")
                logger.info(f"    生成评论数: {len(comments)} 条")
                stats['comments_generated'] += len(comments)
                
                # 2.3 准备推文数据
                # 根据场所类型动态选择父类型ID
                type_pid = ai_paraphraser.get_parent_type_id(restaurant)
                
                tweet_data = {
                    'tweets_title': restaurant_name,  # 不再限制长度
                    'tweets_content': paraphrased_desc,  # 不再限制长度
                    'tweets_describe': restaurant['address'],  # 不再限制长度
                    'tweets_img': images or [],
                    'tweets_type_pid': type_pid,  # 动态选择父类型ID
                    'tweets_type_cid': type_cid,
                    'tweets_user': get_random_username(),
                    'tweets_location': restaurant['city'],
                    'tweets_location_code': restaurant['adcode'],
                    'like_num': random.randint(10, 500),
                    'collect_num': random.randint(5, 100),
                    'browse_num': random.randint(50, 2000)
                }
                
                try:
                    prepared_data = prepare_tweet_data(tweet_data)
                except ValueError as e:
                    logger.error(f"  ❌ 数据验证失败: {e}")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: {str(e)}")
                    continue
                
                # 2.4 插入推文到数据库
                logger.info(f"  插入推文到数据库...")
                tweet_id = insert_tweet(prepared_data)
                
                if tweet_id:
                    logger.info(f"  ✅ 推文插入成功，ID: {tweet_id}")
                    
                    # 2.5 插入评论到数据库
                    if comments:
                        inserted_count = ai_paraphraser.insert_comments_to_db(tweet_id, comments)
                        logger.info(f"  ✅ 评论插入成功: {inserted_count}/{len(comments)} 条")
                    
                    stats['success'] += 1
                else:
                    logger.error(f"  ❌ 推文插入失败")
                    stats['failed'] += 1
                    stats['errors'].append(f"{restaurant_name}: 推文插入失败")
                    
            except Exception as e:
                logger.error(f"  ❌ 处理餐厅失败: {e}", exc_info=True)
                stats['failed'] += 1
                stats['errors'].append(f"{restaurant_name}: {str(e)}")
        
        return stats
        
    except Exception as e:
        logger.error(f"处理笔记失败: {e}", exc_info=True)
        stats['errors'].append(f"处理笔记失败: {str(e)}")
        return stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='独立内容处理脚本 - 处理笔记内容，提取餐厅，AI转述，上传数据库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理单条笔记
  python3 app/process_content.py --title "餐厅名" --description "笔记描述" --city 上海
  
  # 从文件读取笔记并处理
  python3 app/process_content.py --file notes.json --city 上海
  
  # 处理文件中的笔记，限制数量
  python3 app/process_content.py --file notes.json --city 上海 --limit 10
  
  # 不生成评论（只处理内容）
  python3 app/process_content.py --file notes.json --city 上海 --no-comments
        """
    )
    
    parser.add_argument('--title', type=str, help='餐厅名')
    parser.add_argument('--description', type=str, help='笔记描述')
    parser.add_argument('--city', type=str, default='上海', help='城市名称（默认：上海）')
    parser.add_argument('--images', type=str, nargs='+', help='图片URL列表（空格分隔）')
    parser.add_argument('--file', type=str, help='笔记文件路径（JSON格式，每行一个JSON对象）')
    parser.add_argument('--limit', type=int, help='处理数量限制')
    parser.add_argument('--no-comments', action='store_true', help='不生成评论')
    
    args = parser.parse_args()
    
    try:
        total_stats = {
            'total_notes': 0,
            'total_restaurants': 0,
            'total_success': 0,
            'total_failed': 0,
            'total_comments': 0,
            'all_errors': []
        }
        
        # 启动内存监控
        memory_monitor = MemoryMonitor()
        memory_monitor.start_monitoring()
        
        if args.file:
            # 从文件读取笔记
            logger.info(f"从文件读取笔记: {args.file}")
            
            notes = []
            with open(args.file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        note = json.loads(line)
                        notes.append(note)
                    except json.JSONDecodeError as e:
                        logger.warning(f"第 {line_num} 行JSON解析失败: {e}")
                        continue
            
            if args.limit:
                notes = notes[:args.limit]
            
            logger.info(f"共读取 {len(notes)} 条笔记")
            
            # 处理每条笔记
            for idx, note in enumerate(notes, 1):
                logger.info(f"\n处理笔记 {idx}/{len(notes)}")
                
                title = note.get('title', note.get('tweets_title', ''))
                description = note.get('description', note.get('tweets_content', note.get('content', '')))
                city = note.get('city', note.get('tweets_location', args.city))
                images = note.get('images', note.get('tweets_img', []))
                
                if isinstance(images, str):
                    try:
                        images = json.loads(images)
                    except:
                        images = [images]
                
                if not title or not description:
                    logger.warning(f"笔记 {idx} 缺少标题或描述，跳过")
                    continue
                
                stats = process_note(title, description, city, images, 
                                   generate_comments=not args.no_comments)
                
                total_stats['total_notes'] += 1
                total_stats['total_restaurants'] += stats['total_restaurants']
                total_stats['total_success'] += stats['success']
                total_stats['total_failed'] += stats['failed']
                total_stats['total_comments'] += stats['comments_generated']
                total_stats['all_errors'].extend(stats['errors'])
        
        elif args.title:
            # 处理单条笔记
            if not args.description:
                args.description = args.title
                logger.info("未提供描述，使用标题作为描述")
            
            images = args.images or []
            
            stats = process_note(args.title, args.description, args.city, images,
                               generate_comments=not args.no_comments)
            
            total_stats['total_notes'] = 1
            total_stats['total_restaurants'] = stats['total_restaurants']
            total_stats['total_success'] = stats['success']
            total_stats['total_failed'] = stats['failed']
            total_stats['total_comments'] = stats['comments_generated']
            total_stats['all_errors'] = stats['errors']
        
        else:
            parser.print_help()
            sys.exit(1)
        
        # 打印最终统计
        logger.info("\n处理完成！统计信息：")
        logger.info(f"处理笔记数: {total_stats['total_notes']}")
        logger.info(f"提取餐厅数: {total_stats['total_restaurants']}")
        logger.info(f"成功插入: {total_stats['total_success']}")
        logger.info(f"失败数量: {total_stats['total_failed']}")
        logger.info(f"生成评论数: {total_stats['total_comments']}")
        
        if total_stats['all_errors']:
            logger.warning(f"\n错误列表（共 {len(total_stats['all_errors'])} 个）:")
            for error in total_stats['all_errors'][:10]:
                logger.warning(f"  - {error}")
            if len(total_stats['all_errors']) > 10:
                logger.warning(f"  ... 还有 {len(total_stats['all_errors']) - 10} 个错误未显示")
        
        # 停止内存监控
        try:
            memory_monitor.stop_monitoring()
        except:
            pass
        
    except KeyboardInterrupt:
        logger.info("\n\n程序被用户中断 (Ctrl+C)")
        try:
            memory_monitor.stop_monitoring()
        except:
            pass
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n程序执行出错: {e}", exc_info=True)
        try:
            memory_monitor.stop_monitoring()
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()

