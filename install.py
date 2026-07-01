"""Stopen 一键安装脚本"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    print("=" * 50)
    print("Stopen - 自动化渗透测试 Agent")
    print("=" * 50)

    # 安装 Python 依赖
    print("\n[1/2] 安装 Python 依赖...")
    pip = [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    result = subprocess.run(pip, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"安装失败: {result.stderr}")
        sys.exit(1)
    print("✓ 依赖安装完成")

    # 初始化存储目录
    print("\n[2/2] 初始化存储目录...")
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
