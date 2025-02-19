import subprocess
import requests
import os
import platform
import zipfile
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# 配置部分
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")
VERSION = "1.8"

def get_system_info():
    system = "linux"  # GitHub Actions 运行在 Linux 环境
    machine = "amd64"  # GitHub Actions 使用 x64 架构
    return system, machine

def get_download_url(system, arch):
    base_url = f"https://github.com/Ponderfly/GoogleTranslateIpCheck/releases/download/{VERSION}"
    return f"{base_url}/linux-x64.zip"

def download_and_extract():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    
    system, arch = get_system_info()
    
    try:
        download_url = get_download_url(system, arch)
        print(f"正在从 {download_url} 下载...")
        
        zip_path = os.path.join(DOWNLOAD_DIR, f"GoogleTranslateIpCheck_{system}_{arch}.zip")
        response = requests.get(download_url)
        response.raise_for_status()
        
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        print("下载完成！")
        
        if os.path.exists(EXTRACT_DIR):
            import shutil
            shutil.rmtree(EXTRACT_DIR)
        os.makedirs(EXTRACT_DIR)
        
        print("正在解压文件...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        
        print("解压完成！")
        
        executable_name = "GoogleTranslateIpCheck"
        for root, _, files in os.walk(EXTRACT_DIR):
            for file in files:
                if file.lower() == executable_name.lower():
                    return os.path.join(root, file)
        
        raise Exception(f"未找到可执行文件: {executable_name}")
        
    except Exception as e:
        raise Exception(f"下载或解压失败: {e}")

def run_ip_scan():
    try:
        executable_path = download_and_extract()
        print(f"找到可执行文件: {executable_path}")
        
        os.chmod(executable_path, 0o755)
        
        # 使用 -n 参数跳过写入 hosts 文件
        cmd = [executable_path, "-s", "-n"]
        
        print("\n开始扫描IP...")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output = []
        best_ip = None
        hosts_entries = []
        collecting_hosts = False
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.strip()
                print(line)
                output.append(line)
                
                if "translate.googleapis.com" in line:
                    collecting_hosts = True
                    hosts_entries = []
                
                if collecting_hosts and " translate." in line:
                    hosts_entries.append(line.strip())
                    best_ip = line.split()[0]
                
                if collecting_hosts and "translate-pa.googleapis.com" in line:
                    hosts_entries.append(line.strip())
                    best_ip = line.split()[0]
                    collecting_hosts = False
        
        process.wait()
        
        if process.returncode != 0:
            error = process.stderr.read()
            raise Exception(f"扫描出错：{error}")
        
        if not best_ip or not hosts_entries:
            raise Exception("未能获取到有效的IP信息")
        
        return {'hosts_entries': hosts_entries}
        
    except Exception as e:
        raise Exception(f"执行失败: {e}")

def update_gist(content):
    github_token = os.getenv("GITHUB_TOKEN")
    gist_id = os.getenv("GIST_ID")
    
    if not github_token or not gist_id:
        raise Exception("缺少 GitHub Token 或 Gist ID")

    print("\n开始更新 Gist...")    
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {
        "Authorization": f"token {github_token}",
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

def main():
    try:
        scan_result = run_ip_scan()
        if not scan_result:
            return
            
        gist_content = f"""# 最后更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)
# 通过 GitHub Actions 每6小时自动更新一次
# 项目地址：https://github.com/lucky845/GoogleTranslateIpCheck

{chr(10).join(scan_result['hosts_entries'])}"""
        
        gist_info = update_gist(gist_content)
        print("\nGist 更新成功！")
        print(f"访问地址：{gist_info.get('html_url')}")
        print(f"Raw 地址：{gist_info.get('files', {}).get('google_translate_ips.txt', {}).get('raw_url')}")
            
    except Exception as e:
        print(f"错误：{e}")
        exit(1)

if __name__ == "__main__":
    main()