"""检查 PostgreSQL 当前锁和等待情况，用于排查 kline_minute_raw 等表是否被锁住。

只执行只读查询，不修改任何业务数据：
1. 输出当前数据库中非 idle 会话（pg_stat_activity）。
2. 输出与关键表相关的锁信息（pg_locks + pg_class + pg_stat_activity）。
3. 输出被阻塞与阻塞它的会话配对信息。
"""
from __future__ import annotations

import json
from typing import Any, Dict

import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

from cleanup_ingestion_meta import _int_from_env, _str_from_env


KEY_TABLES = [
    "kline_minute_raw",
    "ingestion_jobs",
    "ingestion_job_tasks",
    "ingestion_runs",
]


def main() -> None:
    load_dotenv()

    db_cfg: Dict[str, Any] = {
        "host": _str_from_env("TDX_DB_HOST", "localhost"),
        "port": _int_from_env("TDX_DB_PORT", 5432),
        "user": _str_from_env("TDX_DB_USER", "postgres"),
        "password": _str_from_env("TDX_DB_PASSWORD", ""),
        "dbname": _str_from_env("TDX_DB_NAME", "aistock"),
    }
    print("DB config (masked):", {k: ("***" if k == "password" and v else v) for k, v in db_cfg.items()})

    conn = psycopg2.connect(**db_cfg)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=pgx.RealDictCursor)

        # 1) 当前 DB 中所有非 idle 会话
        print("\n== pg_stat_activity (non-idle sessions in this DB) ==")
        cur.execute(
            """
            SELECT pid,
                   usename,
                   state,
                   wait_event_type,
                   wait_event,
                   query_start,
                   NOW() - query_start AS duration,
                   LEFT(query, 200) AS query
              FROM pg_stat_activity
             WHERE datname = current_database()
               AND state <> 'idle'
             ORDER BY query_start
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("(no non-idle sessions)")
        else:
            for r in rows:
                print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        # 2) 与关键表相关的锁
        print("\n== pg_locks on key tables ==")
        cur.execute(
            """
            SELECT
                c.relname,
                l.locktype,
                l.mode,
                l.granted,
                l.pid,
                a.usename,
                a.state,
                a.wait_event_type,
                a.wait_event,
                a.query_start,
                NOW() - a.query_start AS duration,
                LEFT(a.query, 200) AS query
            FROM pg_locks l
            LEFT JOIN pg_class c ON l.relation = c.oid
            LEFT JOIN pg_stat_activity a ON a.pid = l.pid
            WHERE c.relname = ANY(%s)
            ORDER BY c.relname, l.granted DESC, a.query_start
            """,
            (KEY_TABLES,),
        )
        rows = cur.fetchall()
        if not rows:
            print("(no locks on key tables)")
        else:
            for r in rows:
                print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        # 3) 所有被阻塞会话及其阻塞源
        print("\n== blocking / blocked sessions (any relation) ==")
        cur.execute(
            """
            WITH all_locks AS (
                SELECT * FROM pg_locks
            ),
            blocked AS (
                SELECT * FROM all_locks WHERE NOT granted
            ),
            blocking AS (
                SELECT * FROM all_locks WHERE granted
            )
            SELECT
                b.pid               AS blocked_pid,
                a_blocked.usename  AS blocked_user,
                a_blocked.state    AS blocked_state,
                a_blocked.wait_event_type AS blocked_wait_type,
                a_blocked.wait_event      AS blocked_wait_event,
                a_blocked.query_start     AS blocked_query_start,
                NOW() - a_blocked.query_start AS blocked_duration,
                LEFT(a_blocked.query, 200)   AS blocked_query,
                blk.pid             AS blocking_pid,
                a_blocking.usename  AS blocking_user,
                a_blocking.state    AS blocking_state,
                a_blocking.query_start AS blocking_query_start,
                NOW() - a_blocking.query_start AS blocking_duration,
                LEFT(a_blocking.query, 200)  AS blocking_query
            FROM blocked b
            JOIN blocking blk
              ON b.locktype = blk.locktype
             AND b.database IS NOT DISTINCT FROM blk.database
             AND b.relation IS NOT DISTINCT FROM blk.relation
             AND b.page IS NOT DISTINCT FROM blk.page
             AND b.tuple IS NOT DISTINCT FROM blk.tuple
             AND b.virtualxid IS NOT DISTINCT FROM blk.virtualxid
             AND b.transactionid IS NOT DISTINCT FROM blk.transactionid
             AND b.classid IS NOT DISTINCT FROM blk.classid
             AND b.objid IS NOT DISTINCT FROM blk.objid
             AND b.objsubid IS NOT DISTINCT FROM blk.objsubid
             AND b.pid <> blk.pid
            LEFT JOIN pg_stat_activity a_blocked  ON a_blocked.pid  = b.pid
            LEFT JOIN pg_stat_activity a_blocking ON a_blocking.pid = blk.pid
            ORDER BY a_blocked.query_start
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("(no blocked sessions)")
        else:
            for r in rows:
                print(json.dumps({k: str(v) for k, v in r.items()}, ensure_ascii=False))

        cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
