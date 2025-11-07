from data_source_manager import data_source_manager
from network_optimizer import network_optimizer
import requests

def test_announcements(symbol: str):
    ts_code = data_source_manager._convert_to_ts_code(symbol)
    print(f"ts_code: {ts_code}")
    with network_optimizer.apply():
        df = data_source_manager.tushare_api.anns_d(
            ts_code=ts_code,
            start_date='20250101',
            end_date='20251231',
            limit=10,
            offset=0,
            fields='ts_code,ann_date,ann_type,title,url,pdf_url,file_url,src,adjunct_url,org_id,announcement_id,announcement_type,content'
        )
    if df is None or df.empty:
        print('No announcement data found.')
        return
    print(df[['ann_date','title','pdf_url','file_url','url','src','org_id','announcement_id','announcement_type']])
    for idx, row in df.head(5).iterrows():
        print(f"\n-- Announcement {idx} --")
        for key in ['pdf_url','file_url','url','src','adjunct_url']:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                candidate = value.strip()
                break
        else:
            candidate = None
        print('Candidate URL:', candidate)
        if not candidate:
            continue
        try:
            resp = requests.get(candidate, timeout=20, allow_redirects=True)
            print('Status:', resp.status_code, 'Content-Type:', resp.headers.get('Content-Type'))
            print('Final URL:', resp.url)
            print('Head bytes:', resp.content[:12])
        except Exception as e:
            print('Download failed:', e)

if __name__ == '__main__':
    test_announcements('300073')
