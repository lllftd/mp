#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务队列管理器
支持按顺序执行多个命令行任务
"""
import os
import sys
import json
import logging
import subprocess
import time
from typing import List, Dict, Optional
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def find_python_executable() -> str:
    """
    查找Python可执行文件路径
    优先使用虚拟环境中的Python，否则使用系统Python
    
    Returns:
        Python可执行文件路径
    """
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    
    # 查找虚拟环境
    venv_paths = [
        os.path.join(os.path.dirname(project_root), 'env'),  # 项目根目录的 env
        os.path.join(project_root, 'venv'),  # crawler-tool目录的 venv
        os.path.join(script_dir, '..', '..', 'venv'),  # 其他可能的venv
    ]
    
    for venv_path in venv_paths:
        if os.path.exists(venv_path):
            # Windows
            python_exe = os.path.join(venv_path, 'Scripts', 'python.exe')
            if os.path.exists(python_exe):
                return python_exe
            
            # Linux/Mac
            python_exe = os.path.join(venv_path, 'bin', 'python')
            if os.path.exists(python_exe):
                return python_exe
            
            python_exe = os.path.join(venv_path, 'bin', 'python3')
            if os.path.exists(python_exe):
                return python_exe
    
    # 如果没找到虚拟环境，使用系统Python
    return sys.executable


def get_project_root() -> str:
    """
    获取项目根目录（crawler-tool目录）
    
    Returns:
        项目根目录路径
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(script_dir))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self, tasks: List[Dict], stop_on_error: bool = False, retry_failed: bool = False, max_retries: int = 3):
        """
        初始化任务队列
        
        Args:
            tasks: 任务列表，每个任务包含：
                - name: 任务名称
                - command: 要执行的命令（字符串或列表）
                - args: 命令参数（如果是字符串命令，可以在这里添加参数）
                - cwd: 工作目录（可选）
                - env: 环境变量（可选）
                - timeout: 超时时间（秒，可选）
                - retry: 是否重试（可选，默认False）
                - skip_on_error: 错误时是否跳过（可选，默认False）
            stop_on_error: 遇到错误时是否停止
            retry_failed: 是否重试失败的任务
            max_retries: 最大重试次数
        """
        self.tasks = tasks
        self.stop_on_error = stop_on_error
        self.retry_failed = retry_failed
        self.max_retries = max_retries
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def execute_task(self, task: Dict, task_index: int) -> Dict:
        """
        执行单个任务
        
        Args:
            task: 任务字典
            task_index: 任务索引
            
        Returns:
            执行结果字典
        """
        task_name = task.get('name', f'Task {task_index + 1}')
        command = task.get('command', '')
        args = task.get('args', [])
        cwd = task.get('cwd', None)
        env = task.get('env', None)
        timeout = task.get('timeout', None)
        task_retry = task.get('retry', False)
        skip_on_error = task.get('skip_on_error', False)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"执行任务 {task_index + 1}/{len(self.tasks)}: {task_name}")
        logger.info(f"{'='*60}")
        
        # 构建完整命令
        if isinstance(command, str):
            if args:
                if isinstance(args, list):
                    full_command = [command] + args
                else:
                    full_command = [command, str(args)]
            else:
                # 如果是字符串命令，尝试分割
                full_command = command.split() if ' ' in command else [command]
        elif isinstance(command, list):
            full_command = command + (args if isinstance(args, list) else [str(args)] if args else [])
        else:
            logger.error(f"任务 {task_name} 的命令格式不正确")
            return {
                'task_name': task_name,
                'task_index': task_index,
                'success': False,
                'error': '命令格式不正确',
                'start_time': datetime.now().isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration': 0
            }
        
        # 如果命令是 "python"，替换为虚拟环境中的Python
        if full_command[0].lower() in ['python', 'python3', 'python.exe']:
            python_exe = find_python_executable()
            full_command[0] = python_exe
            logger.debug(f"使用Python解释器: {python_exe}")
        
        # 如果没有指定工作目录，使用项目根目录
        if not cwd:
            cwd = get_project_root()
            logger.debug(f"使用默认工作目录: {cwd}")
        
        logger.info(f"命令: {' '.join(full_command)}")
        logger.info(f"工作目录: {cwd}")
        
        start_time = time.time()
        retry_count = 0
        last_error = None
        
        while retry_count <= (self.max_retries if task_retry else 0):
            try:
                # 准备环境变量
                task_env = os.environ.copy()
                if env:
                    task_env.update(env)
                
                # 设置Python路径，确保能找到项目模块
                python_path = cwd
                if 'PYTHONPATH' in task_env:
                    task_env['PYTHONPATH'] = python_path + os.pathsep + task_env['PYTHONPATH']
                else:
                    task_env['PYTHONPATH'] = python_path
                
                # 执行命令（实时输出日志）
                stdout_lines = []
                stderr_lines = []
                
                process = subprocess.Popen(
                    full_command,
                    cwd=cwd,
                    env=task_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1  # 行缓冲
                )
                
                # 实时读取并输出日志
                import threading
                
                def read_output(pipe, output_list, is_stderr=False):
                    """实时读取输出"""
                    try:
                        for line in iter(pipe.readline, ''):
                            if line:
                                line = line.rstrip('\n\r')
                                output_list.append(line)
                                # 实时输出到控制台
                                if is_stderr:
                                    print(line, file=sys.stderr)
                                else:
                                    print(line)
                    except Exception as e:
                        logger.debug(f"读取输出时出错: {e}")
                    finally:
                        pipe.close()
                
                # 启动线程实时读取输出
                stdout_thread = threading.Thread(
                    target=read_output,
                    args=(process.stdout, stdout_lines, False)
                )
                stderr_thread = threading.Thread(
                    target=read_output,
                    args=(process.stderr, stderr_lines, True)
                )
                
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # 等待进程完成
                try:
                    returncode = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    returncode = -1
                    raise subprocess.TimeoutExpired(full_command[0], timeout)
                
                # 等待输出线程完成
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
                
                stdout_text = '\n'.join(stdout_lines)
                stderr_text = '\n'.join(stderr_lines)
                
                end_time = time.time()
                duration = end_time - start_time
                
                if returncode == 0:
                    logger.info(f"✅ 任务 '{task_name}' 执行成功（耗时: {duration:.2f}秒）")
                    
                    # 任务完成后，清理可能残留的浏览器进程
                    try:
                        from base.browser_cleanup import cleanup_chrome_processes
                        cleanup_chrome_processes()
                    except Exception as e:
                        logger.debug(f"清理浏览器进程时出错: {e}")
                    
                    # 等待一段时间，确保浏览器进程完全关闭
                    logger.debug("等待浏览器进程完全关闭...")
                    time.sleep(3)
                    
                    return {
                        'task_name': task_name,
                        'task_index': task_index,
                        'success': True,
                        'returncode': returncode,
                        'stdout': stdout_text,
                        'stderr': stderr_text,
                        'start_time': datetime.fromtimestamp(start_time).isoformat(),
                        'end_time': datetime.fromtimestamp(end_time).isoformat(),
                        'duration': duration,
                        'retry_count': retry_count
                    }
                else:
                    error_msg = f"命令返回非零退出码: {returncode}"
                    logger.warning(f"❌ 任务 '{task_name}' 执行失败: {error_msg}")
                    if stderr_text:
                        logger.warning(f"错误输出:\n{stderr_text[:500]}")
                    
                    last_error = {
                        'task_name': task_name,
                        'task_index': task_index,
                        'success': False,
                        'returncode': returncode,
                        'error': error_msg,
                        'stdout': stdout_text,
                        'stderr': stderr_text,
                        'start_time': datetime.fromtimestamp(start_time).isoformat(),
                        'end_time': datetime.fromtimestamp(end_time).isoformat(),
                        'duration': time.time() - start_time,
                        'retry_count': retry_count
                    }
                    
                    if skip_on_error:
                        logger.info(f"⚠️  任务 '{task_name}' 配置为跳过错误，继续执行下一个任务")
                        return last_error
                    
                    if task_retry and retry_count < self.max_retries:
                        retry_count += 1
                        wait_time = retry_count * 2  # 递增等待时间
                        logger.info(f"等待 {wait_time} 秒后重试（第 {retry_count}/{self.max_retries} 次）...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return last_error
                        
            except subprocess.TimeoutExpired:
                error_msg = f"任务超时（超时时间: {timeout}秒）"
                logger.error(f"❌ 任务 '{task_name}' {error_msg}")
                last_error = {
                    'task_name': task_name,
                    'task_index': task_index,
                    'success': False,
                    'error': error_msg,
                    'start_time': datetime.fromtimestamp(start_time).isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'duration': time.time() - start_time,
                    'retry_count': retry_count
                }
                
                if skip_on_error:
                    return last_error
                
                if task_retry and retry_count < self.max_retries:
                    retry_count += 1
                    wait_time = retry_count * 2
                    logger.info(f"等待 {wait_time} 秒后重试（第 {retry_count}/{self.max_retries} 次）...")
                    time.sleep(wait_time)
                    continue
                else:
                    return last_error
                    
            except Exception as e:
                error_msg = f"执行任务时发生异常: {str(e)}"
                logger.error(f"❌ 任务 '{task_name}' {error_msg}", exc_info=True)
                last_error = {
                    'task_name': task_name,
                    'task_index': task_index,
                    'success': False,
                    'error': error_msg,
                    'start_time': datetime.fromtimestamp(start_time).isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'duration': time.time() - start_time,
                    'retry_count': retry_count
                }
                
                if skip_on_error:
                    return last_error
                
                if task_retry and retry_count < self.max_retries:
                    retry_count += 1
                    wait_time = retry_count * 2
                    logger.info(f"等待 {wait_time} 秒后重试（第 {retry_count}/{self.max_retries} 次）...")
                    time.sleep(wait_time)
                    continue
                else:
                    return last_error
        
        return last_error
    
    def run(self) -> Dict:
        """
        执行所有任务
        
        Returns:
            执行结果统计
        """
        self.start_time = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"开始执行任务队列，共 {len(self.tasks)} 个任务")
        logger.info(f"{'='*60}\n")
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        for idx, task in enumerate(self.tasks):
            # 在任务开始前，清理可能残留的浏览器进程
            if idx > 0:  # 第一个任务不需要清理
                try:
                    from base.browser_cleanup import cleanup_chrome_processes
                    cleanup_chrome_processes()
                    logger.debug("已清理残留的浏览器进程")
                    time.sleep(2)  # 等待清理完成
                except Exception as e:
                    logger.debug(f"清理浏览器进程时出错: {e}")
            
            result = self.execute_task(task, idx)
            self.results.append(result)
            
            if result['success']:
                success_count += 1
            elif task.get('skip_on_error', False):
                skipped_count += 1
            else:
                failed_count += 1
                
                if self.stop_on_error:
                    logger.error(f"\n遇到错误，停止执行后续任务")
                    break
            
            # 任务之间添加延迟，确保浏览器完全关闭
            if idx < len(self.tasks) - 1:  # 最后一个任务不需要延迟
                delay = 5  # 任务间延迟5秒
                logger.info(f"等待 {delay} 秒后执行下一个任务...")
                time.sleep(delay)
        
        self.end_time = time.time()
        total_duration = self.end_time - self.start_time
        
        # 打印总结
        logger.info(f"\n{'='*60}")
        logger.info(f"任务队列执行完成")
        logger.info(f"{'='*60}")
        logger.info(f"总任务数: {len(self.tasks)}")
        logger.info(f"成功: {success_count}")
        logger.info(f"失败: {failed_count}")
        logger.info(f"跳过: {skipped_count}")
        logger.info(f"总耗时: {total_duration:.2f}秒")
        logger.info(f"{'='*60}\n")
        
        return {
            'total': len(self.tasks),
            'success': success_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'duration': total_duration,
            'results': self.results,
            'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
            'end_time': datetime.fromtimestamp(self.end_time).isoformat()
        }


def load_tasks_from_file(file_path: str) -> List[Dict]:
    """
    从文件加载任务列表
    
    支持格式：
    1. JSON格式：{"tasks": [...]}
    2. JSON数组格式：[...]
    3. 文本格式：每行一个命令
    
    Args:
        file_path: 文件路径
        
    Returns:
        任务列表
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"任务文件不存在: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # 尝试解析JSON
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'tasks' in data:
            return data['tasks']
        elif isinstance(data, dict):
            # 单个任务对象
            return [data]
        else:
            raise ValueError("JSON格式不正确")
    except json.JSONDecodeError:
        # 如果不是JSON，按文本格式处理
        tasks = []
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 解析命令和参数
            parts = line.split()
            if not parts:
                continue
            
            command = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            tasks.append({
                'name': f'任务 {line_num}',
                'command': command,
                'args': args
            })
        
        return tasks


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='任务队列管理器 - 按顺序执行多个命令行任务',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从JSON文件加载任务
  python app/tools/task_queue.py --file tasks.json
  
  # 从文本文件加载任务（每行一个命令）
  python app/tools/task_queue.py --file tasks.txt
  
  # 直接指定任务（JSON格式）
  python app/tools/task_queue.py --tasks '[{"name": "任务1", "command": "python", "args": ["script.py"]}]'
  
  # 遇到错误时停止
  python app/tools/task_queue.py --file tasks.json --stop-on-error
  
  # 重试失败的任务
  python app/tools/task_queue.py --file tasks.json --retry-failed --max-retries 5
        """
    )
    
    parser.add_argument('--file', '-f', type=str, help='任务文件路径（JSON或文本格式）')
    parser.add_argument('--tasks', '-t', type=str, help='任务JSON字符串（直接指定任务）')
    parser.add_argument('--stop-on-error', action='store_true', help='遇到错误时停止执行')
    parser.add_argument('--retry-failed', action='store_true', help='重试失败的任务')
    parser.add_argument('--max-retries', type=int, default=3, help='最大重试次数（默认: 3）')
    parser.add_argument('--output', '-o', type=str, help='结果输出文件路径（JSON格式）')
    
    args = parser.parse_args()
    
    # 加载任务
    if args.file:
        tasks = load_tasks_from_file(args.file)
    elif args.tasks:
        tasks = json.loads(args.tasks)
        if not isinstance(tasks, list):
            tasks = [tasks]
    else:
        parser.print_help()
        sys.exit(1)
    
    if not tasks:
        logger.error("任务列表为空")
        sys.exit(1)
    
    # 创建任务队列并执行
    queue = TaskQueue(
        tasks=tasks,
        stop_on_error=args.stop_on_error,
        retry_failed=args.retry_failed,
        max_retries=args.max_retries
    )
    
    result = queue.run()
    
    # 保存结果
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到: {args.output}")
    
    # 根据执行结果返回退出码
    sys.exit(0 if result['failed'] == 0 else 1)


if __name__ == '__main__':
    main()

