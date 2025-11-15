# 上市公司公告数据获取 Python 使用文档

## 📋 概述

本文档基于 `go-stock-dev` 项目的公告数据获取功能，提供完整的 Python 实现方案，包括 API 接口详细说明、代码实现、使用示例和最佳实践。

---

## 🔗 API 接口信息

### 1.1 公告数据查询接口

**接口地址**: `https://np-anotice-stock.eastmoney.com/api/security/ann`

**请求方法**: `GET`

**数据源**: 东方财富（Eastmoney）

**功能**: 获取指定股票的上市公司公告列表

**是否需要 Token**: ❌ 不需要

---

## 📝 请求参数详解

### 2.1 查询参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `page_size` | int | 否 | 50 | 每页返回的公告数量（建议范围：10-100） |
| `page_index` | int | 否 | 1 | 页码，从1开始 |
| `ann_type` | string | 否 | `SHA,CYB,SZA,BJA,INV` | 公告类型，多个用逗号分隔 |
| `client_source` | string | 否 | `web` | 客户端来源标识 |
| `f_node` | int | 否 | 0 | 节点标识 |
| `stock_list` | string | **是** | - | 股票代码列表，多个代码用逗号分隔 |

### 2.2 公告类型说明

| 类型代码 | 说明 | 适用市场 |
|----------|------|----------|
| `SHA` | 上海A股公告 | 上海证券交易所主板 |
| `CYB` | 创业板公告 | 深圳证券交易所创业板 |
| `SZA` | 深圳A股公告 | 深圳证券交易所主板、中小板 |
| `BJA` | 北京A股公告 | 北京证券交易所 |
| `INV` | 投资公告 | 所有市场 |

**默认值**: `SHA,CYB,SZA,BJA,INV`（查询所有类型）

### 2.3 股票代码处理规则

程序会自动处理以下股票代码格式：

- **移除市场前缀**: `sh`、`sz`、`gb_`、`us`、`us_`
  - `sh600000` → `600000`
  - `sz000001` → `000001`
  - `gb_AAPL` → `AAPL`

- **处理带点号的代码**: `000001.SZ` → `000001`

- **支持批量查询**: 多个代码用逗号分隔
  - `000001,600000,000002`

---

## 🔧 请求头设置

### 3.1 必需请求头

```http
Host: np-anotice-stock.eastmoney.com
Referer: https://data.eastmoney.com/notices/hsa/5.html
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0
```

### 3.2 超时设置

建议设置 **15秒** 超时时间，避免长时间等待。

---

## 📊 响应数据格式

### 4.1 响应结构

```json
{
  "data": {
    "list": [
      {
        "art_code": "1234567890",
        "title": "关于公司重大资产重组的公告",
        "notice_date": "2025-01-15 10:00:00",
        "display_time": "2025-01-15 10:00:00",
        "columns": [
          {
            "column_name": "重大事项"
          }
        ],
        "codes": [
          {
            "stock_code": "000001",
            "short_name": "平安银行",
            "market_code": "0"
          }
        ]
      }
    ]
  }
}
```

### 4.2 字段详细说明

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `art_code` | string | 公告唯一标识码，用于构建PDF下载链接 | `"1234567890"` |
| `title` | string | 公告标题 | `"关于公司重大资产重组的公告"` |
| `notice_date` | string | 公告发布日期（格式：YYYY-MM-DD HH:mm:ss） | `"2025-01-15 10:00:00"` |
| `display_time` | string | 公告显示时间（格式：YYYY-MM-DD HH:mm:ss） | `"2025-01-15 10:00:00"` |
| `columns[].column_name` | string | 公告类型名称 | `"重大事项"`、`"定期报告"`等 |
| `codes[].stock_code` | string | 股票代码（6位数字） | `"000001"` |
| `codes[].short_name` | string | 股票简称 | `"平安银行"` |
| `codes[].market_code` | string | 市场代码（0=深市，1=沪市，2=北交所） | `"0"` |

### 4.3 市场代码说明

| market_code | 市场 | 股票代码前缀 |
|-------------|------|------------|
| `"0"` | 深圳证券交易所 | `000`、`002`、`300` |
| `"1"` | 上海证券交易所 | `600`、`601`、`603`、`688` |
| `"2"` | 北京证券交易所 | `8`开头 |

---

## 📄 PDF 下载接口

### 5.1 PDF 下载地址格式

```
https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf
```

**示例**:
```
https://pdf.dfcfw.com/pdf/H2_1234567890_1.pdf
```

**注意**: PDF URL 末尾可能包含时间戳参数，但不影响下载。

---

## 💻 Python 实现代码

### 6.1 基础实现类

```python
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import time


class StockNoticeAPI:
    """上市公司公告数据获取API"""
    
    def __init__(self, timeout: int = 15):
        """
        初始化API客户端
        
        Args:
            timeout: 请求超时时间（秒），默认15秒
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
        处理股票代码格式，移除市场前缀和点号
        
        Args:
            stock_codes: 原始股票代码列表
            
        Returns:
            处理后的股票代码列表
            
        Examples:
            >>> api = StockNoticeAPI()
            >>> api._process_stock_codes(['sh600000', 'sz000001', '000002.SZ'])
            ['600000', '000001', '000002']
        """
        processed_codes = []
        
        for code in stock_codes:
            code = str(code).strip()
            
            # 处理带点号的代码
            if '.' in code:
                code = code.split('.')[0]
            
            # 移除市场前缀（不区分大小写）
            prefixes_to_remove = ['sh', 'sz', 'gb_', 'us', 'us_']
            for prefix in prefixes_to_remove:
                if code.lower().startswith(prefix.lower()):
                    code = code[len(prefix):]
                    break
            
            if code:
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
            stock_codes: 股票代码列表，支持多种格式
            page_size: 每页返回的公告数量（默认50，建议范围10-100）
            page_index: 页码，从1开始（默认1）
            ann_type: 公告类型（默认查询所有类型）
            
        Returns:
            公告数据列表，每个元素包含公告的详细信息
            
        Examples:
            >>> api = StockNoticeAPI()
            >>> notices = api.get_stock_notices(['000001', '600000'])
            >>> print(f"获取到 {len(notices)} 条公告")
        """
        if not stock_codes:
            return []
        
        # 处理股票代码
        processed_codes = self._process_stock_codes(stock_codes)
        
        if not processed_codes:
            return []
        
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
            
            # 提取公告列表
            if 'data' in data and 'list' in data['data']:
                return data['data']['list']
            else:
                return []
                
        except requests.exceptions.Timeout:
            print(f"请求超时（超过 {self.timeout} 秒）")
            return []
        except requests.exceptions.ConnectionError:
            print("网络连接错误，请检查网络连接")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e.response.status_code} - {e.response.reason}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"响应内容: {response.text[:200]}")
            return []
        except Exception as e:
            print(f"未知错误: {e}")
            return []
    
    def get_pdf_url(self, art_code: str) -> str:
        """
        获取公告PDF下载链接
        
        Args:
            art_code: 公告唯一标识码
            
        Returns:
            PDF下载链接
            
        Examples:
            >>> api = StockNoticeAPI()
            >>> pdf_url = api.get_pdf_url('1234567890')
            >>> print(pdf_url)
            https://pdf.dfcfw.com/pdf/H2_1234567890_1.pdf
        """
        return self.pdf_base_url.format(art_code=art_code)
    
    def download_pdf(self, art_code: str, save_path: str) -> bool:
        """
        下载公告PDF文件
        
        Args:
            art_code: 公告唯一标识码
            save_path: 保存路径（包含文件名）
            
        Returns:
            下载是否成功
            
        Examples:
            >>> api = StockNoticeAPI()
            >>> success = api.download_pdf('1234567890', './notices/notice_1234567890.pdf')
            >>> if success:
            ...     print("PDF下载成功")
        """
        pdf_url = self.get_pdf_url(art_code)
        
        try:
            response = requests.get(pdf_url, timeout=self.timeout)
            response.raise_for_status()
            
            # 检查响应内容是否为PDF
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower() and not pdf_url.endswith('.pdf'):
                print(f"警告: 响应内容可能不是PDF文件 (Content-Type: {content_type})")
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            print(f"PDF已保存到: {save_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"PDF下载失败: {e}")
            return False
        except IOError as e:
            print(f"文件保存失败: {e}")
            return False
```

---

## 📚 使用示例

### 7.1 基础使用

```python
from stock_notice_api import StockNoticeAPI

# 创建API客户端
api = StockNoticeAPI()

# 获取单只股票的公告
notices = api.get_stock_notices(['000001'])

print(f"找到 {len(notices)} 条公告\n")

for notice in notices:
    stock_info = notice['codes'][0]
    print(f"股票代码: {stock_info['stock_code']}")
    print(f"股票名称: {stock_info['short_name']}")
    print(f"公告标题: {notice['title']}")
    print(f"公告类型: {notice['columns'][0]['column_name']}")
    print(f"公告日期: {notice['notice_date']}")
    print(f"PDF链接: {api.get_pdf_url(notice['art_code'])}")
    print("-" * 60)
```

### 7.2 批量查询多只股票

```python
# 批量查询多只股票的公告
stock_codes = ['000001', '000002', '600000', '600519', '000858']

notices = api.get_stock_notices(stock_codes, page_size=100)

print(f"共获取到 {len(notices)} 条公告")

# 按股票代码分组
notices_by_stock = {}
for notice in notices:
    stock_code = notice['codes'][0]['stock_code']
    if stock_code not in notices_by_stock:
        notices_by_stock[stock_code] = []
    notices_by_stock[stock_code].append(notice)

# 显示每只股票的公告数量
for stock_code, stock_notices in notices_by_stock.items():
    print(f"{stock_code}: {len(stock_notices)} 条公告")
```

### 7.3 下载PDF文件

```python
import os

# 创建保存目录
save_dir = './notices'
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# 获取公告并下载PDF
notices = api.get_stock_notices(['000001'], page_size=10)

for notice in notices:
    art_code = notice['art_code']
    title = notice['title'][:50]  # 限制文件名长度
    
    # 生成安全的文件名
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_title = safe_title.replace(' ', '_')
    
    save_path = os.path.join(save_dir, f"{art_code}_{safe_title}.pdf")
    
    if api.download_pdf(art_code, save_path):
        print(f"✓ 已下载: {title}")
    else:
        print(f"✗ 下载失败: {title}")
```

### 7.4 分页获取所有公告

```python
def get_all_notices(api: StockNoticeAPI, stock_codes: List[str], max_pages: int = 10) -> List[Dict]:
    """
    分页获取所有公告
    
    Args:
        api: API客户端实例
        stock_codes: 股票代码列表
        max_pages: 最大页数限制（防止无限循环）
        
    Returns:
        所有公告列表
    """
    all_notices = []
    page_index = 1
    page_size = 50
    
    while page_index <= max_pages:
        notices = api.get_stock_notices(
            stock_codes, 
            page_size=page_size, 
            page_index=page_index
        )
        
        if not notices:
            break
        
        all_notices.extend(notices)
        
        # 如果返回的数据少于请求的数量，说明已经到最后一页
        if len(notices) < page_size:
            break
        
        page_index += 1
        time.sleep(0.5)  # 避免请求过于频繁
    
    return all_notices

# 使用示例
api = StockNoticeAPI()
all_notices = get_all_notices(api, ['000001'], max_pages=5)
print(f"共获取到 {len(all_notices)} 条公告")
```

---

## 🚀 高级功能实现

### 8.1 按日期范围筛选

```python
from datetime import datetime, timedelta

class AdvancedStockNoticeAPI(StockNoticeAPI):
    """增强版公告API，支持更多功能"""
    
    def get_notices_by_date_range(
        self, 
        stock_codes: List[str], 
        start_date: str, 
        end_date: str,
        page_size: int = 50,
        max_pages: int = 20
    ) -> List[Dict[str, Any]]:
        """
        按日期范围获取公告
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            page_size: 每页数量
            max_pages: 最大页数限制
            
        Returns:
            符合日期范围的公告列表
        """
        all_notices = []
        page_index = 1
        
        while page_index <= max_pages:
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
                notice_date_str = notice.get('notice_date', '')
                if notice_date_str:
                    # 提取日期部分（YYYY-MM-DD）
                    notice_date = notice_date_str[:10]
                    if start_date <= notice_date <= end_date:
                        filtered_notices.append(notice)
            
            all_notices.extend(filtered_notices)
            
            # 如果返回的数据少于请求的数量，说明已经到最后一页
            if len(notices) < page_size:
                break
            
            page_index += 1
            time.sleep(0.5)
        
        return all_notices

# 使用示例
api = AdvancedStockNoticeAPI()

# 获取最近7天的公告
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

notices = api.get_notices_by_date_range(
    ['000001', '600000'], 
    start_date, 
    end_date
)

print(f"最近7天共找到 {len(notices)} 条公告")
```

### 8.2 按公告类型筛选

```python
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
        notice_types: 公告类型列表（如：['SHA', 'SZA']）
        page_size: 每页数量
        
    Returns:
        符合类型的公告列表
    """
    all_notices = []
    
    for notice_type in notice_types:
        notices = self.get_stock_notices(
            stock_codes, 
            page_size=page_size,
            ann_type=notice_type
        )
        all_notices.extend(notices)
        time.sleep(0.3)  # 避免请求过于频繁
    
    return all_notices

# 使用示例
api = AdvancedStockNoticeAPI()
notices = api.get_notices_by_type(
    ['000001'], 
    ['SHA', 'SZA']  # 只查询上海和深圳A股公告
)
```

### 8.3 导出到CSV

```python
import csv
from typing import List, Dict, Any

def export_to_csv(self, notices: List[Dict[str, Any]], filename: str):
    """
    导出公告数据到CSV文件
    
    Args:
        notices: 公告数据列表
        filename: 输出文件名
    """
    if not notices:
        print("没有数据可导出")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = [
            'stock_code', 'stock_name', 'title', 'notice_type', 
            'notice_date', 'display_time', 'pdf_url', 'art_code'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for notice in notices:
            stock_info = notice['codes'][0]
            writer.writerow({
                'stock_code': stock_info['stock_code'],
                'stock_name': stock_info['short_name'],
                'title': notice['title'],
                'notice_type': notice['columns'][0]['column_name'],
                'notice_date': notice.get('notice_date', ''),
                'display_time': notice.get('display_time', ''),
                'pdf_url': self.get_pdf_url(notice['art_code']),
                'art_code': notice['art_code']
            })
    
    print(f"数据已导出到: {filename}")

# 使用示例
api = AdvancedStockNoticeAPI()
notices = api.get_stock_notices(['000001', '600000'])
api.export_to_csv(notices, 'stock_notices.csv')
```

### 8.4 导出到Excel

```python
import pandas as pd

def export_to_excel(self, notices: List[Dict[str, Any]], filename: str):
    """
    导出公告数据到Excel文件
    
    Args:
        notices: 公告数据列表
        filename: 输出文件名
    """
    if not notices:
        print("没有数据可导出")
        return
    
    # 准备数据
    data = []
    for notice in notices:
        stock_info = notice['codes'][0]
        data.append({
            '股票代码': stock_info['stock_code'],
            '股票名称': stock_info['short_name'],
            '公告标题': notice['title'],
            '公告类型': notice['columns'][0]['column_name'],
            '公告日期': notice.get('notice_date', '')[:10],
            '显示时间': notice.get('display_time', '')[:19],
            'PDF链接': self.get_pdf_url(notice['art_code']),
            '公告代码': notice['art_code']
        })
    
    # 创建DataFrame并导出
    df = pd.DataFrame(data)
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"数据已导出到: {filename}")

# 使用示例（需要安装: pip install pandas openpyxl）
api = AdvancedStockNoticeAPI()
notices = api.get_stock_notices(['000001', '600000'])
api.export_to_excel(notices, 'stock_notices.xlsx')
```

---

## 🔄 批量处理与性能优化

### 9.1 批量处理（避免单次请求过多股票）

```python
def batch_get_notices(
    api: StockNoticeAPI, 
    stock_codes: List[str], 
    batch_size: int = 10,
    delay: float = 0.5
) -> List[Dict[str, Any]]:
    """
    批量获取公告数据，避免单次请求过多股票
    
    Args:
        api: API客户端实例
        stock_codes: 股票代码列表
        batch_size: 每批处理的股票数量
        delay: 批次之间的延迟时间（秒）
        
    Returns:
        所有公告列表
    """
    all_notices = []
    
    for i in range(0, len(stock_codes), batch_size):
        batch_codes = stock_codes[i:i + batch_size]
        print(f"正在处理第 {i//batch_size + 1} 批，股票: {batch_codes}")
        
        notices = api.get_stock_notices(batch_codes)
        all_notices.extend(notices)
        
        # 添加延迟避免请求过于频繁
        if i + batch_size < len(stock_codes):
            time.sleep(delay)
    
    return all_notices

# 使用示例
api = StockNoticeAPI()
stock_codes = ['000001', '000002', '600000', '600519', '000858', '002594']
all_notices = batch_get_notices(api, stock_codes, batch_size=3, delay=1.0)
print(f"共获取到 {len(all_notices)} 条公告")
```

### 9.2 缓存机制

```python
import pickle
import os
from datetime import datetime, timedelta

class CachedStockNoticeAPI(StockNoticeAPI):
    """带缓存功能的公告API"""
    
    def __init__(self, cache_dir: str = "./cache", cache_hours: int = 1, timeout: int = 15):
        """
        初始化带缓存的API客户端
        
        Args:
            cache_dir: 缓存目录
            cache_hours: 缓存有效期（小时）
            timeout: 请求超时时间（秒）
        """
        super().__init__(timeout=timeout)
        self.cache_dir = cache_dir
        self.cache_hours = cache_hours
        
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _get_cache_key(self, stock_codes: List[str], page_index: int = 1) -> str:
        """生成缓存文件名"""
        codes_str = '_'.join(sorted(stock_codes))
        return f"notices_{codes_str}_p{page_index}.pkl"
    
    def _is_cache_valid(self, cache_file: str) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(cache_file):
            return False
        
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        return datetime.now() - file_time < timedelta(hours=self.cache_hours)
    
    def get_stock_notices(self, stock_codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        """带缓存的获取公告数据"""
        page_index = kwargs.get('page_index', 1)
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(stock_codes, page_index))
        
        # 检查缓存
        if self._is_cache_valid(cache_file):
            print(f"从缓存加载数据: {cache_file}")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        
        # 获取新数据
        print(f"从API获取数据...")
        notices = super().get_stock_notices(stock_codes, **kwargs)
        
        # 保存缓存
        if notices:
            with open(cache_file, 'wb') as f:
                pickle.dump(notices, f)
            print(f"数据已缓存到: {cache_file}")
        
        return notices

# 使用示例
api = CachedStockNoticeAPI(cache_dir='./cache', cache_hours=2)
notices = api.get_stock_notices(['000001'])  # 第一次：从API获取
notices = api.get_stock_notices(['000001'])  # 第二次：从缓存加载
```

---

## ⚠️ 错误处理

### 10.1 完整错误处理示例

```python
def safe_get_notices(
    api: StockNoticeAPI, 
    stock_codes: List[str],
    retry_times: int = 3
) -> List[Dict[str, Any]]:
    """
    安全的获取公告数据，包含完整的错误处理和重试机制
    
    Args:
        api: API客户端实例
        stock_codes: 股票代码列表
        retry_times: 重试次数
        
    Returns:
        公告数据列表
    """
    for attempt in range(retry_times):
        try:
            notices = api.get_stock_notices(stock_codes)
            return notices
            
        except requests.exceptions.Timeout:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                print(f"请求超时，{wait_time}秒后重试 ({attempt + 1}/{retry_times})")
                time.sleep(wait_time)
            else:
                print("请求超时，已达到最大重试次数")
                return []
                
        except requests.exceptions.ConnectionError:
            if attempt < retry_times - 1:
                wait_time = (attempt + 1) * 2
                print(f"网络连接错误，{wait_time}秒后重试 ({attempt + 1}/{retry_times})")
                time.sleep(wait_time)
            else:
                print("网络连接错误，已达到最大重试次数")
                return []
                
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e.response.status_code} - {e.response.reason}")
            if e.response.status_code == 429:  # 请求过于频繁
                wait_time = (attempt + 1) * 5
                print(f"请求过于频繁，{wait_time}秒后重试")
                time.sleep(wait_time)
            else:
                return []
                
        except Exception as e:
            print(f"未知错误: {e}")
            return []
    
    return []

# 使用示例
api = StockNoticeAPI()
notices = safe_get_notices(api, ['000001'], retry_times=3)
```

### 10.2 常见错误及解决方案

| 错误类型 | 原因 | 解决方案 |
|----------|------|----------|
| **网络超时** | 请求超时 | 增加timeout时间或重试 |
| **JSON解析错误** | 响应格式异常 | 检查响应内容，添加异常处理 |
| **股票代码无效** | 代码格式错误 | 使用`_process_stock_codes`处理 |
| **无数据返回** | 股票无公告或参数错误 | 检查股票代码和请求参数 |
| **HTTP 429** | 请求过于频繁 | 增加请求间隔时间 |
| **连接错误** | 网络问题 | 检查网络连接，使用代理 |

---

## 📦 完整项目示例

### 11.1 项目结构

```
stock_notice_api/
├── __init__.py
├── api.py              # API实现
├── examples/           # 使用示例
│   ├── basic_usage.py
│   ├── advanced_usage.py
│   ├── batch_processing.py
│   └── export_data.py
├── tests/              # 测试文件
│   └── test_api.py
├── requirements.txt    # 依赖包
└── README.md           # 项目说明
```

### 11.2 requirements.txt

```txt
requests>=2.25.1
pandas>=1.3.0
openpyxl>=3.0.0
python-dateutil>=2.8.0
```

### 11.3 完整示例代码

```python
# examples/complete_example.py
"""
完整的公告数据获取示例
"""
from stock_notice_api import StockNoticeAPI, AdvancedStockNoticeAPI
from datetime import datetime, timedelta
import os

def main():
    # 创建API客户端
    api = AdvancedStockNoticeAPI()
    
    # 1. 获取单只股票的公告
    print("=" * 60)
    print("1. 获取单只股票的公告")
    print("=" * 60)
    notices = api.get_stock_notices(['000001'], page_size=10)
    print(f"平安银行(000001) 最新10条公告:")
    for i, notice in enumerate(notices[:5], 1):
        print(f"{i}. {notice['title']}")
        print(f"   类型: {notice['columns'][0]['column_name']}")
        print(f"   日期: {notice['notice_date'][:10]}")
    
    # 2. 批量查询多只股票
    print("\n" + "=" * 60)
    print("2. 批量查询多只股票")
    print("=" * 60)
    stock_codes = ['000001', '600000', '000002']
    all_notices = api.get_stock_notices(stock_codes, page_size=20)
    print(f"共获取到 {len(all_notices)} 条公告")
    
    # 3. 按日期范围查询
    print("\n" + "=" * 60)
    print("3. 按日期范围查询最近7天的公告")
    print("=" * 60)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent_notices = api.get_notices_by_date_range(
        ['000001'], 
        start_date, 
        end_date
    )
    print(f"最近7天共找到 {len(recent_notices)} 条公告")
    
    # 4. 导出到CSV
    print("\n" + "=" * 60)
    print("4. 导出数据到CSV")
    print("=" * 60)
    if all_notices:
        api.export_to_csv(all_notices, 'stock_notices.csv')
    
    # 5. 下载PDF文件
    print("\n" + "=" * 60)
    print("5. 下载PDF文件")
    print("=" * 60)
    save_dir = './notices'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    for notice in notices[:3]:  # 只下载前3条
        art_code = notice['art_code']
        title = notice['title'][:30]
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        
        save_path = os.path.join(save_dir, f"{art_code}_{safe_title}.pdf")
        if api.download_pdf(art_code, save_path):
            print(f"✓ 已下载: {title}")

if __name__ == "__main__":
    main()
```

---

## 🎯 最佳实践

### 12.1 请求频率控制

```python
import time

class RateLimitedStockNoticeAPI(StockNoticeAPI):
    """带请求频率限制的API客户端"""
    
    def __init__(self, min_interval: float = 1.0, timeout: int = 15):
        """
        初始化带频率限制的API客户端
        
        Args:
            min_interval: 最小请求间隔（秒）
            timeout: 请求超时时间（秒）
        """
        super().__init__(timeout=timeout)
        self.min_interval = min_interval
        self.last_request_time = 0
    
    def get_stock_notices(self, stock_codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        """带频率限制的获取公告数据"""
        # 控制请求频率
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        return super().get_stock_notices(stock_codes, **kwargs)
```

### 12.2 数据验证

```python
def validate_notice_data(notice: Dict[str, Any]) -> bool:
    """
    验证公告数据的完整性
    
    Args:
        notice: 公告数据字典
        
    Returns:
        数据是否有效
    """
    required_fields = ['art_code', 'title', 'notice_date', 'codes', 'columns']
    
    for field in required_fields:
        if field not in notice:
            print(f"缺少必需字段: {field}")
            return False
    
    if not notice['codes'] or not notice['columns']:
        print("codes 或 columns 为空")
        return False
    
    if not notice['codes'][0].get('stock_code'):
        print("股票代码为空")
        return False
    
    return True

# 使用示例
api = StockNoticeAPI()
notices = api.get_stock_notices(['000001'])

valid_notices = [n for n in notices if validate_notice_data(n)]
print(f"有效公告: {len(valid_notices)}/{len(notices)}")
```

### 12.3 日志记录

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stock_notice_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('StockNoticeAPI')

class LoggedStockNoticeAPI(StockNoticeAPI):
    """带日志记录的API客户端"""
    
    def get_stock_notices(self, stock_codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        """带日志记录的获取公告数据"""
        logger.info(f"开始获取公告数据: 股票代码={stock_codes}, 参数={kwargs}")
        
        try:
            notices = super().get_stock_notices(stock_codes, **kwargs)
            logger.info(f"成功获取 {len(notices)} 条公告")
            return notices
        except Exception as e:
            logger.error(f"获取公告数据失败: {e}", exc_info=True)
            return []
```

---

## 📋 数据字段完整说明

### 13.1 响应数据结构

```python
{
    "data": {
        "list": [
            {
                # 公告基本信息
                "art_code": "1234567890",              # 公告唯一标识码
                "title": "关于公司重大资产重组的公告",  # 公告标题
                "notice_date": "2025-01-15 10:00:00",  # 公告发布日期
                "display_time": "2025-01-15 10:00:00",  # 显示时间
                
                # 公告类型
                "columns": [
                    {
                        "column_name": "重大事项"       # 公告类型名称
                    }
                ],
                
                # 关联股票信息
                "codes": [
                    {
                        "stock_code": "000001",        # 股票代码（6位）
                        "short_name": "平安银行",       # 股票简称
                        "market_code": "0"            # 市场代码
                    }
                ],
                
                # 其他可能存在的字段
                "ann_type": "SZA",                    # 公告类型代码
                "ann_date": "2025-01-15",             # 公告日期（仅日期）
                # ... 其他字段
            }
        ]
    }
}
```

### 13.2 公告类型名称示例

常见公告类型名称包括：
- `重大事项`
- `定期报告`
- `临时公告`
- `业绩预告`
- `分红派息`
- `股权变动`
- `重大合同`
- `诉讼仲裁`
- `关联交易`
- `对外投资`
- `资产重组`
- `停复牌公告`
- `风险提示`
- `澄清公告`
- `其他公告`

---

## 🔍 常见问题解答

### Q1: 如何获取特定类型的公告？

```python
# 只查询上海A股公告
notices = api.get_stock_notices(['600000'], ann_type='SHA')

# 只查询创业板公告
notices = api.get_stock_notices(['300001'], ann_type='CYB')

# 查询多个类型
notices = api.get_stock_notices(['000001'], ann_type='SHA,SZA')
```

### Q2: 如何获取更多公告（超过50条）？

```python
# 方法1: 增加page_size（最大建议100）
notices = api.get_stock_notices(['000001'], page_size=100)

# 方法2: 分页获取
all_notices = []
page = 1
while True:
    notices = api.get_stock_notices(['000001'], page_index=page, page_size=50)
    if not notices:
        break
    all_notices.extend(notices)
    if len(notices) < 50:
        break
    page += 1
    time.sleep(0.5)
```

### Q3: 如何处理股票代码格式不一致的问题？

```python
# API会自动处理，支持以下格式：
codes = [
    '000001',        # 标准格式
    'sh600000',      # 带市场前缀
    'sz000002',      # 带市场前缀
    '000001.SZ',     # 带点号
    '600000.SH'      # 带点号
]

notices = api.get_stock_notices(codes)  # 自动处理所有格式
```

### Q4: PDF下载失败怎么办？

```python
def download_pdf_with_retry(api: StockNoticeAPI, art_code: str, save_path: str, max_retries: int = 3) -> bool:
    """带重试的PDF下载"""
    for attempt in range(max_retries):
        if api.download_pdf(art_code, save_path):
            return True
        if attempt < max_retries - 1:
            print(f"下载失败，{2*(attempt+1)}秒后重试...")
            time.sleep(2 * (attempt + 1))
    return False
```

---

## ⚙️ 配置说明

### 14.1 推荐配置

```python
# 基础配置
api = StockNoticeAPI(timeout=15)  # 15秒超时

# 带缓存的配置
cached_api = CachedStockNoticeAPI(
    cache_dir='./cache',
    cache_hours=2,      # 缓存2小时
    timeout=15
)

# 带频率限制的配置
rate_limited_api = RateLimitedStockNoticeAPI(
    min_interval=1.0,   # 最小间隔1秒
    timeout=15
)
```

### 14.2 性能优化建议

1. **批量处理**: 单次请求不超过10只股票
2. **请求间隔**: 建议间隔0.5-1秒
3. **使用缓存**: 对于不经常变化的数据使用缓存
4. **分页获取**: 大量数据时使用分页，避免单次请求过大
5. **错误重试**: 实现重试机制，提高成功率

---

## 📝 注意事项

### 15.1 使用限制

1. **请求频率**: 建议控制请求频率，避免过于频繁的请求
2. **数据时效性**: 公告数据可能存在延迟，建议定期更新
3. **网络环境**: 确保网络环境稳定，支持HTTPS请求
4. **数据准确性**: 数据来源于第三方，请自行验证准确性

### 15.2 法律声明

使用本API时请遵守相关法律法规：
- 不得用于非法用途
- 数据来源为公开信息
- 使用者需自行承担使用风险
- 请遵守数据源的使用条款

---

## 📚 完整代码文件

### 16.1 stock_notice_api.py

```python
"""
上市公司公告数据获取API
基于东方财富API实现
"""

import requests
import json
import time
import pickle
import os
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


class StockNoticeAPI:
    """上市公司公告数据获取API"""
    
    def __init__(self, timeout: int = 15):
        """初始化API客户端"""
        self.base_url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        self.pdf_base_url = "https://pdf.dfcfw.com/pdf/H2_{art_code}_1.pdf"
        self.timeout = timeout
        
        self.headers = {
            "Host": "np-anotice-stock.eastmoney.com",
            "Referer": "https://data.eastmoney.com/notices/hsa/5.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
        }
    
    def _process_stock_codes(self, stock_codes: List[str]) -> List[str]:
        """处理股票代码格式"""
        processed_codes = []
        for code in stock_codes:
            code = str(code).strip()
            if '.' in code:
                code = code.split('.')[0]
            prefixes_to_remove = ['sh', 'sz', 'gb_', 'us', 'us_']
            for prefix in prefixes_to_remove:
                if code.lower().startswith(prefix.lower()):
                    code = code[len(prefix):]
                    break
            if code:
                processed_codes.append(code)
        return processed_codes
    
    def get_stock_notices(
        self, 
        stock_codes: List[str], 
        page_size: int = 50, 
        page_index: int = 1,
        ann_type: str = "SHA,CYB,SZA,BJA,INV"
    ) -> List[Dict[str, Any]]:
        """获取股票公告数据"""
        if not stock_codes:
            return []
        
        processed_codes = self._process_stock_codes(stock_codes)
        if not processed_codes:
            return []
        
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
            
            if 'data' in data and 'list' in data['data']:
                return data['data']['list']
            return []
                
        except Exception as e:
            print(f"获取公告数据失败: {e}")
            return []
    
    def get_pdf_url(self, art_code: str) -> str:
        """获取公告PDF下载链接"""
        return self.pdf_base_url.format(art_code=art_code)
    
    def download_pdf(self, art_code: str, save_path: str) -> bool:
        """下载公告PDF文件"""
        pdf_url = self.get_pdf_url(art_code)
        try:
            response = requests.get(pdf_url, timeout=self.timeout)
            response.raise_for_status()
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"PDF下载失败: {e}")
            return False


# 使用示例
if __name__ == "__main__":
    api = StockNoticeAPI()
    
    # 获取公告
    notices = api.get_stock_notices(['000001', '600000'])
    print(f"获取到 {len(notices)} 条公告")
    
    # 显示公告信息
    for notice in notices[:5]:
        stock = notice['codes'][0]
        print(f"\n股票: {stock['stock_code']} {stock['short_name']}")
        print(f"标题: {notice['title']}")
        print(f"类型: {notice['columns'][0]['column_name']}")
        print(f"日期: {notice['notice_date'][:10]}")
```

---

## 📖 快速开始

### 17.1 安装依赖

```bash
pip install requests
```

### 17.2 基础使用

```python
from stock_notice_api import StockNoticeAPI

# 创建API客户端
api = StockNoticeAPI()

# 获取公告
notices = api.get_stock_notices(['000001'])

# 打印结果
for notice in notices:
    print(notice['title'])
```

---

## 🔄 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2025-01-XX | 初始版本，基于go-stock-dev项目分析生成 |

---

**文档维护**: 本文档基于 `go-stock-dev` 项目源代码分析生成，如有疑问请参考源代码实现。

**数据源**: 东方财富（Eastmoney）  
**接口地址**: `https://np-anotice-stock.eastmoney.com/api/security/ann`  
**无需Token**: ✅ 直接使用

