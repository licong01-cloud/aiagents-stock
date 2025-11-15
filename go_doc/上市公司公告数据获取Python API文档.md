# 上市公司公告数据获取 Python API 文档

## 📋 概述

本文档基于 `go-stock-dev` 项目的公告数据获取功能，提供完整的 Python 实现方案。通过东方财富 API 获取上市公司公告数据，包括公告列表查询、PDF 下载等功能。

---

## 🔗 API 接口信息

### 1.1 公告数据查询接口

**接口地址**: `https://np-anotice-stock.eastmoney.com/api/security/ann`

**请求方法**: `GET`

**数据源**: 东方财富（Eastmoney）

**功能**: 获取指定股票的公告列表

**是否需要 Token**: ❌ 不需要

---

## 📝 请求参数详解

### 2.1 查询参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `page_size` | int | 否 | 50 | 每页返回的公告数量（最大建议50） |
| `page_index` | int | 否 | 1 | 页码，从1开始 |
| `ann_type` | string | 否 | `SHA,CYB,SZA,BJA,INV` | 公告类型，多个用逗号分隔 |
| `client_source` | string | 否 | `web` | 客户端来源标识 |
| `f_node` | int | 否 | 0 | 节点标识 |
| `stock_list` | string | **是** | - | 股票代码列表，多个代码用逗号分隔 |

### 2.2 公告类型说明

| 类型代码 | 说明 | 适用市场 |
|----------|------|---------|
| `SHA` | 上海A股公告 | 上海证券交易所 |
| `CYB` | 创业板公告 | 深圳证券交易所创业板 |
| `SZA` | 深圳A股公告 | 深圳证券交易所 |
| `BJA` | 北京A股公告 | 北京证券交易所 |
| `INV` | 投资公告 | 通用 |

**默认值**: `SHA,CYB,SZA,BJA,INV`（查询所有类型）

### 2.3 股票代码处理规则

程序会自动处理以下股票代码格式：

| 输入格式 | 处理后 | 说明 |
|---------|--------|------|
| `000001` | `000001` | 标准格式 |
| `sz000001` | `000001` | 移除深圳前缀 |
| `sh600000` | `600000` | 移除上海前缀 |
| `000001.SZ` | `000001` | 移除点号和后缀 |
| `600000.SH` | `600000` | 移除点号和后缀 |
| `gb_AAPL` | `AAPL` | 移除美股前缀 |
| `usTSLA` | `TSLA` | 移除美股前缀 |

**批量查询**: 多个代码用逗号分隔，如 `000001,600000,000002`

---

## 🌐 请求头设置

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
        "title": "关于公司重大事项的公告",
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
| `title` | string | 公告标题 | `"关于公司重大事项的公告"` |
| `notice_date` | string | 公告发布日期（格式：YYYY-MM-DD HH:mm:ss） | `"2025-01-15 10:00:00"` |
| `display_time` | string | 公告显示时间（格式：YYYY-MM-DD HH:mm:ss） | `"2025-01-15 10:00:00"` |
| `columns` | array | 公告类型数组 | `[{"column_name": "重大事项"}]` |
| `columns[].column_name` | string | 公告类型名称 | `"重大事项"` |
| `codes` | array | 关联股票数组 | `[{"stock_code": "000001", ...}]` |
| `codes[].stock_code` | string | 股票代码（6位数字） | `"000001"` |
| `codes[].short_name` | string | 股票简称 | `"平安银行"` |
| `codes[].market_code` | string | 市场代码（0=深市，1=沪市，2=北交所） | `"0"` |

### 4.3 市场代码映射

| market_code | 市场 | 说明 |
|------------|------|------|
| `"0"` | 深市 | 深圳证券交易所 |
| `"1"` | 沪市 | 上海证券交易所 |
| `"2"` | 北交所 | 北京证券交易所 |
| `"3"` | 港股 | 香港交易所 |

---

## 🐍 Python 实现方案

### 5.1 基础实现类

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
        
        # 必需请求头
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
            >>> api._process_stock_codes(["sz000001", "sh600000", "000001.SZ"])
            ['000001', '600000', '000001']
        """
        processed_codes = []
        
        for code in stock_codes:
            if not code or not code.strip():
                continue
                
            code = code.strip()
            
            # 处理带点号的代码（如 000001.SZ）
            if '.' in code:
                code = code.split('.')[0]
            
            # 移除市场前缀（不区分大小写）
            prefixes_to_remove = ['sh', 'sz', 'gb_', 'us', 'us_', 'hk', 'bj']
            code_lower = code.lower()
            
            for prefix in prefixes_to_remove:
                if code_lower.startswith(prefix):
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
            stock_codes: 股票代码列表，支持多种格式（如 ['000001', 'sz000002', '600000.SH']）
            page_size: 每页返回数量，默认50，最大建议50
            page_index: 页码，从1开始，默认1
            ann_type: 公告类型，多个用逗号分隔，默认查询所有类型
            
        Returns:
            公告数据列表，每个元素包含公告的详细信息
            
        Examples:
            >>> api = StockNoticeAPI()
            >>> notices = api.get_stock_notices(["000001", "600000"])
            >>> print(f"获取到 {len(notices)} 条公告")
            >>> for notice in notices[:3]:  # 显示前3条
            ...     print(f"{notice['title']} - {notice['notice_date']}")
        """
        # 处理股票代码
        processed_codes = self._process_stock_codes(stock_codes)
        
        if not processed_codes:
            print("警告: 没有有效的股票代码")
            return []
        
        # 构建请求参数
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
            
            # 解析JSON响应
            data = response.json()
            
            # 提取公告列表
            notices = data.get('data', {}).get('list', [])
            
            return notices
            
        except requests.exceptions.Timeout:
            print(f"请求超时（超过{self.timeout}秒）")
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
            print(f"未知错误: {type(e).__name__} - {e}")
            return []
    
    def get_pdf_url(self, art_code: str) -> str:
        """
        获取公告PDF下载链接
        
        Args:
            art_code: 公告唯一标识码（art_code字段）
            
        Returns:
            PDF下载链接
            
        Examples:
            >>> api = StockNoticeAPI()
            >>> pdf_url = api.get_pdf_url("1234567890")
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
            >>> success = api.download_pdf("1234567890", "./notices/notice_1234567890.pdf")
            >>> if success:
            ...     print("PDF下载成功")
        """
        pdf_url = self.get_pdf_url(art_code)
        
        try:
            response = requests.get(pdf_url, timeout=self.timeout)
            response.raise_for_status()
            
            # 确保目录存在
            import os
            os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else '.', exist_ok=True)
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            print(f"PDF已保存到: {save_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"PDF下载失败: {e}")
            return False
        except Exception as e:
            print(f"保存PDF文件失败: {e}")
            return False
```

---

### 5.2 基础使用示例

```python
from stock_notice_api import StockNoticeAPI

def basic_example():
    """基础使用示例"""
    # 创建API客户端
    api = StockNoticeAPI(timeout=15)
    
    # 方式1: 获取单只股票的公告
    print("=" * 60)
    print("示例1: 获取单只股票公告")
    print("=" * 60)
    notices = api.get_stock_notices(["000001"])
    print(f"找到 {len(notices)} 条公告\n")
    
    for i, notice in enumerate(notices[:5], 1):  # 显示前5条
        stock_info = notice['codes'][0]
        print(f"{i}. [{stock_info['stock_code']}] {stock_info['short_name']}")
        print(f"   标题: {notice['title']}")
        print(f"   类型: {notice['columns'][0]['column_name']}")
        print(f"   日期: {notice['notice_date']}")
        print(f"   PDF: {api.get_pdf_url(notice['art_code'])}")
        print()
    
    # 方式2: 批量获取多只股票的公告
    print("=" * 60)
    print("示例2: 批量获取多只股票公告")
    print("=" * 60)
    stock_codes = ["000001", "sz000002", "600000.SH", "300001"]
    notices = api.get_stock_notices(stock_codes, page_size=20)
    print(f"找到 {len(notices)} 条公告\n")
    
    # 按股票代码分组显示
    from collections import defaultdict
    grouped = defaultdict(list)
    for notice in notices:
        code = notice['codes'][0]['stock_code']
        grouped[code].append(notice)
    
    for code, code_notices in grouped.items():
        print(f"{code}: {len(code_notices)} 条公告")
    
    # 方式3: 下载PDF文件
    print("\n" + "=" * 60)
    print("示例3: 下载公告PDF")
    print("=" * 60)
    if notices:
        first_notice = notices[0]
        art_code = first_notice['art_code']
        save_path = f"./notices/notice_{art_code}.pdf"
        
        if api.download_pdf(art_code, save_path):
            print(f"✓ PDF下载成功: {save_path}")
        else:
            print("✗ PDF下载失败")


if __name__ == "__main__":
    basic_example()
```

---

### 5.3 高级功能实现

```python
from datetime import datetime, timedelta
from typing import List, Dict, Any
import csv
import os
import pickle
from stock_notice_api import StockNoticeAPI


class AdvancedStockNoticeAPI(StockNoticeAPI):
    """增强版公告API，支持更多高级功能"""
    
    def get_all_notices(
        self, 
        stock_codes: List[str],
        max_pages: int = 10,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取所有公告（自动翻页）
        
        Args:
            stock_codes: 股票代码列表
            max_pages: 最大翻页数，防止无限循环
            page_size: 每页数量
            
        Returns:
            所有公告数据列表
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
            
            all_notices.extend(notices)
            
            # 如果返回的数据少于请求的数量，说明已经到最后一页
            if len(notices) < page_size:
                break
            
            page_index += 1
            time.sleep(0.5)  # 避免请求过于频繁
        
        return all_notices
    
    def get_notices_by_date_range(
        self, 
        stock_codes: List[str], 
        start_date: str, 
        end_date: str,
        max_pages: int = 10,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        按日期范围获取公告
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            max_pages: 最大翻页数
            page_size: 每页数量
            
        Returns:
            指定日期范围内的公告数据列表
            
        Examples:
            >>> api = AdvancedStockNoticeAPI()
            >>> notices = api.get_notices_by_date_range(
            ...     ["000001"],
            ...     "2025-01-01",
            ...     "2025-01-31"
            ... )
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
                    elif notice_date < start_date:
                        # 如果日期已经早于开始日期，可以提前结束
                        # 因为公告通常是按时间倒序排列的
                        break
            
            all_notices.extend(filtered_notices)
            
            # 如果返回的数据少于请求的数量，说明已经到最后一页
            if len(notices) < page_size:
                break
            
            page_index += 1
            time.sleep(0.5)
        
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
            notice_types: 公告类型列表（如 ['SHA', 'CYB']）
            page_size: 每页数量
            
        Returns:
            指定类型的公告数据列表
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
    
    def filter_notices_by_keywords(
        self,
        notices: List[Dict[str, Any]],
        keywords: List[str],
        match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """
        根据关键词过滤公告
        
        Args:
            notices: 公告列表
            keywords: 关键词列表
            match_all: True=必须包含所有关键词，False=包含任一关键词即可
            
        Returns:
            过滤后的公告列表
        """
        filtered = []
        
        for notice in notices:
            title = notice.get('title', '').lower()
            notice_type = notice.get('columns', [{}])[0].get('column_name', '').lower()
            text = f"{title} {notice_type}"
            
            if match_all:
                # 必须包含所有关键词
                if all(keyword.lower() in text for keyword in keywords):
                    filtered.append(notice)
            else:
                # 包含任一关键词即可
                if any(keyword.lower() in text for keyword in keywords):
                    filtered.append(notice)
        
        return filtered
    
    def export_to_csv(
        self, 
        notices: List[Dict[str, Any]], 
        filename: str,
        encoding: str = 'utf-8-sig'  # 使用utf-8-sig以便Excel正确显示中文
    ):
        """
        导出公告数据到CSV文件
        
        Args:
            notices: 公告数据列表
            filename: 输出文件名
            encoding: 文件编码，默认utf-8-sig（Excel兼容）
        """
        if not notices:
            print("没有数据可导出")
            return
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        with open(filename, 'w', newline='', encoding=encoding) as csvfile:
            fieldnames = [
                '股票代码', '股票名称', '公告标题', '公告类型', 
                '公告日期', '显示时间', 'PDF链接'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for notice in notices:
                code_info = notice.get('codes', [{}])[0]
                column_info = notice.get('columns', [{}])[0]
                
                writer.writerow({
                    '股票代码': code_info.get('stock_code', ''),
                    '股票名称': code_info.get('short_name', ''),
                    '公告标题': notice.get('title', ''),
                    '公告类型': column_info.get('column_name', ''),
                    '公告日期': notice.get('notice_date', ''),
                    '显示时间': notice.get('display_time', ''),
                    'PDF链接': self.get_pdf_url(notice.get('art_code', ''))
                })
        
        print(f"✓ 数据已导出到: {filename} (共 {len(notices)} 条)")
    
    def export_to_json(
        self,
        notices: List[Dict[str, Any]],
        filename: str,
        indent: int = 2
    ):
        """
        导出公告数据到JSON文件
        
        Args:
            notices: 公告数据列表
            filename: 输出文件名
            indent: JSON缩进，默认2
        """
        if not notices:
            print("没有数据可导出")
            return
        
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(notices, f, ensure_ascii=False, indent=indent)
        
        print(f"✓ 数据已导出到: {filename} (共 {len(notices)} 条)")


# 使用示例
if __name__ == "__main__":
    api = AdvancedStockNoticeAPI()
    
    # 示例1: 获取最近一周的公告
    print("=" * 60)
    print("示例1: 获取最近一周的公告")
    print("=" * 60)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    notices = api.get_notices_by_date_range(
        ["000001", "600000"], 
        start_date, 
        end_date
    )
    
    print(f"找到 {len(notices)} 条公告")
    
    # 示例2: 过滤关键词
    print("\n" + "=" * 60)
    print("示例2: 过滤包含'重大'或'风险'的公告")
    print("=" * 60)
    
    filtered = api.filter_notices_by_keywords(notices, ['重大', '风险'])
    print(f"过滤后剩余 {len(filtered)} 条公告")
    
    # 示例3: 导出到CSV
    print("\n" + "=" * 60)
    print("示例3: 导出到CSV文件")
    print("=" * 60)
    
    api.export_to_csv(notices, "./notices/stock_notices.csv")
```

---

### 5.4 批量处理和缓存功能

```python
import time
from functools import lru_cache
from datetime import datetime, timedelta


class CachedStockNoticeAPI(AdvancedStockNoticeAPI):
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
    
    def get_stock_notices(
        self, 
        stock_codes: List[str], 
        page_size: int = 50, 
        page_index: int = 1,
        ann_type: str = "SHA,CYB,SZA,BJA,INV",
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        带缓存的获取公告数据
        
        Args:
            stock_codes: 股票代码列表
            page_size: 每页数量
            page_index: 页码
            ann_type: 公告类型
            use_cache: 是否使用缓存
            
        Returns:
            公告数据列表
        """
        if not use_cache:
            return super().get_stock_notices(stock_codes, page_size, page_index, ann_type)
        
        cache_file = os.path.join(self.cache_dir, self._get_cache_key(stock_codes, page_index))
        
        # 检查缓存
        if self._is_cache_valid(cache_file):
            print(f"使用缓存: {cache_file}")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        
        # 获取新数据
        notices = super().get_stock_notices(stock_codes, page_size, page_index, ann_type)
        
        # 保存缓存
        if notices:
            with open(cache_file, 'wb') as f:
                pickle.dump(notices, f)
            print(f"缓存已保存: {cache_file}")
        
        return notices


class BatchStockNoticeAPI(AdvancedStockNoticeAPI):
    """批量处理公告API"""
    
    def batch_get_notices(
        self, 
        stock_codes: List[str], 
        batch_size: int = 10,
        delay: float = 0.5,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        批量获取公告数据，避免单次请求过多股票
        
        Args:
            stock_codes: 股票代码列表
            batch_size: 每批处理的股票数量
            delay: 批次之间的延迟（秒）
            page_size: 每页数量
            
        Returns:
            所有公告数据列表
        """
        all_notices = []
        total_batches = (len(stock_codes) + batch_size - 1) // batch_size
        
        for i in range(0, len(stock_codes), batch_size):
            batch_codes = stock_codes[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"处理批次 {batch_num}/{total_batches}: {batch_codes}")
            
            notices = self.get_stock_notices(batch_codes, page_size=page_size)
            all_notices.extend(notices)
            
            print(f"  获取到 {len(notices)} 条公告")
            
            # 添加延迟避免请求过于频繁
            if i + batch_size < len(stock_codes):
                time.sleep(delay)
        
        return all_notices


# 使用示例
if __name__ == "__main__":
    # 示例1: 使用缓存
    print("=" * 60)
    print("示例1: 使用缓存功能")
    print("=" * 60)
    
    cached_api = CachedStockNoticeAPI(cache_dir="./cache", cache_hours=1)
    
    # 第一次请求（从API获取）
    notices1 = cached_api.get_stock_notices(["000001"])
    print(f"第一次请求: {len(notices1)} 条公告")
    
    # 第二次请求（从缓存获取）
    notices2 = cached_api.get_stock_notices(["000001"])
    print(f"第二次请求: {len(notices2)} 条公告")
    
    # 示例2: 批量处理
    print("\n" + "=" * 60)
    print("示例2: 批量处理多只股票")
    print("=" * 60)
    
    batch_api = BatchStockNoticeAPI()
    stock_codes = ["000001", "000002", "600000", "600519", "000858", "002594"]
    
    all_notices = batch_api.batch_get_notices(
        stock_codes,
        batch_size=3,
        delay=0.5
    )
    
    print(f"\n总共获取到 {len(all_notices)} 条公告")
```

---

## 📦 完整项目结构

### 6.1 项目目录结构

```
stock_notice_api/
├── __init__.py
├── api.py                    # 基础API实现
├── advanced_api.py           # 高级功能实现
├── cached_api.py             # 缓存功能实现
├── batch_api.py              # 批量处理实现
├── examples/                 # 使用示例
│   ├── basic_usage.py
│   ├── advanced_usage.py
│   ├── batch_processing.py
│   └── cache_example.py
├── tests/                    # 测试文件
│   ├── test_api.py
│   └── test_advanced.py
├── requirements.txt          # 依赖包
└── README.md                 # 项目说明
```

### 6.2 requirements.txt

```txt
requests>=2.25.1
```

### 6.3 安装和使用

```bash
# 安装依赖
pip install requests

# 或者使用requirements.txt
pip install -r requirements.txt
```

---

## 🔍 使用场景示例

### 7.1 场景1: 监控特定股票的公告

```python
from stock_notice_api import StockNoticeAPI
from datetime import datetime

def monitor_stock_notices(stock_code: str, keywords: List[str] = None):
    """
    监控特定股票的公告，筛选重要公告
    
    Args:
        stock_code: 股票代码
        keywords: 关键词列表，用于筛选重要公告
    """
    api = StockNoticeAPI()
    
    # 获取最新公告
    notices = api.get_stock_notices([stock_code], page_size=20)
    
    print(f"股票 {stock_code} 最新公告:")
    print("=" * 60)
    
    important_notices = []
    for notice in notices:
        title = notice['title']
        notice_type = notice['columns'][0]['column_name']
        notice_date = notice['notice_date']
        
        # 检查是否包含关键词
        is_important = False
        if keywords:
            text = f"{title} {notice_type}".lower()
            is_important = any(kw.lower() in text for kw in keywords)
        
        if is_important or not keywords:
            important_notices.append(notice)
            print(f"[{notice_date[:10]}] {notice_type}")
            print(f"  {title}")
            print(f"  PDF: {api.get_pdf_url(notice['art_code'])}")
            print()
    
    return important_notices


# 使用示例
if __name__ == "__main__":
    # 监控平安银行的重要公告
    keywords = ['重大', '风险', '减持', '增持', '重组', '停牌']
    important = monitor_stock_notices("000001", keywords)
    print(f"\n找到 {len(important)} 条重要公告")
```

### 7.2 场景2: 批量下载公告PDF

```python
from stock_notice_api import AdvancedStockNoticeAPI
from datetime import datetime, timedelta
import os

def batch_download_pdfs(
    stock_codes: List[str],
    start_date: str,
    end_date: str,
    save_dir: str = "./notices_pdf"
):
    """
    批量下载指定日期范围内的公告PDF
    
    Args:
        stock_codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        save_dir: 保存目录
    """
    api = AdvancedStockNoticeAPI()
    
    # 获取公告列表
    notices = api.get_notices_by_date_range(stock_codes, start_date, end_date)
    
    print(f"找到 {len(notices)} 条公告，开始下载PDF...")
    
    # 创建保存目录
    os.makedirs(save_dir, exist_ok=True)
    
    success_count = 0
    fail_count = 0
    
    for i, notice in enumerate(notices, 1):
        art_code = notice['art_code']
        stock_code = notice['codes'][0]['stock_code']
        title = notice['title'][:50]  # 限制文件名长度
        
        # 生成文件名
        filename = f"{stock_code}_{art_code}_{title}.pdf"
        filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
        save_path = os.path.join(save_dir, filename)
        
        print(f"[{i}/{len(notices)}] 下载: {filename}")
        
        if api.download_pdf(art_code, save_path):
            success_count += 1
        else:
            fail_count += 1
        
        # 添加延迟避免请求过于频繁
        time.sleep(0.3)
    
    print(f"\n下载完成: 成功 {success_count} 个，失败 {fail_count} 个")


# 使用示例
if __name__ == "__main__":
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    batch_download_pdfs(
        ["000001", "600000"],
        start_date,
        end_date,
        save_dir="./notices_pdf"
    )
```

### 7.3 场景3: 公告数据分析和统计

```python
from stock_notice_api import AdvancedStockNoticeAPI
from collections import Counter, defaultdict
from datetime import datetime, timedelta

def analyze_notices(stock_codes: List[str], days: int = 30):
    """
    分析股票的公告情况
    
    Args:
        stock_codes: 股票代码列表
        days: 分析最近N天的公告
    """
    api = AdvancedStockNoticeAPI()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    notices = api.get_notices_by_date_range(stock_codes, start_date, end_date)
    
    print(f"分析期间: {start_date} 至 {end_date}")
    print(f"共找到 {len(notices)} 条公告\n")
    
    # 统计1: 按股票代码分组
    print("=" * 60)
    print("统计1: 各股票公告数量")
    print("=" * 60)
    by_stock = defaultdict(int)
    for notice in notices:
        code = notice['codes'][0]['stock_code']
        by_stock[code] += 1
    
    for code, count in sorted(by_stock.items(), key=lambda x: x[1], reverse=True):
        print(f"{code}: {count} 条")
    
    # 统计2: 按公告类型分组
    print("\n" + "=" * 60)
    print("统计2: 公告类型分布")
    print("=" * 60)
    by_type = Counter()
    for notice in notices:
        notice_type = notice['columns'][0]['column_name']
        by_type[notice_type] += 1
    
    for notice_type, count in by_type.most_common():
        print(f"{notice_type}: {count} 条")
    
    # 统计3: 按日期分组
    print("\n" + "=" * 60)
    print("统计3: 每日公告数量")
    print("=" * 60)
    by_date = defaultdict(int)
    for notice in notices:
        date = notice['notice_date'][:10]
        by_date[date] += 1
    
    for date in sorted(by_date.keys()):
        print(f"{date}: {by_date[date]} 条")
    
    return {
        'total': len(notices),
        'by_stock': dict(by_stock),
        'by_type': dict(by_type),
        'by_date': dict(by_date)
    }


# 使用示例
if __name__ == "__main__":
    stats = analyze_notices(["000001", "600000", "000002"], days=30)
```

---

## ⚠️ 错误处理和最佳实践

### 8.1 错误处理示例

```python
from stock_notice_api import StockNoticeAPI
import requests

def safe_get_notices_with_retry(
    api: StockNoticeAPI, 
    stock_codes: List[str],
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> List[Dict[str, Any]]:
    """
    带重试机制的安全获取公告数据
    
    Args:
        api: API客户端实例
        stock_codes: 股票代码列表
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        
    Returns:
        公告数据列表
    """
    for attempt in range(max_retries):
        try:
            notices = api.get_stock_notices(stock_codes)
            return notices
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"请求超时，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print("请求超时，已达到最大重试次数")
                return []
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                print(f"网络连接错误，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print("网络连接错误，已达到最大重试次数")
                return []
        except Exception as e:
            print(f"未知错误: {type(e).__name__} - {e}")
            return []
    
    return []
```

### 8.2 最佳实践

1. **控制请求频率**
   ```python
   # 在批量请求时添加延迟
   for codes in batch_codes:
       notices = api.get_stock_notices(codes)
       time.sleep(0.5)  # 延迟0.5秒
   ```

2. **使用缓存**
   ```python
   # 对于不经常变化的数据使用缓存
   cached_api = CachedStockNoticeAPI(cache_hours=1)
   ```

3. **错误处理**
   ```python
   # 始终包含错误处理
   try:
       notices = api.get_stock_notices(codes)
   except Exception as e:
       print(f"获取失败: {e}")
       notices = []
   ```

4. **数据验证**
   ```python
   # 验证返回数据的完整性
   if notices and len(notices) > 0:
       first_notice = notices[0]
       if 'art_code' in first_notice and 'title' in first_notice:
           # 数据有效
           pass
   ```

---

## 📈 性能优化建议

### 9.1 并发请求（使用线程池）

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from stock_notice_api import StockNoticeAPI

def concurrent_get_notices(stock_codes: List[str], max_workers: int = 5):
    """
    并发获取多只股票的公告
    
    Args:
        stock_codes: 股票代码列表
        max_workers: 最大并发数
        
    Returns:
        所有公告数据列表
    """
    api = StockNoticeAPI()
    all_notices = []
    
    def get_single_stock_notices(code):
        return api.get_stock_notices([code])
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {
            executor.submit(get_single_stock_notices, code): code 
            for code in stock_codes
        }
        
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                notices = future.result()
                all_notices.extend(notices)
                print(f"✓ {code}: {len(notices)} 条公告")
            except Exception as e:
                print(f"✗ {code}: 获取失败 - {e}")
    
    return all_notices


# 使用示例
if __name__ == "__main__":
    codes = ["000001", "000002", "600000", "600519", "000858"]
    notices = concurrent_get_notices(codes, max_workers=3)
    print(f"\n总共获取到 {len(notices)} 条公告")
```

---

## 🔐 安全注意事项

1. **请求频率限制**: 建议控制请求频率，避免过于频繁的请求导致IP被封
2. **数据验证**: 始终验证返回数据的完整性和正确性
3. **错误处理**: 包含完整的错误处理机制，避免程序崩溃
4. **资源管理**: 及时释放网络连接和文件资源

---

## 📚 完整示例代码

### 10.1 基础使用完整示例

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上市公司公告数据获取 - 完整示例
"""

from stock_notice_api import StockNoticeAPI, AdvancedStockNoticeAPI
from datetime import datetime, timedelta
import os

def main():
    """主函数"""
    # 创建API客户端
    api = AdvancedStockNoticeAPI(timeout=15)
    
    # 示例1: 获取单只股票的最新公告
    print("=" * 70)
    print("示例1: 获取平安银行最新公告")
    print("=" * 70)
    
    notices = api.get_stock_notices(["000001"], page_size=10)
    print(f"获取到 {len(notices)} 条公告\n")
    
    for i, notice in enumerate(notices[:5], 1):
        stock_info = notice['codes'][0]
        print(f"{i}. [{stock_info['stock_code']}] {stock_info['short_name']}")
        print(f"   标题: {notice['title']}")
        print(f"   类型: {notice['columns'][0]['column_name']}")
        print(f"   日期: {notice['notice_date'][:10]}")
        print()
    
    # 示例2: 获取最近一周的公告
    print("=" * 70)
    print("示例2: 获取最近一周的公告")
    print("=" * 70)
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    weekly_notices = api.get_notices_by_date_range(
        ["000001", "600000"],
        start_date,
        end_date
    )
    print(f"找到 {len(weekly_notices)} 条公告\n")
    
    # 示例3: 导出到CSV
    print("=" * 70)
    print("示例3: 导出公告数据到CSV")
    print("=" * 70)
    
    os.makedirs("./output", exist_ok=True)
    csv_file = f"./output/notices_{datetime.now().strftime('%Y%m%d')}.csv"
    api.export_to_csv(weekly_notices, csv_file)
    
    # 示例4: 下载重要公告PDF
    print("\n" + "=" * 70)
    print("示例4: 下载重要公告PDF")
    print("=" * 70)
    
    important_keywords = ['重大', '风险', '减持', '增持']
    important_notices = api.filter_notices_by_keywords(
        weekly_notices,
        important_keywords
    )
    
    print(f"找到 {len(important_notices)} 条重要公告")
    
    os.makedirs("./notices_pdf", exist_ok=True)
    for notice in important_notices[:3]:  # 只下载前3条
        art_code = notice['art_code']
        stock_code = notice['codes'][0]['stock_code']
        pdf_path = f"./notices_pdf/{stock_code}_{art_code}.pdf"
        
        if api.download_pdf(art_code, pdf_path):
            print(f"✓ 已下载: {pdf_path}")
        else:
            print(f"✗ 下载失败: {art_code}")


if __name__ == "__main__":
    main()
```

---

## 📋 API接口总结

| 功能 | 方法 | 说明 |
|------|------|------|
| **获取公告列表** | `get_stock_notices()` | 基础方法，支持分页 |
| **获取所有公告** | `get_all_notices()` | 自动翻页获取所有数据 |
| **按日期范围查询** | `get_notices_by_date_range()` | 指定日期范围 |
| **按类型查询** | `get_notices_by_type()` | 指定公告类型 |
| **关键词过滤** | `filter_notices_by_keywords()` | 根据关键词筛选 |
| **导出CSV** | `export_to_csv()` | 导出为CSV文件 |
| **导出JSON** | `export_to_json()` | 导出为JSON文件 |
| **获取PDF链接** | `get_pdf_url()` | 生成PDF下载链接 |
| **下载PDF** | `download_pdf()` | 下载PDF文件 |

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2025-01-XX | 初始版本，基于go-stock-dev项目分析 |

---

## 📞 技术支持

如有问题或建议，请参考源代码实现：
- Go实现: `C:\Users\lc999\go-stock-dev\go-stock-dev\backend\data\market_news_api.go:510`
- 前端实现: `C:\Users\lc999\go-stock-dev\go-stock-dev\frontend\src\components\StockNoticeList.vue`

---

**文档版本**: 1.0  
**最后更新**: 2025-01-XX  
**数据源**: 东方财富（Eastmoney）  
**维护者**: 基于 go-stock-dev 项目分析

