"""Ingest a small sample from TDX API into TimescaleDB for validation.
Datasets: codes -> symbol_dim, stock_info, kline_daily_qfq (5d), minute_1m (today or last trading day, small window).
"""
import os
import sys
import json
import time
import datetime as dt
from typing import List, Dict, Any, Optional

import requests
import psycopg2
import psycopg2.extras as pgx
from requests import exceptions as req_exc

TDX_API_BASE = os.getenv('TDX_API_BASE', 'http://localhost:8080')
DB = dict(
    host=os.getenv('TDX_DB_HOST', 'localhost'),
    port=int(os.getenv('TDX_DB_PORT', '5432')),
    user=os.getenv('TDX_DB_USER', 'postgres'),
    password=os.getenv('TDX_DB_PASSWORD', ''),
    dbname=os.getenv('TDX_DB_NAME', 'aistock'),
)

SAMPLE_CODES = [
    '000001',  # 平安银行
    '600000',  # 浦发银行
]


def http_get(path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    url = TDX_API_BASE.rstrip('/') + path
    max_retries = 3
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get('code') != 0:
                raise RuntimeError(f"TDX API error {path}: {data}")
            return data
        except (req_exc.ConnectionError, req_exc.Timeout) as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            time.sleep(1 + attempt)
        except Exception:
            raise
    raise last_exc or RuntimeError(f"TDX API request failed after retries: {url}")


def _to_date(v: Any) -> str | None:
    """Parse date value into 'YYYY-MM-DD'. Accepts date strings, ints, ISO timestamps."""
    if v is None:
        return None
    s = str(v)
    s = s.strip()
    if not s:
        return None
    if 'T' in s:
        try:
            return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).date().isoformat()
        except ValueError:
            pass
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return s
    if len(s) == 8 and s.isdigit():
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return s


def _combine_trade_time(date_hint: str, value: Any) -> str | None:
    """Combine date hint and time field into ISO timestamp with +08:00."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    cleaned = s.replace('Z', '+00:00')
    try:
        dt_obj = dt.datetime.fromisoformat(cleaned)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
        return dt_obj.isoformat()
    except ValueError:
        pass

    base_date = _to_date(date_hint)
    if not base_date:
        return None
    try:
        trade_date = dt.date.fromisoformat(base_date)
    except ValueError:
        return None

    time_obj = None
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            time_obj = dt.datetime.strptime(s, fmt).time()
            break
        except ValueError:
            continue
    if time_obj is None:
        return None

    tzinfo = dt.timezone(dt.timedelta(hours=8))
    combined = dt.datetime.combine(trade_date, time_obj).replace(tzinfo=tzinfo)
    return combined.isoformat()


def fetch_codes() -> List[Dict[str, Any]]:
    data = http_get('/api/codes')
    if data.get('code') != 0:
        raise RuntimeError(f"codes api error: {data}")
    return data.get('data', [])


def split_ts_code(ts_code: str):
    if not ts_code or '.' not in ts_code:
        return ts_code, None
    code, exch = ts_code.split('.', 1)
    return code, exch.upper()


def fetch_stock_info(code: str) -> Dict[str, Any]:
    # API 期望 6 位 code
    resp = http_get('/api/stock-info', params={'code': code})
    if resp.get('code') != 0:
        raise RuntimeError(f"stock-info api error: {code}: {resp}")
    return resp.get('data', {})


def fetch_kline_daily_qfq(code: str, start: str, end: str) -> List[Dict[str, Any]]:
    resp = http_get('/api/kline', params={'code': code, 'type': 'day', 'adjust': 'qfq', 'start': start, 'end': end})
    if resp.get('code') != 0:
        raise RuntimeError(f"kline api error: {code}: {resp}")
    data = resp.get('data')
    # 兼容 List/list 包裹
    if isinstance(data, dict):
        items = data.get('List') or data.get('list') or []
    else:
        items = data or []
    return list(items)


def fetch_minute_1m(code: str, date: str) -> List[Dict[str, Any]]:
    resp = http_get('/api/minute', params={'code': code, 'type': 'minute1', 'date': date})
    if resp.get('code') != 0:
        raise RuntimeError(f"minute api error: {code}: {resp}")
    data = resp.get('data')
    # 兼容多层嵌套
    if isinstance(data, dict):
        items = data.get('List') or data.get('list') or data
        if isinstance(items, dict):
            items = items.get('List') or items.get('list') or []
    else:
        items = data or []
    return list(items)


def upsert_symbol_dim(conn, rows: List[Dict[str, Any]]):
    sql = (
        "INSERT INTO market.symbol_dim (ts_code, symbol, exchange, name, industry, list_date) "
        "VALUES %s ON CONFLICT (ts_code) DO UPDATE SET "
        "symbol=EXCLUDED.symbol, exchange=EXCLUDED.exchange, name=EXCLUDED.name, industry=EXCLUDED.industry, list_date=EXCLUDED.list_date"
    )
    values = []
    for r in rows:
        ts_code = r.get('ts_code') or r.get('code')
        symbol = ts_code.split('.')[0] if ts_code else None
        exch = ts_code.split('.')[1] if ts_code else ''
        exchange = {'SZ':'SZ','SH':'SH','BJ':'BJ'}.get(exch.upper(), 'SZ')
        name = r.get('name')
        industry = r.get('industry')
        list_date = r.get('list_date')
        values.append((ts_code, symbol, exchange, name, industry, list_date))
    if not values:
        print("[WARN] no symbol_dim rows mapped")
        return 0
    with conn.cursor() as cur:
        pgx.execute_values(cur, sql, values)
    return len(values)


def upsert_stock_info(conn, rows: List[Dict[str, Any]]):
    sql = (
        "INSERT INTO market.stock_info (ts_code, name, industry, market, area, list_date, ext_json, updated_at) "
        "VALUES %s ON CONFLICT (ts_code) DO UPDATE SET "
        "name=EXCLUDED.name, industry=EXCLUDED.industry, market=EXCLUDED.market, area=EXCLUDED.area, list_date=EXCLUDED.list_date, ext_json=EXCLUDED.ext_json, updated_at=NOW()"
    )
    values = []
    for r in rows:
        ts_code = r.get('ts_code') or r.get('code')
        values.append((
            ts_code,
            r.get('name'),
            r.get('industry'),
            r.get('market'),
            r.get('area'),
            r.get('list_date'),
            json.dumps(r, ensure_ascii=False),
            dt.datetime.now(dt.timezone.utc),
        ))
    with conn.cursor() as cur:
        pgx.execute_values(cur, sql, values)


def upsert_kline_daily_qfq(conn, ts_code: str, bars: List[Dict[str, Any]]):
    sql = (
        "INSERT INTO market.kline_daily_qfq (trade_date, ts_code, open_li, high_li, low_li, close_li, volume_hand, amount_li, adjust_type, source) "
        "VALUES %s ON CONFLICT (ts_code, trade_date) DO UPDATE SET "
        "open_li=EXCLUDED.open_li, high_li=EXCLUDED.high_li, low_li=EXCLUDED.low_li, close_li=EXCLUDED.close_li, volume_hand=EXCLUDED.volume_hand, amount_li=EXCLUDED.amount_li"
    )
    values = []
    for b in bars:
        # 兼容大小写键名：Date/Open/High/Low/Close/Volume/Amount
        trade_date = _to_date(b.get('Date') or b.get('date') or b.get('Time') or b.get('time'))
        open_li = b.get('Open') or b.get('open')
        high_li = b.get('High') or b.get('high')
        low_li = b.get('Low') or b.get('low')
        close_li = b.get('Close') or b.get('close')
        volume_hand = b.get('Volume') or b.get('volume') or 0
        amount_li = b.get('Amount') or b.get('amount') or 0
        if trade_date is None or open_li is None or high_li is None or low_li is None or close_li is None:
            continue
        values.append((trade_date, ts_code, open_li, high_li, low_li, close_li, volume_hand, amount_li, 'qfq', 'tdx_api'))
    if not values:
        print(f"[WARN] no mapped daily rows for {ts_code}; example_raw={bars[:1]}")
        return 0
    with conn.cursor() as cur:
        try:
            pgx.execute_values(cur, sql, values)
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] daily upsert failed for {ts_code}: {e}")
            raise
    return len(values)


def upsert_minute_1m(conn, ts_code: str, bars: List[Dict[str, Any]], trade_date_hint: str):
    sql = (
        "INSERT INTO market.kline_minute_raw (trade_time, ts_code, freq, open_li, high_li, low_li, close_li, volume_hand, amount_li, adjust_type, source) "
        "VALUES %s ON CONFLICT (ts_code, trade_time, freq) DO UPDATE SET "
        "open_li=EXCLUDED.open_li, high_li=EXCLUDED.high_li, low_li=EXCLUDED.low_li, close_li=EXCLUDED.close_li, volume_hand=EXCLUDED.volume_hand, amount_li=EXCLUDED.amount_li"
    )
    values = []
    for b in bars:
        # 兼容大小写键名：Time/Open/High/Low/Close/Volume/Amount 或 Price（仅价格）
        trade_time = b.get('TradeTime') or b.get('trade_time')
        if trade_time is None:
            trade_time = b.get('Time') or b.get('time')
        trade_time_iso = _combine_trade_time(trade_date_hint, trade_time)
        open_li = b.get('Open') or b.get('open')
        high_li = b.get('High') or b.get('high')
        low_li = b.get('Low') or b.get('low')
        close_li = b.get('Close') or b.get('close') or b.get('Price') or b.get('price')
        volume_hand = b.get('Volume') or b.get('volume') or 0
        amount_li = b.get('Amount') or b.get('amount') or 0
        if trade_time_iso is None:
            continue
        values.append((trade_time_iso, ts_code, '1m', open_li, high_li, low_li, close_li, volume_hand, amount_li, 'none', 'tdx_api'))
    if not values:
        print(f"[WARN] no mapped minute rows for {ts_code}; example_raw={bars[:1]}")
        return 0
    with conn.cursor() as cur:
        try:
            pgx.execute_values(cur, sql, values)
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] minute upsert failed for {ts_code}: {e}")
            raise
    return len(values)


def previous_trading_day(date: dt.date) -> dt.date:
    # 简化：若是周末退回到周五
    while date.weekday() >= 5:
        date -= dt.timedelta(days=1)
    return date


def main():
    today = dt.date.today()
    start_day = today - dt.timedelta(days=10)
    start = start_day.strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')

    # 分别取样本代码的基本信息与行情
    code_rows = []
    stock_info_rows = []

    # 如果 /api/codes 可用，获取并筛选 SAMPLE_CODES（可能需要映射成 ts_code）
    try:
        codes = fetch_codes()
        sample = []
        for c in codes:
            code = c.get('code') or c.get('Code') or ''
            if code in SAMPLE_CODES:
                sample.append({'ts_code': f"{code}.SH" if code.startswith('6') else f"{code}.SZ", 'name': c.get('name') or c.get('Name')})
        if sample:
            code_rows.extend(sample)
    except Exception:
        pass

    # 补充确保 SAMPLE_CODES 都有记录
    for code in SAMPLE_CODES:
        try:
            info = fetch_stock_info(code)
            if info:
                # 拼 symbol_dim 行
                sd = {
                    'ts_code': f"{code}.SH" if code.startswith('6') else f"{code}.SZ",
                    'name': info.get('name'),
                    'industry': info.get('industry'),
                    'list_date': info.get('list_date'),
                }
                code_rows.append(sd)
                # 丰富 stock_info，确保 ts_code 可用
                enriched = dict(info)
                enriched['ts_code'] = sd['ts_code']
                stock_info_rows.append(enriched)
        except Exception as e:
            print(f"[WARN] stock-info fail {code}: {e}")

    with psycopg2.connect(**DB) as conn:
        conn.autocommit = True
        if code_rows:
            upsert_symbol_dim(conn, code_rows)
            print(f"[OK] symbol_dim upsert: {len(code_rows)}")
        if stock_info_rows:
            upsert_stock_info(conn, stock_info_rows)
            print(f"[OK] stock_info upsert: {len(stock_info_rows)}")

        for code in SAMPLE_CODES:
            ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            try:
                daily = fetch_kline_daily_qfq(code, start, end)
                inserted = upsert_kline_daily_qfq(conn, ts_code, daily)
                print(f"[OK] kline_daily_qfq upsert: {code} inserted={inserted} src={len(daily)}")
            except Exception as e:
                print(f"[WARN] daily kline fail {code}: {e}")

            # 分钟数据取上一交易日，避免非交易日
            d = previous_trading_day(today)
            date_param = d.strftime('%Y%m%d')
            try:
                minute = fetch_minute_1m(code, date_param)
                # 仅取前 60 条样本（如果是列表）
                if isinstance(minute, list):
                    minute = minute[:60]
                inserted_m = upsert_minute_1m(conn, ts_code, minute, date_param)
                count = len(minute) if isinstance(minute, list) else 0
                print(f"[OK] minute_1m upsert: {code} inserted={inserted_m} src={count} ({date_param})")
            except Exception as e:
                print(f"[WARN] minute fail {code}: {e}")

    print("[DONE] small sample ingestion finished.")


if __name__ == '__main__':
    main()
