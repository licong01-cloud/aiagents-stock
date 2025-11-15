# 自选股票池执行步骤

## 阶段一：Schema 与仓储
1. 初始化/升级应用 Schema
   - 运行：`python scripts/init_app_schema.py`
   - 结果：创建 `app.watchlist_categories`、`app.watchlist_items`，索引与默认分类
2. 数据验证
   - 运行：`python scripts/verify_app_data.py`
   - 结果：打印各表行数；包含 watchlist 表与 Top 样例
3. 仓储冒烟
   - 运行：`python scripts/smoke_watchlist_repo.py`
   - 步骤：创建分类→添加单/批→分页查询→迁移分类→删除→清理分类

## 阶段二：UI 管理页
1. 入口
   - `app.py` 选股模块新增“⭐ 自选股票池（管理）”按钮
2. 管理页功能（watchlist_ui.py）
   - 单/批量添加，支持“存在则移动”
   - 分类标签、创建/重命名/删除（删除需空分类）
   - 分页与排序：
     - 服务端：code/name/category/created_at/updated_at/last_analysis_time
     - 客户端：last/pct_change/open/prev_close/high/low/volume_hand/amount_li
   - 实时行情：TDX 批量获取，缓存 TTL 3s；刷新/自动刷新
   - 批量操作：改分类、删除、批量分析（跳转主力选股批量流程）
   - 历史链接：跳转历史页并预填搜索词

## 阶段三：选股页集成
1. 主力选股页（main_force_ui.py）
   - “➕ 添加到自选股票池”面板
   - 支持选择候选列表中的多个代码添加到指定分类
   - 代码归一化为 ts_code；存在则可选择移动

## 注意
- 代码规范化：UI 写入 watchlist 使用 tushare ts_code（如 000001.SZ）
- 实时请求：TDX 实时接口需要 6 位代码，UI 会从 ts_code 转回 6 位
- 计量换算：
  - volume_hand = volume/100（股→手）
  - amount_li = amount*1000（元→厘），若源单位不同以接口为准
- 历史页支持从 session 预填搜索词

## 回归与验证
- verify_app_data.py 检查 watchlist 表计数
- smoke_watchlist_repo.py 执行 CRUD 冒烟
- 手动在 app 界面验证：添加/分页/排序/实时行情/批量分析跳转
