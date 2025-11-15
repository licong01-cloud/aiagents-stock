#!/usr/bin/env python3
"""
AI股票分析系统启动脚本
运行命令: python run.py
"""

import subprocess
import sys
import os
import time
from urllib.parse import urlparse

from dotenv import load_dotenv


def _start_backend() -> subprocess.Popen | None:
    """启动TDX调度后端（uvicorn），并返回进程对象。"""
    load_dotenv(override=True)
    base = os.getenv("TDX_BACKEND_BASE", "http://127.0.0.1:9000").strip()
    if not base:
        base = "http://127.0.0.1:9000"
    parsed = urlparse(base if "://" in base else f"http://{base}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9000

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "tdx_backend:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    try:
        print(f"🛠️  正在启动调度后端 (uvicorn) -> http://{host}:{port}")
        proc = subprocess.Popen(cmd, env=os.environ.copy())
        time.sleep(1.0)
        if proc.poll() is not None:
            print("⚠️  调度后端进程已退出，请确认端口是否被占用或 uvicorn 是否正常安装。")
            return None
        return proc
    except FileNotFoundError:
        print("⚠️  未找到 uvicorn。请先安装: pip install uvicorn")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  调度后端启动失败: {exc}")
    return None

def check_requirements():
    """检查必要的依赖是否安装"""
    try:
        import streamlit
        import pandas
        import plotly
        import yfinance
        import akshare
        import openai
        print("✅ 所有依赖包已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_config():
    """检查配置文件"""
    try:
        import config
        if not config.DEEPSEEK_API_KEY:
            print("⚠️  警告: DeepSeek API Key 未配置")
            print("请在config.py中设置 DEEPSEEK_API_KEY")
            return False
        print("✅ 配置文件检查通过")
        return True
    except ImportError:
        print("❌ 配置文件config.py不存在")
        return False

def main():
    """主函数"""
    print("🚀 启动AI股票分析系统...")
    print("=" * 50)
    
    # 检查依赖
    if not check_requirements():
        return
    
    # 检查配置
    config_ok = check_config()
    
    # 启动Streamlit应用
    print("🌐 正在启动Web界面...")
    print("📝 访问地址: http://localhost:8503")
    print("⏹️  按 Ctrl+C 停止服务")
    print("=" * 50)
    
    backend_proc = _start_backend()

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8503",
            "--server.address", "127.0.0.1"
        ])
    except KeyboardInterrupt:
        print("\n👋 感谢使用AI股票分析系统！")
    finally:
        if backend_proc:
            print("⏹️  正在关闭调度后端...")
            backend_proc.terminate()
            try:
                backend_proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                backend_proc.kill()

if __name__ == "__main__":
    main()
