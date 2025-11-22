# 上市公司公告数据获取API文档

## 概述

本文档基于Go股票开发程序的分析，详细介绍了如何通过东方财富API获取上市公司公告数据，包括API接口、数据格式、请求参数以及Python实现方案。

## 1. API接口信息

### 1.1 公告数据查询API

**接口地址**: `https://np-anotice-stock.eastmoney.com/api/security/ann`

**请求方法**: GET

**功能**: 获取指定股票的公告列表

### 1.2 PDF下载API

**接口地址**: `https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf`

**请求方法**: GET

**功能**: 下载公告PDF文件

## 2. 请求参数详解

### 2.1 查询参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| page_size | int | 否 | 50 | 每页返回的公告数量 |
| page_index | int | 否 | 1 | 页码，从1开始 |
| ann_type | string | 否 | SHA,CYB,SZA,BJA,INV | 公告类型 |
| client_source | string | 否 | web | 客户端来源 |
| f_node | int | 否 | 0 | 节点标识 |
| stock_list | string | 是 | - | 股票代码列表，逗号分隔 |

### 2.2 公告类型说明

| 类型代码 | 说明 |
|----------|------|
| SHA | 上海A股公告 |
| CYB | 创业板公告 |
| SZA | 深圳A股公告 |
| BJA | 北京A股公告 |
| INV | 投资公告 |

### 2.3 股票代码处理规则

程序会自动处理以下股票代码格式：

- 移除市场前缀：`sh`、`sz`、`gb_`、`us`、`us_`
- 处理带点号的代码：如`000001.SZ` → `000001`
- 支持批量查询：多个代码用逗号分隔

## 3. 请求头设置

### 3.1 必需请求头

```http
Host: np-anotice-stock.eastmoney.com
Referer: https://data.eastmoney.com/notices/hsa/5.html
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0
```

### 3.2 请求超时设置

建议设置15秒超时时间，避免长时间等待。

## 4. 响应数据格式

### 4.1 响应结构

```json
{
  "data": {
    "list": [
      {
        "art_code": "公告唯一标识码",
        "title": "公告标题",
        "notice_date": "公告日期",
        "columns": [
          {
            "column_name": "公告类型名称"
          }
        ],
        "codes": [
          {
            "stock_code": "股票代码",
            "short_name": "股票简称",
            "market_code": "市场代码"
          }
        ]
      }
    ]
  }
}
```

### 4.2 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| art_code | string | 公告唯一标识码，用于构建PDF下载链接 |
| title | string | 公告标题 |
| notice_date | string | 公告发布日期 |
| columns[].column_name | string | 公告类型名称 |
| codes[].stock_code | string | 股票代码 |
| codes[].short_name | string | 股票简称 |
| codes[].market_code | string | 市场代码 |

## 5. Python实现方案

### 5.1 基础实现类

```python
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

class StockNoticeAPI:
    """上市公司公告数据获取API"""
    
    def __init__(self, timeout: int = 15):
        """
        初始化API客户端
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.base_url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        self.pdf_base_url = "https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf"
        self.timeout = timeout
        
        self.headers = {
            "Host": "np-anotice-stock.eastmoney.com",
            "Referer": "https://data.eastmoney.com/notices/hsa/5.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
        }
    
    def _process_stock_codes(self, stock_codes: List[str]) -> List[str]:
        """
        处理股票代码格式
        
        Args:
            stock_codes: 原始股票代码列表
            
        Returns:
            处理后的股票代码列表
        """
        processed_codes = []
        
        for code in stock_codes:
            # 处理带点号的代码
            if '.' in code:
                code = code.split('.')[0]
            
            # 移除市场前缀
            prefixes_to_remove = ['sh', 'sz', 'gb_', 'us', 'us_']
            for prefix in prefixes_to_remove:
                if code.startswith(prefix):
                    code = code[len(prefix):]
                    break
            
            processed_codes.append(code)
        
        return processed_codes
    
    def get_stock_notices(
        self, 
        stock_codes: List[str], 
        page_size: int = 50, 
        page_index: int = 1,
        ann_type: str = "SHA,CYB,SZA,BJA,INV"
    ) -> List[Dict[str, Any]]:
        """
        获取股票公告数据
        
        Args:
            stock_codes: 股票代码列表
            page_size: 每页数量
            page_index: 页码
            ann_type: 公告类型
            
        Returns:
            公告数据列表
        """
        # 处理股票代码
        processed_codes = self._process_stock_codes(stock_codes)
        
        params = {
            'page_size': page_size,
            'page_index': page_index,
            'ann_type': ann_type,
            'client_source': 'web',
            'f_node': '0',
            'stock_list': ','.join(processed_codes)
        }
        
        try:
            response = requests.get(
                self.base_url, 
                params=params, 
                headers=self.headers, 
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('data', {}).get('list', [])
            
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return []
    
    def get_pdf_url(self, art_code: str) -> str:
        """
        获取公告PDF下载链接
        
        Args:
            art_code: 公告代码
            
        Returns:
            PDF下载链接
        """
        return self.pdf_base_url.format(art_code=art_code)
    
    def download_pdf(self, art_code: str, save_path: str) -> bool:
        """
        下载公告PDF文件
        
        Args:
            art_code: 公告代码
            save_path: 保存路径
            
        Returns:
            下载是否成功
        """
        pdf_url = self.get_pdf_url(art_code)
        
        try:
            response = requests.get(pdf_url, timeout=self.timeout)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
            
        except requests.RequestException as e:
            print(f"PDF下载失败: {e}")
            return False
```

### 5.2 使用示例

```python
# 基础使用
if __name__ == "__main__":
    # 创建API客户端
    api = StockNoticeAPI()
    
    # 获取股票公告
    stock_codes = ["000001", "000002", "600000"]
    notices = api.get_stock_notices(stock_codes)
    
    # 处理公告数据
    for notice in notices:
        print(f"股票代码: {notice['codes'][0]['stock_code']}")
        print(f"股票名称: {notice['codes'][0]['short_name']}")
        print(f"公告标题: {notice['title']}")
        print(f"公告类型: {notice['columns'][0]['column_name']}")
        print(f"PDF链接: {api.get_pdf_url(notice['art_code'])}")
        print("-" * 50)
    
    # 下载PDF文件
    if notices:
        first_notice = notices[0]
        pdf_url = api.get_pdf_url(first_notice['art_code'])
        print(f"下载PDF: {pdf_url}")
        
        # 保存PDF文件
        save_path = f"notice_{first_notice['art_code']}.pdf"
        if api.download_pdf(first_notice['art_code'], save_path):
            print(f"PDF已保存到: {save_path}")
```

### 5.3 高级功能实现

```python
class AdvancedStockNoticeAPI(StockNoticeAPI):
    """增强版公告API，支持更多功能"""
    
    def get_notices_by_date_range(
        self, 
        stock_codes: List[str], 
        start_date: str, 
        end_date: str,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        按日期范围获取公告
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            page_size: 每页数量
            
        Returns:
            公告数据列表
        """
        all_notices = []
        page_index = 1
        
        while True:
            notices = self.get_stock_notices(
                stock_codes, 
                page_size=page_size, 
                page_index=page_index
            )
            
            if not notices:
                break
            
            # 过滤日期范围
            filtered_notices = []
            for notice in notices:
                notice_date = notice.get('notice_date', '')
                if start_date <= notice_date <= end_date:
                    filtered_notices.append(notice)
            
            all_notices.extend(filtered_notices)
            
            # 如果返回的数据少于请求的数量，说明已经到最后一页
            if len(notices) < page_size:
                break
            
            page_index += 1
        
        return all_notices
    
    def get_notices_by_type(
        self, 
        stock_codes: List[str], 
        notice_types: List[str],
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        按公告类型获取公告
        
        Args:
            stock_codes: 股票代码列表
            notice_types: 公告类型列表
            page_size: 每页数量
            
        Returns:
            公告数据列表
        """
        all_notices = []
        
        for notice_type in notice_types:
            notices = self.get_stock_notices(
                stock_codes, 
                page_size=page_size,
                ann_type=notice_type
            )
            all_notices.extend(notices)
        
        return all_notices
    
    def export_to_csv(self, notices: List[Dict[str, Any]], filename: str):
        """
        导出公告数据到CSV文件
        
        Args:
            notices: 公告数据列表
            filename: 输出文件名
        """
        import csv
        
        if not notices:
            print("没有数据可导出")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'stock_code', 'stock_name', 'title', 'notice_type', 
                'notice_date', 'pdf_url'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for notice in notices:
                writer.writerow({
                    'stock_code': notice['codes'][0]['stock_code'],
                    'stock_name': notice['codes'][0]['short_name'],
                    'title': notice['title'],
                    'notice_type': notice['columns'][0]['column_name'],
                    'notice_date': notice.get('notice_date', ''),
                    'pdf_url': self.get_pdf_url(notice['art_code'])
                })
        
        print(f"数据已导出到: {filename}")

# 使用示例
if __name__ == "__main__":
    api = AdvancedStockNoticeAPI()
    
    # 获取最近一周的公告
    from datetime import datetime, timedelta
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    notices = api.get_notices_by_date_range(
        ["000001", "000002"], 
        start_date, 
        end_date
    )
    
    print(f"找到 {len(notices)} 条公告")
    
    # 导出到CSV
    api.export_to_csv(notices, "stock_notices.csv")
```

## 6. 错误处理

### 6.1 常见错误类型

| 错误类型 | 原因 | 解决方案 |
|----------|------|----------|
| 网络超时 | 请求超时 | 增加timeout时间或重试 |
| JSON解析错误 | 响应格式异常 | 检查响应内容，添加异常处理 |
| 股票代码无效 | 代码格式错误 | 检查代码格式，使用_process_stock_codes处理 |
| 无数据返回 | 股票无公告或参数错误 | 检查股票代码和请求参数 |

### 6.2 错误处理示例

```python
def safe_get_notices(api: StockNoticeAPI, stock_codes: List[str]) -> List[Dict[str, Any]]:
    """安全的获取公告数据，包含完整的错误处理"""
    try:
        notices = api.get_stock_notices(stock_codes)
        return notices
    except requests.exceptions.Timeout:
        print("请求超时，请稍后重试")
        return []
    except requests.exceptions.ConnectionError:
        print("网络连接错误，请检查网络")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"HTTP错误: {e}")
        return []
    except Exception as e:
        print(f"未知错误: {e}")
        return []
```

## 7. 性能优化建议

### 7.1 批量处理

```python
def batch_get_notices(api: StockNoticeAPI, stock_codes: List[str], batch_size: int = 10):
    """批量获取公告数据，避免单次请求过多股票"""
    all_notices = []
    
    for i in range(0, len(stock_codes), batch_size):
        batch_codes = stock_codes[i:i + batch_size]
        notices = api.get_stock_notices(batch_codes)
        all_notices.extend(notices)
        
        # 添加延迟避免请求过于频繁
        time.sleep(0.5)
    
    return all_notices
```

### 7.2 缓存机制

```python
import pickle
import os
from datetime import datetime, timedelta

class CachedStockNoticeAPI(StockNoticeAPI):
    """带缓存功能的公告API"""
    
    def __init__(self, cache_dir: str = "./cache", cache_hours: int = 1):
        super().__init__()
        self.cache_dir = cache_dir
        self.cache_hours = cache_hours
        
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _get_cache_key(self, stock_codes: List[str]) -> str:
        """生成缓存键"""
        return f"notices_{'_'.join(sorted(stock_codes))}.pkl"
    
    def _is_cache_valid(self, cache_file: str) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(cache_file):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        return datetime.now() - file_time < timedelta(hours=self.cache_hours)
    
    def get_stock_notices(self, stock_codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        """带缓存的获取公告数据"""
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(stock_codes))
        
        # 检查缓存
        if self._is_cache_valid(cache_file):
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        
        # 获取新数据
        notices = super().get_stock_notices(stock_codes, **kwargs)
        
        # 保存缓存
        with open(cache_file, 'wb') as f:
            pickle.dump(notices, f)
        
        return notices
```

## 8. 完整示例项目

### 8.1 项目结构

```
stock_notice_api/
├── __init__.py
├── api.py              # API实现
├── examples/             # 使用示例
│   ├── basic_usage.py
│   ├── advanced_usage.py
│   └── batch_processing.py
├── tests/              # 测试文件
│   └── test_api.py
├── requirements.txt    # 依赖包
└── README.md          # 项目说明
```

### 8.2 requirements.txt

```txt
requests>=2.25.1
pandas>=1.3.0
python-dateutil>=2.8.0
```

### 8.3 基础使用示例

```python
# examples/basic_usage.py
from stock_notice_api import StockNoticeAPI

def main():
    # 创建API客户端
    api = StockNoticeAPI()
    
    # 获取单只股票的公告
    notices = api.get_stock_notices(["000001"])
    
    print(f"找到 {len(notices)} 条公告")
    
    for notice in notices:
        print(f"标题: {notice['title']}")
        print(f"类型: {notice['columns'][0]['column_name']}")
        print(f"PDF: {api.get_pdf_url(notice['art_code'])}")
        print("-" * 50)

if __name__ == "__main__":
    main()
```

## 9. 注意事项

### 9.1 使用限制

1. **请求频率**: 建议控制请求频率，避免过于频繁的请求
2. **数据时效性**: 公告数据可能存在延迟，建议定期更新
3. **网络环境**: 确保网络环境稳定，支持HTTPS请求

### 9.2 最佳实践

1. **错误处理**: 始终包含适当的错误处理机制
2. **数据验证**: 验证返回数据的完整性和正确性
3. **日志记录**: 记录重要的操作和错误信息
4. **资源管理**: 及时释放网络连接和文件资源

### 9.3 法律声明

使用本API时请遵守相关法律法规，不得用于非法用途。数据来源为公开信息，使用者需自行承担使用风险。

## 10. 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2024-01-01 | 初始版本，基础功能实现 |

---

**文档维护**: 本文档基于Go股票开发程序分析生成，如有疑问请参考源代码实现。
