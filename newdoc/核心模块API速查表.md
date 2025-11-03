# 核心模块API速查表

**版本**: v1.0  
**创建日期**: 2025-11-01  
**说明**: 本文档提供核心模块的快速API查询参考

---

## 1. 数据源管理器 (DataSourceManager)

### 导入
```python
from data_source_manager import data_source_manager
```

### 核心API (24个方法)

| 方法名 | 功能 | 主要参数 | 返回类型 |
|--------|------|----------|----------|
| `get_stock_hist_data()` | 获取历史数据 | symbol, start_date, end_date, adjust | DataFrame |
| `get_stock_basic_info()` | 获取基本信息 | symbol | dict |
| `get_realtime_quotes()` | 获取实时行情 | symbol | dict |
| `get_financial_data()` | 获取财务数据 | symbol, report_type | DataFrame |
| `get_margin_trading_data()` | 获取融资融券 | symbol, trade_date | dict |
| `get_hsgt_fund_flow_data()` | 获取沪深港通 | symbol, trade_date | dict |
| `get_research_reports_data()` | 获取研报 | symbol, days | dict |
| `get_turnover_rate_data()` | 获取换手率 | symbol, trade_date | dict |
| `get_market_index_data()` | 获取指数 | index_code, trade_date | dict |
| `get_concept_data()` | 获取概念板块 | 无 | DataFrame |
| `get_industry_data()` | 获取行业板块 | 无 | DataFrame |
| `get_longhubang_*()` | 龙虎榜数据 | trade_date, ts_code | DataFrame/dict |
| `is_margin_trading_stock()` | 判断是否融资融券标的 | symbol | bool |
| `get_tushare_data()` | 通用Tushare接口 | interface_name, **kwargs | DataFrame |

### 快速示例
```python
# 获取历史数据
df = data_source_manager.get_stock_hist_data('002230', start_date='20240101')

# 获取基本信息
info = data_source_manager.get_stock_basic_info('002230')

# 获取实时行情
quotes = data_source_manager.get_realtime_quotes('002230')
```

---

## 2. 网络优化器 (NetworkOptimizer)

### 导入
```python
from network_optimizer import network_optimizer
```

### 核心API (51个方法)

#### 代理管理 (10个)
| 方法名 | 功能 | 参数 |
|--------|------|------|
| `add_proxy()` | 添加代理 | name, proxy_config, priority, enabled, description |
| `remove_proxy()` | 删除代理 | name |
| `update_proxy()` | 更新代理 | old_name, new_name, proxy_config, ... |
| `toggle_proxy()` | 启用/禁用代理 | name, enabled |
| `update_proxy_priority()` | 更新优先级 | name, priority |
| `get_proxy_list()` | 获取代理列表 | 无 |
| `enable_proxy()` | 启用代理功能 | 无 |
| `disable_proxy()` | 禁用代理功能 | 无 |
| `is_proxy_enabled()` | 检查代理状态 | 无 |
| `set_proxy_enabled()` | 设置代理开关 | enabled |

#### 动态代理 (5个)
| 方法名 | 功能 |
|--------|------|
| `add_dynamic_proxy_source()` | 添加动态代理源 |
| `get_dynamic_proxy()` | 获取动态代理 |
| `get_dynamic_proxy_from_source()` | 从指定源获取代理 |
| `update_dynamic_proxy_source()` | 更新动态代理源 |
| `add_proxy_from_txt_file()` | 从文本导入代理 |

#### 代理测试 (4个)
| 方法名 | 功能 |
|--------|------|
| `test_proxy()` | 完整测试代理 |
| `test_proxy_fast()` | 快速测试代理 |
| `test_proxy_list()` | 批量测试代理 |
| `parse_proxy_txt_file()` | 解析代理文本 |

#### 网络请求 (2个)
| 方法名 | 功能 |
|--------|------|
| `get_etf_spot_data_with_retry()` | 获取ETF实时数据 |
| `get_etf_hist_data_with_retry()` | 获取ETF历史数据 |

#### 状态查询 (2个)
| 方法名 | 功能 |
|--------|------|
| `get_network_status()` | 获取网络状态 |
| `test_network_connection()` | 测试网络连接 |

### 快速示例
```python
# 添加代理
network_optimizer.add_proxy("本地代理", {"proxy": "http://127.0.0.1:7890"}, priority=2)

# 启用代理
network_optimizer.enable_proxy()

# 测试代理
is_ok = network_optimizer.test_proxy_fast({"proxy": "http://127.0.0.1:7890"})

# 获取状态
status = network_optimizer.get_network_status()
```

---

## 3. AI分析师模块 (StockAnalysisAgents)

### 导入
```python
from ai_agents import StockAnalysisAgents
```

### 九位分析师

| 方法名 | 分析师 | 主要参数 | 关注领域 |
|--------|--------|----------|----------|
| `technical_analyst_agent()` | 技术分析师 | stock_info, stock_data, indicators | 技术指标、趋势、支撑阻力 |
| `fundamental_analyst_agent()` | 基本面分析师 | stock_info, financial_data, quarterly_data | 财务指标、行业、估值 |
| `fund_flow_analyst_agent()` | 资金面分析师 | stock_info, indicators, fund_flow_data, margin_data | 资金流向、融资融券 |
| `risk_management_agent()` | 风险管理师 | stock_info, indicators, risk_data | 风险评估、解禁减持 |
| `market_sentiment_agent()` | 市场情绪分析师 | stock_info, sentiment_data | 市场情绪、热度 |
| `news_analyst_agent()` | 新闻分析师 | stock_info, news_data | 新闻舆情、事件 |
| `research_report_analyst_agent()` | 机构研报分析师 | stock_info, research_data | 研报、评级 |
| `announcement_analyst_agent()` | 公告分析师 | stock_info, announcement_data | 公告、重大事项 |
| `chip_analyst_agent()` | 筹码分析师 | stock_info, chip_data | 筹码分布、主力 |

### 返回格式
```python
{
    "agent_name": "技术分析师",
    "agent_role": "负责技术指标分析...",
    "analysis": "分析内容（Markdown格式）",
    "focus_areas": ["技术指标", "趋势分析", ...],
    "timestamp": "2025-11-01 14:47:10"
}
```

### 快速示例
```python
from ai_agents import StockAnalysisAgents
from stock_data import StockDataFetcher

agents = StockAnalysisAgents()
fetcher = StockDataFetcher()

# 获取数据
stock_info = fetcher.get_stock_info('002230')
stock_data = fetcher.get_stock_data('002230', '1y')
indicators = fetcher.calculate_technical_indicators(stock_data)

# 调用分析师
result = agents.technical_analyst_agent(stock_info, stock_data, indicators)
print(result['analysis'])
```

---

## 4. 持仓管理器 (PortfolioManager)

### 导入
```python
from portfolio_manager import portfolio_manager
```

### 核心API (17个方法)

#### 持仓管理 (7个)
| 方法名 | 功能 | 参数 | 返回 |
|--------|------|------|------|
| `add_stock()` | 添加持仓 | code, name, cost_price, quantity, note, auto_monitor | (bool, str, int) |
| `update_stock()` | 更新持仓 | stock_id, **kwargs | (bool, str) |
| `delete_stock()` | 删除持仓 | stock_id | (bool, str) |
| `get_stock()` | 获取单个持仓 | stock_id | dict |
| `get_all_stocks()` | 获取所有持仓 | auto_monitor_only | list[dict] |
| `search_stocks()` | 搜索持仓 | keyword | list[dict] |
| `get_stock_count()` | 统计持仓数 | 无 | int |

#### 分析功能 (4个)
| 方法名 | 功能 | 主要参数 |
|--------|------|----------|
| `analyze_single_stock()` | 单股分析 | stock_code, period, selected_analysts |
| `batch_analyze_sequential()` | 顺序批量分析 | stock_codes, period, selected_analysts |
| `batch_analyze_parallel()` | 并行批量分析 | stock_codes, period, selected_analysts, max_workers |
| `batch_analyze_portfolio()` | 持仓批量分析 | mode, period, selected_analysts, auto_monitor_only |

#### 历史记录 (6个)
| 方法名 | 功能 |
|--------|------|
| `save_analysis_results()` | 保存分析结果 |
| `get_analysis_history()` | 获取分析历史 |
| `get_latest_analysis()` | 获取最新分析 |
| `get_all_latest_analysis()` | 获取所有最新分析 |
| `get_rating_changes()` | 获取评级变化 |

### 快速示例
```python
# 添加持仓
success, msg, stock_id = portfolio_manager.add_stock(
    code='002230',
    name='科大讯飞',
    cost_price=55.05,
    quantity=1000
)

# 批量分析
results = portfolio_manager.batch_analyze_portfolio(mode='sequential')

# 查询历史
history = portfolio_manager.get_analysis_history(stock_id, limit=10)
```

---

## 5. 持仓数据库 (PortfolioDB)

### 导入
```python
from portfolio_db import portfolio_db
```

### 数据表结构

#### portfolio_stocks表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| code | TEXT | 股票代码 |
| name | TEXT | 股票名称 |
| cost_price | REAL | 持仓成本 |
| quantity | INTEGER | 持仓数量 |
| note | TEXT | 备注 |
| auto_monitor | BOOLEAN | 自动监测 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### portfolio_analysis_history表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| portfolio_stock_id | INTEGER | 外键 |
| analysis_time | TIMESTAMP | 分析时间 |
| rating | TEXT | 评级 |
| confidence | REAL | 置信度 |
| current_price | REAL | 当前价 |
| target_price | REAL | 目标价 |
| entry_min | REAL | 建仓下限 |
| entry_max | REAL | 建仓上限 |
| take_profit | REAL | 止盈价 |
| stop_loss | REAL | 止损价 |
| summary | TEXT | 摘要 |

### 核心API (18个方法)
- 数据操作: `add_stock()`, `update_stock()`, `delete_stock()`, `get_stock()`, ...
- 分析记录: `save_analysis()`, `get_analysis_history()`, `get_latest_analysis()`, ...

---

## 6. 定时调度器 (PortfolioScheduler)

### 导入
```python
from portfolio_scheduler import portfolio_scheduler
```

### 核心API (29个方法)

#### 时间调度 (5个)
| 方法名 | 功能 |
|--------|------|
| `set_schedule_time()` | 设置单个时间 |
| `add_schedule_time()` | 添加时间点 |
| `remove_schedule_time()` | 删除时间点 |
| `get_schedule_times()` | 获取所有时间 |
| `set_schedule_times()` | 批量设置时间 |

#### 调度控制 (6个)
| 方法名 | 功能 |
|--------|------|
| `start()` | 启动调度器 |
| `stop()` | 停止调度器 |
| `run_once()` | 立即运行一次 |
| `is_running()` | 检查运行状态 |
| `get_status()` | 获取状态信息 |
| `get_next_run_time()` | 获取下次运行时间 |

#### 配置管理 (5个)
| 方法名 | 功能 |
|--------|------|
| `set_analysis_mode()` | 设置分析模式 |
| `set_auto_monitor_sync()` | 设置监测同步 |
| `set_notification_enabled()` | 设置通知开关 |
| `set_selected_agents()` | 设置分析师 |
| `update_config()` | 批量更新配置 |

### 快速示例
```python
from portfolio_scheduler import portfolio_scheduler

# 配置调度器
portfolio_scheduler.add_schedule_time("09:30")
portfolio_scheduler.add_schedule_time("15:00")
portfolio_scheduler.set_analysis_mode("sequential")
portfolio_scheduler.set_notification_enabled(True)

# 启动调度器
success = portfolio_scheduler.start()

# 查看状态
status = portfolio_scheduler.get_status()
print(f"运行中: {status['is_running']}")
print(f"下次运行: {status['next_run_time']}")

# 立即运行一次
portfolio_scheduler.run_once()

# 停止调度器
portfolio_scheduler.stop()
```

---

## 7. 股票数据获取器 (StockDataFetcher)

### 导入
```python
from stock_data import StockDataFetcher
```

### 核心API (31个方法)

| 方法名 | 功能 | 支持类型 |
|--------|------|----------|
| `get_stock_info()` | 获取股票信息 | A股/港股/美股/ETF |
| `get_stock_data()` | 获取历史数据 | A股/港股/美股/ETF |
| `calculate_technical_indicators()` | 计算技术指标 | 所有类型 |
| `get_latest_indicators()` | 获取最新指标 | 所有类型 |
| `get_financial_data()` | 获取财务数据 | A股/港股/美股 |
| `get_risk_data()` | 获取风险数据 | A股 |
| `get_etf_*()` | ETF相关方法 | ETF |
| `get_real_time_data()` | 获取实时数据 | 所有类型 |

### 快速示例
```python
from stock_data import StockDataFetcher

fetcher = StockDataFetcher()

# 获取股票信息
info = fetcher.get_stock_info('002230')

# 获取历史数据
data = fetcher.get_stock_data('002230', period='1y')

# 计算技术指标
indicators = fetcher.calculate_technical_indicators(data)

# 获取最新指标
latest = fetcher.get_latest_indicators(data)
```

---

## 8. 常用工作流

### 完整分析流程
```python
from ai_agents import StockAnalysisAgents
from stock_data import StockDataFetcher
from data_source_manager import data_source_manager

# 1. 初始化
agents = StockAnalysisAgents()
fetcher = StockDataFetcher()

# 2. 获取数据
symbol = '002230'
stock_info = fetcher.get_stock_info(symbol)
stock_data = fetcher.get_stock_data(symbol, '1y')
indicators = fetcher.calculate_technical_indicators(stock_data)
financial_data = data_source_manager.get_financial_data(symbol)
margin_data = data_source_manager.get_margin_trading_data(symbol)

# 3. AI分析
tech_result = agents.technical_analyst_agent(stock_info, stock_data, indicators)
fund_result = agents.fundamental_analyst_agent(stock_info, financial_data)
capital_result = agents.fund_flow_analyst_agent(stock_info, indicators, None, margin_data)

# 4. 输出结果
print(tech_result['analysis'])
print(fund_result['analysis'])
print(capital_result['analysis'])
```

### 持仓批量分析
```python
from portfolio_manager import portfolio_manager

# 添加持仓
portfolio_manager.add_stock('002230', '科大讯飞', 55.05, 1000)
portfolio_manager.add_stock('600519', '贵州茅台', 1680.0, 100)

# 批量分析
results = portfolio_manager.batch_analyze_portfolio(
    mode='sequential',
    period='1y',
    selected_analysts={
        'tech': True,
        'fund': True,
        'capital': True,
        'risk': True,
        'market': True
    }
)

# 查看结果
for stock_code, result in results.items():
    print(f"\n{stock_code}:")
    if result.get('success'):
        print(f"  评级: {result['rating']}")
        print(f"  置信度: {result['confidence']}%")
    else:
        print(f"  失败: {result.get('error')}")
```

### 定时自动分析
```python
from portfolio_scheduler import portfolio_scheduler

# 配置调度器
portfolio_scheduler.add_schedule_time("09:30")  # 开盘后
portfolio_scheduler.add_schedule_time("15:05")  # 收盘后
portfolio_scheduler.set_analysis_mode("parallel")  # 并行分析
portfolio_scheduler.set_auto_monitor_sync(True)  # 同步到监测
portfolio_scheduler.set_notification_enabled(True)  # 启用通知

# 启动
if portfolio_scheduler.start():
    print("定时分析已启动")
    print(f"下次运行时间: {portfolio_scheduler.get_next_run_time()}")
```

---

## 9. 环境配置

### .env 文件模板
```env
# Tushare配置（必需）
TUSHARE_TOKEN=your_token_here

# DeepSeek配置（必需）
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 邮件通知（可选）
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_TO_EMAIL=recipient@gmail.com

# Webhook通知（可选）
WEBHOOK_URL=https://your.webhook.url
WEBHOOK_KEYWORD=股票分析
```

### proxy_config.json 模板
```json
{
  "proxy_priority": [
    {
      "name": "直连模式",
      "proxy": null,
      "enabled": true,
      "priority": 1,
      "description": "不使用代理"
    },
    {
      "name": "本地代理",
      "proxy": "http://127.0.0.1:7890",
      "enabled": true,
      "priority": 2,
      "description": "本地Clash代理"
    }
  ],
  "use_proxy": false
}
```

---

## 10. 故障排查

### 常见问题

**Q1: 数据获取失败**
```python
# 检查数据源状态
from data_source_manager import data_source_manager
print(f"Tushare可用: {data_source_manager.tushare_available}")

# 检查网络
from network_optimizer import network_optimizer
print(f"网络连接: {network_optimizer.test_network_connection()}")
```

**Q2: AI分析失败**
```python
# 检查DeepSeek配置
import os
print(f"API Key: {os.getenv('DEEPSEEK_API_KEY')[:10]}...")
print(f"Base URL: {os.getenv('DEEPSEEK_BASE_URL')}")
```

**Q3: 持仓数据库错误**
```python
# 检查数据库
from portfolio_db import portfolio_db
stocks = portfolio_db.get_all_stocks()
print(f"持仓数量: {len(stocks)}")
```

---

**文档版本**: v1.0  
**最后更新**: 2025-11-01  
**维护者**: AI Assistant  

**相关文档**:
- 完整文档: `docs/核心模块说明.md`
- 快速开始: `docs/QUICK_START.md`
- 更新日志: `docs/UPDATE_LOG.md`

