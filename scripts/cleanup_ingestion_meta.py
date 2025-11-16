"""清空 ingestion 元数据表，用于在干净环境下重跑入库任务。

只会清理以下元数据表，不会删除任何行情/业务数据表：
- market.ingestion_job_tasks
- market.ingestion_checkpoints
- market.ingestion_errors
- market.ingestion_runs
- market.ingestion_logs
- market.ingestion_jobs
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg2


def load_dotenv(path: Path) -> None:
    """从 .env 文件加载环境变量（如果存在）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # 不覆盖已经存在的环境变量
        os.environ.setdefault(key, value)


def _int_from_env(name: str, default: int) -> int:
    """从环境变量读取整数，兼容诸如 '"5432"' 这种带引号的写法。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    text = raw.strip().strip("'").strip('"')
    try:
        return int(text)
    except ValueError:
        print(f"WARNING: invalid int for {name}={raw!r}, using default {default}")
        return default


def _str_from_env(name: str, default: str) -> str:
    """从环境变量读取字符串，去掉首尾引号。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    text = raw.strip().strip("'").strip('"')
    return text or default


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    db_cfg = dict(
        host=_str_from_env("TDX_DB_HOST", "localhost"),
        port=_int_from_env("TDX_DB_PORT", 5432),
        user=_str_from_env("TDX_DB_USER", "postgres"),
        password=_str_from_env("TDX_DB_PASSWORD", ""),
        dbname=_str_from_env("TDX_DB_NAME", "aistock"),
    )

    print("Using DB config:", {k: ("***" if k == "password" and v else v) for k, v in db_cfg.items()})

    conn = psycopg2.connect(**db_cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE TABLE "
                "market.ingestion_job_tasks, "
                "market.ingestion_checkpoints, "
                "market.ingestion_errors, "
                "market.ingestion_runs, "
                "market.ingestion_logs, "
                "market.ingestion_jobs;"
            )
        print("Truncated ingestion metadata tables successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
