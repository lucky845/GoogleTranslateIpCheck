import subprocess
import requests
import os
import platform
import zipfile
import pexpect
from dotenv import load_dotenv

load_dotenv()

# 1. 配置部分
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
EXTRACT_DIR = os.path.join(BASE_DIR, "extracted")
VERSION = "1.8"  # 当前版本号

# 确定操作系统和架构
def get_system_info():
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "darwin":
        system = "mac"
    if machine in ["x86_64", "amd64"]:
        machine = "amd64"
    elif machine in ["aarch64", "arm64"]:
        machine = "arm64"
    
    return system, machine

def get_download_url(system, arch):
    """根据系统和架构获取下载地址"""
    base_url = f"https://github.com/Ponderfly/GoogleTranslateIpCheck/releases/download/{VERSION}"
    
    if system == "windows":
        # 对于 Windows，特别处理 TurboSyn 版本
        if arch == "amd64":
            if VERSION >= "1.10":
                return f"{base_url}/win-x64.TurboSyn.zip"
            return f"{base_url}/win-x64.zip"
        return f"{base_url}/win-x86.zip"
    elif system == "mac":
        if arch == "arm64":
            return f"{base_url}/osx-arm64.zip"
        return f"{base_url}/osx-x64.zip"
    elif system == "linux":
        if arch == "arm64":
            return f"{base_url}/linux-arm64.zip"
        return f"{base_url}/linux-x64.zip"
    
    raise Exception(f"不支持的系统或架构: {system}-{arch}")

def download_and_extract():
    # 创建必要的目录
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    
    # 获取系统信息
    system, arch = get_system_info()
    
    try:
        download_url = get_download_url(system, arch)
        print(f"正在从 {download_url} 下载...")
        
        # 下载文件，添加进度显示
        zip_path = os.path.join(DOWNLOAD_DIR, f"GoogleTranslateIpCheck_{system}_{arch}.zip")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(zip_path, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for data in response.iter_content(chunk_size=8192):
                    downloaded += len(data)
                    f.write(data)
                    done = int(50 * downloaded / total_size)
                    print(f"\r下载进度: [{'=' * done}{' ' * (50-done)}] {downloaded}/{total_size} 字节", end='')
        print("\n下载完成！")
        
        # 清理解压目录
        print("清理旧文件...")
        if os.path.exists(EXTRACT_DIR):
            for item in os.listdir(EXTRACT_DIR):
                item_path = os.path.join(EXTRACT_DIR, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        import shutil
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"清理文件失败: {e}")
        
        # 解压文件
        print("正在解压文件...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_DIR)
        except zipfile.BadZipFile:
            raise Exception("解压失败：文件可能已损坏，请重试")
        
        print("解压完成！")
        
        # 查找可执行文件
        executable_name = "GoogleTranslateIpCheck"
        if system == "windows":
            executable_name += ".exe"
        
        for root, _, files in os.walk(EXTRACT_DIR):
            for file in files:
                if file.lower() == executable_name.lower():
                    return os.path.join(root, file)
        
        raise Exception(f"在解压目录中未找到可执行文件: {executable_name}")
        
    except Exception as e:
        raise Exception(f"下载或解压失败: {e}")

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
        if platform.system().lower() != "windows":
            cmd = f"{executable_path} -s -n"
        else:
            cmd = f"{executable_path} -s -n"
            
        print("\n开始扫描IP...")
        
        # 使用 pexpect 分配伪终端，模拟真实控制台输入
        child = pexpect.spawn(cmd, encoding="utf-8", timeout=300)
        output = []
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
            output.append(line)
            
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
            'raw_output': "\n".join(output),
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
        raise Exception("缺少 GitHub Token 或 Gist ID，请在 .env 文件中配置")

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
            print("\nGist 更新成功！访问地址：", gist_info.get("html_url"))
            print(f"\nSwitchHosts 远程地址：https://gist.githubusercontent.com/{os.getenv('GITHUB_USERNAME')}/{GIST_ID}/raw")
        except Exception as e:
            print("\n更新 Gist 失败：", e)
            
    except Exception as e:
        print("扫描 IP 出错：", e)

if __name__ == "__main__":
    main()
