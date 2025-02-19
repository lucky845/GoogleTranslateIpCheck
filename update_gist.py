import subprocess
import requests
import os
import platform
import zipfile
import pexpect

from local_update_gist import download_and_extract

# 1. 配置部分
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")
VERSION = "1.8"  # 当前版本号

# 2. 调用 GoogleTranslateIpCheck 扫描 IP
def run_ip_scan():
    try:
        # 下载并解压最新版本
        executable_path = download_and_extract()
        print(f"找到可执行文件: {executable_path}")
        
        # 设置执行权限（非 Windows 系统）
        if platform.system().lower() != "windows":
            try:
                os.chmod(executable_path, 0o755)
            except Exception as e:
                raise Exception(f"设置执行权限失败: {e}")
    
        # 构建执行命令
        cmd = f"{executable_path} -s -n"
            
        print("\n开始扫描IP...")
        
        # 使用 pexpect 分配伪终端，模拟真实控制台输入
        child = pexpect.spawn(cmd, encoding="utf-8", timeout=300)
        best_ip = None
        hosts_entries = []
        collecting_hosts = False
        
        while True:
            try:
                line = child.readline().strip()
            except pexpect.EOF:
                break
            if not line:
                if child.eof():
                    break
                continue
            print(line)
            
            # 当发现 hosts 条目时开始收集
            if "translate.googleapis.com" in line:
                collecting_hosts = True
                hosts_entries = []
            
            # 收集 hosts 条目
            if collecting_hosts and " translate." in line:
                hosts_entries.append(line)
                best_ip = line.split()[0]
            
            # 当发现 hosts 条目结束时停止收集
            if collecting_hosts and "translate-pa.googleapis.com" in line:
                hosts_entries.append(line)
                best_ip = line.split()[0]
                collecting_hosts = False
            
            # 当出现询问是否需要写入hosts时自动输入 n
            if "是否设置到Host文件" in line:
                print("已自动选择不写入hosts")
                child.sendline("n")
        
        child.expect(pexpect.EOF)
        child.close()
        
        if child.exitstatus != 0:
            raise Exception(f"扫描出错，退出码：{child.exitstatus}")
        
        if not best_ip or not hosts_entries:
            raise Exception("未能获取到有效的IP信息")
        
        result = {
            'best_ip': best_ip,
            'hosts_entries': hosts_entries
        }
        
        return result
    except Exception as e:
        raise Exception(f"执行失败: {e}")

# 3. 更新 GitHub Gist
def update_gist(content):
    """更新或创建 GitHub Gist"""
    # 从系统环境变量获取（GitHub Actions 会传入这些变量）
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GIST_ID = os.getenv("GIST_ID")

    if not GITHUB_TOKEN or not GIST_ID:
        raise Exception("缺少 GitHub Token 或 Gist ID, 请在项目环境变量配置")

    print("\n开始更新 Gist...")    
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "files": {
            "google_translate_ips.txt": {
                "content": content
            }
        }
    }
    
    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"更新 Gist 失败: {str(e)}")

# 4. 主流程
def main():
    try:
        scan_result = run_ip_scan()
        if not scan_result:
            return
            
        try:
            from datetime import datetime
            gist_content = f"""# 最后更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)
# 通过 GitHub Actions 每6小时自动更新一次
# 项目地址：https://github.com/lucky845/GoogleTranslateIpCheck

{chr(10).join(scan_result['hosts_entries'])}"""
            
            gist_info = update_gist(gist_content)
            print("\nGist 更新成功！")
        except Exception as e:
            print("\n更新 Gist 失败：", e)
            
    except Exception as e:
        print("扫描 IP 出错：", e)

if __name__ == "__main__":
    main()
