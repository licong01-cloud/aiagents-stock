import os
import psycopg2
import psycopg2.extras as pgx
from dotenv import load_dotenv

def main() -> None:
    load_dotenv(override=True)
    cfg = {
        "host": os.getenv("TDX_DB_HOST", "localhost"),
        "port": int(os.getenv("TDX_DB_PORT", "5432")),
        "user": os.getenv("TDX_DB_USER", "postgres"),
        "password": os.getenv("TDX_DB_PASSWORD", ""),
        "dbname": os.getenv("TDX_DB_NAME", "aistock"),
    }

    with psycopg2.connect(**cfg) as conn:
        conn.autocommit = True
        with conn.cursor(cursor_factory=pgx.RealDictCursor) as cur:
            print("[实时] chunk 压缩状态汇总：")
            cur.execute(
                """
                SELECT is_compressed, COUNT(*) AS cnt
                  FROM timescaledb_information.chunks
                 WHERE hypertable_name = 'kline_daily_raw'
                 GROUP BY is_compressed
                 ORDER BY is_compressed
                """
            )
            rows = cur.fetchall()
            if not rows:
                print("  未查询到 chunk 信息")
            else:
                for row in rows:
                    status = "compressed" if row["is_compressed"] else "uncompressed"
                    print(f"  {status}: {row['cnt']}")

            print("\n[实时] 当前压缩作业（Timescale jobs）状态：")
            cur.execute(
                """
                SELECT jobs.job_id,
                       jobs.last_run_started_at,
                       jobs.last_successful_finish,
                       jobs.next_run_start,
                       jobs.total_runs,
                       jobs.total_successes,
                       jobs.total_failures
                  FROM timescaledb_information.jobs AS jobs
                  JOIN timescaledb_information.hypertables AS hyper
                    ON jobs.hypertable_id = hyper.hypertable_id
                 WHERE hyper.table_name = 'kline_daily_raw'
                """
            )
            jobs = cur.fetchall()
            if not jobs:
                print("  未配置压缩策略作业")
            else:
                for row in jobs:
                    print(
                        (
                            "  job_id={job_id}, last_run={last_run}, last_success={last_success}, "
                            "next_run={next_run}, runs={runs}, success={success}, failures={failures}"
                        ).format(
                            job_id=row["job_id"],
                            last_run=row["last_run_started_at"],
                            last_success=row["last_successful_finish"],
                            next_run=row["next_run_start"],
                            runs=row["total_runs"],
                            success=row["total_successes"],
                            failures=row["total_failures"],
                        )
                    )

    print("\n实时状态查询完成")


if __name__ == "__main__":
    main()
