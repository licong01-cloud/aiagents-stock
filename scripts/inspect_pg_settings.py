from __future__ import annotations
import os
import psycopg2

PARAMS = [
    'shared_buffers','work_mem','maintenance_work_mem','effective_cache_size',
    'max_connections','wal_level','checkpoint_timeout','max_wal_size','min_wal_size',
    'synchronous_commit','random_page_cost','effective_io_concurrency','autovacuum',
    'autovacuum_vacuum_cost_limit','autovacuum_vacuum_cost_delay',
    'timescaledb.max_background_workers','timescaledb.max_chunks_per_job',
    'timescaledb.enable_transparent_decompression','timescaledb.last_tuned',
]

def main() -> None:
    cfg = dict(
        host=os.getenv('TDX_DB_HOST', 'localhost'),
        port=int(os.getenv('TDX_DB_PORT', '5432')),
        dbname=os.getenv('TDX_DB_NAME', 'aistock'),
        user=os.getenv('TDX_DB_USER', 'postgres'),
        password=os.getenv('TDX_DB_PASSWORD', ''),
    )
    with psycopg2.connect(**cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, setting, COALESCE(unit,''), short_desc
                  FROM pg_settings
                 WHERE name = ANY(%s)
                 ORDER BY name
                """,
                (PARAMS,)
            )
            rows = cur.fetchall()
    for name, setting, unit, desc in rows:
        print(f"{name}={setting}{unit} // {desc}")

if __name__ == '__main__':
    main()
