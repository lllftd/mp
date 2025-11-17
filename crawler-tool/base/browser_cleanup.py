#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器进程清理工具
用于清理DrissionPage遗留的Chrome进程
"""
import os
import sys
import subprocess
import logging
import signal
import atexit

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_chrome_processes(port: int = None):
    """
    清理Chrome进程
    
    Args:
        port: 如果指定端口，只清理该端口的进程；否则清理所有DrissionPage相关的Chrome进程
    """
    try:
        if port:
            # 清理指定端口的进程
            cmd = f"ps aux | grep 'remote-debugging-port={port}' | grep -v grep | awk '{{print $2}}' | xargs kill -9 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                logger.info(f"已清理端口 {port} 的Chrome进程")
            else:
                logger.debug(f"端口 {port} 没有Chrome进程")
        else:
            # 清理所有DrissionPage相关的Chrome进程
            cmd = "ps aux | grep 'remote-debugging-port' | grep -v grep | awk '{print $2}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                logger.info(f"发现 {len(pids)} 个Chrome进程，正在清理...")
                
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True, capture_output=True, timeout=2)
                        logger.debug(f"已清理进程 PID: {pid}")
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        pass
                
                logger.info(f"✅ 已清理 {len(pids)} 个Chrome进程")
            else:
                logger.debug("没有发现需要清理的Chrome进程")
    except Exception as e:
        logger.error(f"清理Chrome进程失败: {e}")


def cleanup_drissionpage_processes():
    """清理所有DrissionPage相关的Chrome进程"""
    cleanup_chrome_processes()


def safe_close_browser(page, port: int = None):
    """
    安全关闭浏览器，确保进程被清理
    
    Args:
        page: ChromiumPage实例
        port: 浏览器调试端口（可选）
    """
    if not page:
        return
    
    try:
        # 方法1: 使用page.close()
        try:
            page.close()
            logger.debug("使用page.close()关闭浏览器")
        except:
            pass
        
        # 方法2: 使用browser.close()
        try:
            if hasattr(page, 'browser') and hasattr(page.browser, 'close'):
                page.browser.close()
                logger.debug("使用browser.close()关闭浏览器")
        except:
            pass
        
        # 方法3: 强制清理进程（如果提供了端口）
        if port:
            cleanup_chrome_processes(port)
        
        # 等待一下，确保进程关闭
        import time
        time.sleep(0.5)
        
    except Exception as e:
        logger.warning(f"关闭浏览器时出错: {e}")
        # 最后尝试：强制清理
        if port:
            cleanup_chrome_processes(port)


# 注册退出时的清理函数
def register_cleanup_on_exit(port: int = None):
    """注册退出时的清理函数"""
    def cleanup():
        cleanup_chrome_processes(port)
    atexit.register(cleanup)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='清理Chrome进程')
    parser.add_argument('--port', type=int, help='指定端口号（可选）')
    args = parser.parse_args()
    
    cleanup_chrome_processes(args.port)


