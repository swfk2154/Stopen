"""Stopen 一键安装脚本（pip 依赖 + 初始化 storage/ 目录）"""
import subprocess, sys, os, shutil
from pathlib import Path

ROOT = Path(__file__).parent


def run_pip(extra_args=None, req_file=None):
    """执行 pip install，可附加额外参数（如 -i 指定源）"""
    cmd = [
        sys.executable, "-m", "pip", "install",
        "-r", str(req_file or ROOT / "requirements.txt"),
    ]
    # --break-system-packages 仅对系统 pip 需要，conda 环境可能不识此参数
    # 加 --isolated 绕过 conda/系统 pip 配置干扰
    cmd.append("--isolated")
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


def check_aiohttp_python_version():
    """检查 Python 版本 — aiohttp>=3.9.0 需 Python>=3.8"""
    py_ver = sys.version_info
    if py_ver < (3, 8):
        print(f"✗ Python {py_ver.major}.{py_ver.minor} 太旧，需要 Python 3.8+")
        return False
    if py_ver >= (3, 13):
        print(f"→ Python 3.13 检测到，aiohttp 可能缺少预编译 wheel")
    return True


def is_kali():
    return os.path.isfile("/etc/os-release") and "kali" in open("/etc/os-release").read().lower()


def try_apt_install():
    """Kali/Debian 上用 apt 安装系统 python3 包"""
    print("\n尝试通过 apt 安装系统包...")
    apt_packages = [
        "python3-fastapi", "python3-uvicorn", "python3-httpx",
        "python3-pydantic", "python3-click", "python3-rich",
        "python3-aiohttp",
    ]
    cmd = ["apt", "install", "-y"] + apt_packages
    result = subprocess.run(
        cmd, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("✓ apt 安装完成")
        return True
    print(f"✗ apt 安装失败: {result.stderr[-300:]}")
    return False


def install_deps():
    print("[1/2] 安装 Python 依赖...")
    check_aiohttp_python_version()

    # 尝试 1: 正常 pip 安装
    result = run_pip()
    if result.returncode == 0:
        print("✓ 依赖安装完成")
        return True

    # pip 失败，收集错误信息
    stderr = result.stderr.lower()
    print(f"✗ pip 安装失败")
    if "no matching distribution" in stderr or "could not find" in stderr:
        print("  原因: pip 找不到匹配的包版本，常见原因:")
        print("    - Python 版本过新，依赖包尚未发布预编译 wheel")
        print("    - pip 源配置问题或网络不通")

    # 尝试 2: 加清华源重试（国内/网络慢场景）
    print("\n→ 尝试清华源...")
    result = run_pip(["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])
    if result.returncode == 0:
        print("✓ 通过清华源安装成功")
        return True

    # 尝试 3: 降级 aiohttp 版本要求再试
    print("\n→ 尝试降低 aiohttp 版本兼容性...")
    temp_req = ROOT / "requirements.tmp"
    with open(ROOT / "requirements.txt") as f:
        lines = f.readlines()
    with open(temp_req, "w") as f:
        for line in lines:
            if line.strip().startswith("aiohttp"):
                f.write("aiohttp>=3.8.0\n")  # 降低版本
            else:
                f.write(line)
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(temp_req), "--isolated"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    temp_req.unlink(missing_ok=True)
    if result.returncode == 0:
        print("✓ 降级 aiohttp 版本后安装成功")
        return True

    # 尝试 4: Kali/Debian 用 apt 安装系统 python3 包
    if is_kali() or shutil.which("apt"):
        print("\n→ 尝试通过 apt 安装系统包...")
        if try_apt_install():
            print("⚠  apt 安装的系统包版本可能较旧，但可运行")
            return True

    # 全部失败，给出手动修复指引
    print("\n" + "=" * 50)
    print("自动安装失败，请手动执行以下任一方案:")
    print("=" * 50)
    print()
    print("方案 1（推荐）- 使用 venv 隔离环境:")
    print(f"  {sys.executable} -m venv .venv")
    print("  source .venv/bin/activate")
    print("  pip install --upgrade pip")
    print("  python install.py")
    print()
    print("方案 2 - 指定 pip 源:")
    print(f"  {sys.executable} -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --break-system-packages")
    print()
    if is_kali():
        print("方案 3 - apt 安装（Kali/Debian）:")
        print("  apt install python3-fastapi python3-uvicorn python3-httpx python3-pydantic python3-click python3-rich python3-aiohttp")
    return False


def build_frontend():
    """npm install + vite build"""
    frontend_dir = ROOT / "stopen" / "frontend"
    if not (frontend_dir / "package.json").is_file():
        return False

    # npm install
    r1 = subprocess.run(["npm", "install"], cwd=str(frontend_dir), capture_output=True, text=True, timeout=120)
    if r1.returncode != 0:
        print(f"  npm install 失败")
        return False

    # vite build
    r2 = subprocess.run(["npx", "vite", "build"], cwd=str(frontend_dir), capture_output=True, text=True, timeout=120)
    if r2.returncode != 0:
        print(f"  vite build 失败")
        return False
    return True


def main():
    print("=" * 50)
    print("Stopen - 自动化渗透测试 Agent")
    print("=" * 50)

    if not install_deps():
        sys.exit(1)

    # 前端构建（如无 dist）
    frontend_dist = ROOT / "stopen" / "frontend" / "dist"
    if not (frontend_dist / "index.html").is_file():
        print("\n[2/3] 构建前端...")
        npm_ok = build_frontend()
        if npm_ok:
            print("✓ 前端构建完成")
        else:
            print("⚠ 前端构建失败，后端将以 API-only 模式运行")
            print("  可手动构建: cd stopen/frontend && npm install && npx vite build")
    else:
        print("\n[2/3] 前端 dist 已存在，跳过构建")

    # 初始化存储目录
    print("\n[3/3] 初始化存储目录...")
    storage_dirs = [
        ROOT / "stopen" / "storage",
        ROOT / "stopen" / "storage" / "logs",
        ROOT / "stopen" / "storage" / "uploads",
    ]
    for d in storage_dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("✓ 存储目录已创建")

    print("\n" + "=" * 50)
    print("安装完成！")
    print()
    print("启动:  python run.py")
    print("访问:  http://127.0.0.1:8080")
    print("=" * 50)


if __name__ == "__main__":
    main()
