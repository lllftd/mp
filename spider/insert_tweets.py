import pandas as pd
import pymysql
import json
from datetime import datetime
import random
import paramiko
import time
import subprocess
import sys

# 数据库连接配置
DB_CONFIG = {
    'host': '47.121.133.201',
    'port': 3306,
    'user': 'root',
    'password': 'adminMysql',
    'database': 'jxwq_end',
    'charset': 'utf8mb4',
    'connect_timeout': 10
}

def connect_database():
    """连接数据库"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        print("✅ 数据库连接成功!")
        return connection
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return None

def test_database_connection():
    """测试数据库连接"""
    connection = connect_database()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            connection.close()
            print("✅ 数据库连接测试成功!")
            return True
        except Exception as e:
            print(f"❌ 数据库连接测试失败: {e}")
            connection.close()
            return False
    return False

def restart_mysql():
    """重启MySQL容器 - 改进版本"""
    hostname = '47.121.133.201'
    username = 'root'
    password = 'Dz@2024!'
    
    print("🔌 正在连接服务器...")
    
    try:
        # 方法1: 使用paramiko进行SSH连接
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 设置更长的超时时间
        ssh.connect(hostname, username=username, password=password, timeout=30)
        print("✅ SSH连接成功!")
        
        # 检查Docker是否运行
        print("🔍 检查Docker状态...")
        stdin, stdout, stderr = ssh.exec_command('docker --version')
        docker_version = stdout.read().decode().strip()
        if not docker_version:
            print("❌ Docker未安装或未运行")
            ssh.close()
            return False
        print(f"✅ Docker版本: {docker_version}")
        
        # 检查MySQL容器是否存在
        print("🔍 检查MySQL容器...")
        stdin, stdout, stderr = ssh.exec_command('docker ps -a | grep mysql')
        mysql_container = stdout.read().decode().strip()
        if not mysql_container:
            print("❌ MySQL容器不存在")
            ssh.close()
            return False
        print(f"✅ 找到MySQL容器: {mysql_container}")
        
        # 重启MySQL容器
        print("🔄 重启MySQL容器...")
        stdin, stdout, stderr = ssh.exec_command('docker restart mysql')
        restart_result = stdout.read().decode()
        error_result = stderr.read().decode()
        
        if error_result:
            print(f"⚠️ 重启警告: {error_result}")
        
        print(f"重启结果: {restart_result.strip()}")
        
        # 等待容器启动
        print("⏳ 等待MySQL启动...")
        time.sleep(10)
        
        # 检查容器状态
        print("🔍 检查容器状态...")
        stdin, stdout, stderr = ssh.exec_command('docker ps | grep mysql')
        container_status = stdout.read().decode().strip()
        if container_status:
            print(f"✅ 容器运行状态: {container_status}")
        else:
            print("❌ 容器未运行")
            ssh.close()
            return False
        
        # 测试MySQL连接
        print("🧪 测试MySQL连接...")
        test_command = 'docker exec mysql mysql -u root -padminMysql -e "SELECT 1;" 2>/dev/null'
        stdin, stdout, stderr = ssh.exec_command(test_command)
        mysql_test = stdout.read().decode()
        mysql_error = stderr.read().decode()
        
        if "1" in mysql_test and not mysql_error:
            print("✅ MySQL重启成功!")
            ssh.close()
            return True
        else:
            print(f"❌ MySQL连接测试失败")
            print(f"输出: {mysql_test}")
            print(f"错误: {mysql_error}")
            ssh.close()
            return False
        
    except paramiko.AuthenticationException:
        print("❌ SSH认证失败: 用户名或密码错误")
        return False
    except paramiko.SSHException as e:
        print(f"❌ SSH连接异常: {e}")
        return False
    except Exception as e:
        print(f"❌ SSH连接失败: {e}")
        
        # 尝试使用subprocess作为备选方案
        print("🔄 尝试使用subprocess连接...")
        return restart_mysql_subprocess(hostname, username, password)

def restart_mysql_subprocess(hostname, username, password):
    """使用subprocess重启MySQL - 备选方案"""
    try:
        print("🔌 使用subprocess连接服务器...")
        
        # 测试SSH连接
        test_cmd = f'echo "{password}" | ssh -o StrictHostKeyChecking=no {username}@{hostname} "echo SSH连接成功"'
        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"❌ SSH连接失败: {result.stderr}")
            return False
        
        print("✅ SSH连接成功!")
        
        # 重启MySQL容器
        restart_cmd = f'echo "{password}" | ssh -o StrictHostKeyChecking=no {username}@{hostname} "docker restart mysql"'
        print("🔄 重启MySQL容器...")
        result = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"❌ 重启失败: {result.stderr}")
            return False
        
        print("✅ 重启命令执行成功!")
        
        # 等待启动
        print("⏳ 等待MySQL启动...")
        time.sleep(10)
        
        # 测试连接
        test_cmd = f'echo "{password}" | ssh -o StrictHostKeyChecking=no {username}@{hostname} "docker exec mysql mysql -u root -padminMysql -e \\"SELECT 1;\\""'
        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "1" in result.stdout:
            print("✅ MySQL重启成功!")
            return True
        else:
            print(f"❌ MySQL连接测试失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 操作超时")
        return False
    except Exception as e:
        print(f"❌ subprocess操作失败: {e}")
        return False

def diagnose_mysql_issues():
    """诊断MySQL连接问题"""
    print("🔍 MySQL连接诊断工具")
    print("=" * 50)
    
    # 1. 测试直接数据库连接
    print("\n1. 测试直接数据库连接...")
    if test_database_connection():
        print("✅ 直接数据库连接正常")
        return True
    else:
        print("❌ 直接数据库连接失败")
    
    # 2. 测试SSH连接
    print("\n2. 测试SSH连接...")
    hostname = '47.121.133.201'
    username = 'root'
    password = 'Dz@2024!'
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password, timeout=10)
        print("✅ SSH连接成功")
        
        # 检查Docker状态
        print("\n3. 检查Docker状态...")
        stdin, stdout, stderr = ssh.exec_command('docker --version')
        docker_version = stdout.read().decode().strip()
        if docker_version:
            print(f"✅ Docker已安装: {docker_version}")
        else:
            print("❌ Docker未安装")
            ssh.close()
            return False
        
        # 检查MySQL容器
        print("\n4. 检查MySQL容器...")
        stdin, stdout, stderr = ssh.exec_command('docker ps -a | grep mysql')
        mysql_containers = stdout.read().decode().strip()
        if mysql_containers:
            print(f"✅ MySQL容器存在:\n{mysql_containers}")
        else:
            print("❌ MySQL容器不存在")
            ssh.close()
            return False
        
        # 检查容器状态
        print("\n5. 检查容器运行状态...")
        stdin, stdout, stderr = ssh.exec_command('docker ps | grep mysql')
        running_status = stdout.read().decode().strip()
        if running_status:
            print(f"✅ MySQL容器正在运行:\n{running_status}")
        else:
            print("❌ MySQL容器未运行")
            print("尝试启动容器...")
            stdin, stdout, stderr = ssh.exec_command('docker start mysql')
            start_result = stdout.read().decode().strip()
            print(f"启动结果: {start_result}")
        
        ssh.close()
        return True
        
    except Exception as e:
        print(f"❌ SSH连接失败: {e}")
        return False

def insert_tweets_data():
    """插入推文数据"""
    # 读取CSV文件
    try:
        with open('上海美食完整清理结果2.csv', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"📁 成功读取文件，共{len(lines)}行")
        
        # 解析数据
        data = []
        for line in lines[1:]:  # 跳过标题行
            parts = line.strip().split(',')
            if len(parts) >= 6:
                tweets_type_cid = f"{parts[-2]},{parts[-1]}"
                data.append({
                    '餐厅名字': parts[0],
                    '实际地址': parts[1],
                    '餐厅评价': parts[2],
                    '用户名': parts[3],
                    'tweets_type_cid': tweets_type_cid
                })
        
        df = pd.DataFrame(data)
        print(f"📊 成功解析数据，共{len(df)}条记录")
        
    except Exception as e:
        print(f"❌ 读取CSV文件失败: {e}")
        return
    
    # 连接数据库
    connection = connect_database()
    if not connection:
        print("❌ 数据库连接失败，无法插入数据")
        return
    
    cursor = connection.cursor()
    
    # 插入数据
    success_count = 0
    error_count = 0
    
    for index, row in df.iterrows():
        try:
            # 准备数据
            tweets_type_pid = 5
            tweets_type_cid = str(row['tweets_type_cid']) if pd.notna(row['tweets_type_cid']) else '42'
            tweets_title = row['餐厅名字'][:120] if pd.notna(row['餐厅名字']) else '未知餐厅'
            tweets_user = row['用户名'][:20] if pd.notna(row['用户名']) else '匿名用户'
            tweets_describe = row['实际地址'][:400] if pd.notna(row['实际地址']) else '地址未知'
            tweets_img = json.dumps(["https://example.com/restaurant1.jpg", "https://example.com/restaurant2.jpg"])
            tweets_content = row['餐厅评价'][:2000] if pd.notna(row['餐厅评价']) else '暂无评价'
            
            # 随机生成数据
            like_num = random.randint(0, 100)
            collect_num = random.randint(0, 50)
            browse_num = random.randint(10, 1000)
            create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建SQL语句
            sql = """
            INSERT INTO `tweets` 
            (`tweets_type_pid`, `tweets_type_cid`, `tweets_title`, `tweets_user`, 
             `tweets_describe`, `tweets_img`, `tweets_content`, `like_num`, 
             `collect_num`, `browse_num`, `create_time`, `create_user`, `update_user`) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                tweets_type_pid, tweets_type_cid, tweets_title, tweets_user,
                tweets_describe, tweets_img, tweets_content, like_num,
                collect_num, browse_num, create_time, '1', '1'
            )
            
            cursor.execute(sql, values)
            success_count += 1
            
            if success_count % 10 == 0:
                print(f"📈 已成功插入 {success_count} 条数据...")

            time.sleep(5)

                
        except Exception as e:
            error_count += 1
            print(f"❌ 插入第 {index + 1} 条数据失败: {e}")
    
    # 提交事务
    connection.commit()
    cursor.close()
    connection.close()
    
    print(f"\n🎉 数据插入完成!")
    print(f"✅ 成功插入: {success_count} 条")
    print(f"❌ 失败: {error_count} 条")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            test_database_connection()
        elif sys.argv[1] == '--restart':
            if restart_mysql():
                print("✅ MySQL重启成功，可以尝试连接数据库")
            else:
                print("❌ MySQL重启失败，请检查服务器状态")
        elif sys.argv[1] == '--diagnose':
            diagnose_mysql_issues()
        elif sys.argv[1] == '--help':
            print("""
🚀 数据库管理工具

使用方法:
  python insert_tweets.py          # 插入数据
  python insert_tweets.py --test   # 测试数据库连接
  python insert_tweets.py --restart # 重启MySQL容器
  python insert_tweets.py --diagnose # 诊断MySQL连接问题
  python insert_tweets.py --help   # 显示帮助信息
            """)
        else:
            print(f"❌ 未知参数: {sys.argv[1]}")
            print("使用 --help 查看帮助信息")
    else:
        print("🚀 开始插入深圳美食推文数据...")
        if test_database_connection():
            insert_tweets_data()
        else:
            print("❌ 数据库连接失败，无法插入数据") 