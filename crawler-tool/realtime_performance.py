"""
实时性能监控显示模块
在爬虫运行时实时显示性能指标
"""
import time
import threading
import os
from typing import Optional
from performance_monitor import get_crawler_performance_monitor


class RealTimePerformanceDisplay:
    """实时性能监控显示"""
    
    def __init__(self, update_interval: float = 2.0):
        """
        初始化实时显示
        
        Args:
            update_interval: 更新间隔（秒），默认2秒
        """
        self.update_interval = update_interval
        self.monitor = get_crawler_performance_monitor()
        self.is_running = False
        self.display_thread = None
        self.start_time = None
    
    def format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 0.001:
            return f"{seconds * 1000000:.0f}μs"
        elif seconds < 1:
            return f"{seconds * 1000:.2f}ms"
        else:
            return f"{seconds:.2f}s"
    
    def format_size(self, mb: float) -> str:
        """格式化大小"""
        if mb < 1:
            return f"{mb * 1024:.0f}KB"
        else:
            return f"{mb:.1f}MB"
    
    def clear_screen(self):
        """清屏（使用ANSI转义序列）"""
        # 清屏并移动光标到顶部
        print('\033[2J\033[H', end='', flush=True)
    
    def display_stats(self):
        """显示性能统计"""
        summary = self.monitor.get_summary()
        all_stats = self.monitor.get_all_statistics()
        
        # 计算运行时间
        if self.start_time:
            elapsed = time.time() - self.start_time
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            elapsed_str = f"{elapsed_min}分{elapsed_sec}秒"
        else:
            elapsed_str = "0秒"
        
        # 清屏并显示
        self.clear_screen()
        
        print("="*100)
        print(f"📊 实时性能监控 | 运行时间: {elapsed_str} | 更新时间: {time.strftime('%H:%M:%S')}")
        print("="*100)
        
        # 总体统计
        print(f"\n【总体统计】")
        total_ops = summary.get('total_operations', 0)
        total_time = summary.get('total_time', 0)
        avg_time = summary.get('avg_time_per_operation', 0)
        memory = summary.get('current_memory_mb', 0)
        cpu = summary.get('current_cpu_percent', 0)
        print(f"  总操作数: {total_ops:>6}  |  总耗时: {self.format_duration(total_time):>10}  |  平均耗时: {self.format_duration(avg_time):>10}")
        print(f"  内存使用: {self.format_size(memory):>8}  |  CPU使用率: {cpu:>5.1f}%")
        
        # 爬虫操作统计
        crawl_ops = {k: v for k, v in all_stats.items() if k.startswith('crawl.')}
        if crawl_ops:
            print(f"\n【爬虫操作】")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(crawl_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('crawl.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        # AI操作统计
        ai_ops = {k: v for k, v in all_stats.items() if k.startswith('ai.') and not k.startswith('ai.api_call.attempt_')}
        if ai_ops:
            print(f"\n【AI操作】")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(ai_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('ai.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        # AI成功/失败统计
        ai_success = self.monitor.metrics.get('ai.success', [])
        ai_error = self.monitor.metrics.get('ai.error', [])
        if ai_success or ai_error:
            success_count = len(ai_success)
            error_count = len(ai_error)
            total_ai = success_count + error_count
            if total_ai > 0:
                success_rate = (success_count / total_ai) * 100
                print(f"\n【AI状态】")
                print(f"  成功率: {success_count}/{total_ai} ({success_rate:.1f}%)", end='')
                if error_count > 0:
                    error_types = {}
                    for err in ai_error:
                        err_type = err.get('error_type', 'unknown')
                        error_types[err_type] = error_types.get(err_type, 0) + 1
                    print(f"  |  失败: {error_count}次")
                    if error_types:
                        print(f"  错误类型: {', '.join([f'{k}({v})' for k, v in error_types.items()])}")
                else:
                    print()
        
        # 解析操作统计
        parse_ops = {k: v for k, v in all_stats.items() if k.startswith('parse.')}
        if parse_ops:
            print(f"\n【解析操作】")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(parse_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('parse.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        # 图片处理统计
        image_ops = {k: v for k, v in all_stats.items() if k.startswith('image.')}
        if image_ops:
            print(f"\n【图片处理】")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(image_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('image.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        # 数据库操作统计
        db_ops = {k: v for k, v in all_stats.items() if k.startswith('database.')}
        if db_ops:
            print(f"\n【数据库操作】")
            print(f"  {'操作':<25} {'次数':>6} {'平均耗时':>12} {'上次耗时':>12} {'总耗时':>12}")
            print(f"  {'-'*25} {'-'*6} {'-'*12} {'-'*12} {'-'*12}")
            for op_name, op_stats in sorted(db_ops.items()):
                count = op_stats.get('count', 0)
                avg = op_stats.get('avg_duration', 0)
                last = op_stats.get('last_duration', 0)
                total = op_stats.get('total_duration', 0)
                name_short = op_name.replace('database.', '')[:25]
                print(f"  {name_short:<25} {count:>6} {self.format_duration(avg):>12} {self.format_duration(last):>12} {self.format_duration(total):>12}")
        
        # 显示最新操作（最近10条）
        print(f"\n【最新操作】（最近10条）")
        recent_ops = []
        for op_name, records in self.monitor.metrics.items():
            if records:
                last_record = records[-1]
                # 支持 duration 和 value 字段（CrawlerPerformanceTimer 使用 value）
                duration = last_record.get('duration') or last_record.get('value')
                if duration is not None:
                    recent_ops.append({
                        'name': op_name,
                        'time': last_record.get('timestamp', ''),
                        'duration': duration
                    })
        
        # 按时间排序，显示最近10条
        recent_ops.sort(key=lambda x: x['time'], reverse=True)
        if recent_ops:
            print(f"  {'操作':<35} {'耗时':>12} {'时间':>20}")
            print(f"  {'-'*35} {'-'*12} {'-'*20}")
            for op in recent_ops[:10]:
                name_short = op['name'][:35]
                time_str = op['time'].split('T')[1][:8] if 'T' in op['time'] else op['time'][:8]
                print(f"  {name_short:<35} {self.format_duration(op['duration']):>12} {time_str:>20}")
        
        print("\n" + "="*100)
        print("💡 提示: 性能监控每2秒自动更新 | 按 Ctrl+C 停止爬虫")
        print("="*100)
    
    def _update_loop(self):
        """更新循环（在后台线程中运行）"""
        while self.is_running:
            try:
                self.display_stats()
                time.sleep(self.update_interval)
            except Exception as e:
                # 如果显示出错，继续运行
                pass
    
    def start(self):
        """启动实时显示"""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = time.time()
        self.display_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.display_thread.start()
    
    def stop(self):
        """停止实时显示"""
        self.is_running = False
        if self.display_thread:
            self.display_thread.join(timeout=1)
        # 最后显示一次完整统计
        self.display_stats()
    
    def __enter__(self):
        """上下文管理器：进入"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器：退出"""
        self.stop()
        return False


# 全局实时显示实例
_real_time_display = None

def get_real_time_display(update_interval: float = 2.0) -> RealTimePerformanceDisplay:
    """获取全局实时显示实例"""
    global _real_time_display
    if _real_time_display is None:
        _real_time_display = RealTimePerformanceDisplay(update_interval)
    return _real_time_display

