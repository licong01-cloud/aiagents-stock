# 自选股票池功能设计

## 概述
- 目标：提供可管理的自选股票池，支持单/批量添加、分类管理、分页与排序、实时行情展示、链接分析历史与批量分析。
- 范围：阶段一为股票池管理；阶段二在主力选股等页面集成“添加到自选”。

## 数据模型
- app.watchlist_categories
  - id BIGSERIAL PK
  - name TEXT UNIQUE NOT NULL
  - description TEXT NULL
  - created_at TIMESTAMPTZ DEFAULT now()
  - updated_at TIMESTAMPTZ DEFAULT now()
  - 初始化：插入一条 name="默认"
- app.watchlist_items
  - id BIGSERIAL PK
  - code TEXT UNIQUE NOT NULL（与 TDX/analysis_records 的 ts_code 一致）
  - name TEXT NOT NULL（TDX 基本信息）
  - category_id BIGINT NOT NULL REFERENCES app.watchlist_categories(id)
  - note TEXT NULL
  - created_at TIMESTAMPTZ DEFAULT now()
  - updated_at TIMESTAMPTZ DEFAULT now()
- 索引
  - watchlist_items(code)
  - watchlist_items(category_id, updated_at DESC)
  - analysis_records(ts_code, analysis_date DESC)
- 最新分析拼接（运行时）
  - LATERAL 子查询按 code 从 app.analysis_records 拉最新一条
  - last_analysis_time = analysis_date
  - last_rating = final_decision.rating 或 agents_results.final_decision.rating
  - last_conclusion = final_decision.advice 或 agents_results.final_decision.advice 或 discussion_result.summary

## 实时行情字段
- 展示
  - 最新价 last
  - 涨幅% pct_change = (last - prev_close)/prev_close*100（prev_close<=0 时 N/A）
  - 开盘 open
  - 昨收 prev_close
  - 最高 high
  - 最低 low
  - 成交量（手）volume_hand = volume/100
  - 成交额（厘）amount_li = amount(元)*1000（若源单位不同以接口为准）
- 获取
  - UI 层批量调用 TDX 实时行情（以当前页或全部 codes），内存缓存 TTL 2-5 秒，提供“刷新”和自动刷新开关

## 排序设计
- 服务端排序（持久字段，DAL）
  - code、name、category（c.name）、created_at、updated_at、last_analysis_time（a.analysis_date）、last_rating（可选）
  - 方向 asc/desc；NULLS LAST；二级排序 i.code ASC；字段白名单防注入
  - 评级映射（可选）：买入=2 > 持有=1 > 卖出=0（CASE）
- 客户端排序（实时字段，UI）
  - last、pct_change、open、prev_close、high、low、volume_hand、amount_li
  - 策略：优先全量行情→内存排序→分页；过阈值（如 >2000）自动退化为“页内排序”；同值按 code ASC 兜底

## UI/交互
- 管理页（watchlist_ui）
  - 顶部：分类标签（全部+各分类）、排序字段/方向、每页数量、自动刷新/刷新
  - 添加：单只添加（支持新建分类）、批量添加（逗号分隔，存在可选择“移动到本分类”）
  - 列表：选择框 | 代码 | 名称 | 分类 | last | pct% | open | prev_close | high | low | 量(手) | 额(厘) | 最近结论 | 分析时间 | 历史
  - 批量操作：批量改分类、批量删除、批量分析（传 codes 至既有分析流程）
  - 历史链接：跳转“历史记录”页，并预填 code 搜索
- 选股页集成（阶段二）
  - 主力选股/其他选股结果行前加选择框
  - 提供“添加到自选”与分类选择，批量导入 watchlist

## 性能与稳定性
- 稳定分页：服务端排序追加二级 i.code ASC
- 索引：见数据模型
- 缓存：行情缓存 TTL 2-5 秒，控制刷新频率
- 缺失值：统一显示 N/A；排序使用 NULLS LAST

## 校验与约束
- code 统一为 ts_code 格式（与 TDX/analysis_records 一致）
- 分类删除需空分类（UI 提供批量迁移）
- 批量添加重复：支持忽略或移动到目标分类

## 文件与模块
- scripts/init_app_schema.py：新增 watchlist 两表与索引，插入默认分类
- pg_watchlist_repo.py：仓储（CRUD、分页与排序、最新分析 JOIN）
- watchlist_ui.py：管理页（添加、分页、排序、分类管理、实时行情、批量操作、历史链接）
- app.py：在选股模块增加“⭐ 自选股票池（管理）”入口并路由到管理页
- scripts/smoke_watchlist_repo.py：仓储冒烟测试
- scripts/verify_app_data.py：增加 watchlist 表统计
