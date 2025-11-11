# TDX API 扩展接口诊断报告

> 测试时间：2025-11-10 19:20 CST（脚本：`scripts/test_tdx_all_api.py --verbose --output tmp/tdx_api_test_results.json`）

## 1. 测试环境
- 基础地址：`http://localhost:8080`
- 样例股票：`000001`（平安银行）、`600000`、`601318`
- 指数：`sh000001`
- 历史区间：`2024-10-11` 至 `2024-11-10`
- 超时：10 秒

完整原始结果保存在 `tmp/tdx_api_test_results.json`。

## 2. 失败接口详情

| 接口 | 请求示例 | 期望行为 | 实际响应/错误 | 初步诊断 |
|------|----------|----------|---------------|-----------|
| `GET /api/kline-all` | `GET /api/kline-all?code=000001&type=day&limit=200` | 返回全量或指定上限的历史 K 线数组 | HTTP 200，`{"code":0,"message":"success","data":[]}` | 服务端路由存在，但未返回数据；推测接口尚未实现或数据源为空，需要补充 `handleGetKlineAll` 逻辑。 |
| `GET /api/index/all` | `GET /api/index/all?code=sh000001&type=day&limit=200` | 返回指数历史 K 线数组 | HTTP 200，`data=[]` | 同上，未获取任何数据；确认指数全量接口实现。 |
| `GET /api/trade-history/full` | `GET /api/trade-history/full?code=000001&before=2024-11-10&limit=300` | 在限制内返回上市以来成交明细 | 10 秒内无响应 → `ReadTimeout` | 接口可能执行全量扫描，未做分页或默认参数过大；需检查后台是否实现以及读取策略。 |
| `GET /api/workday/range` | `GET /api/workday/range?start=2024-11-01&end=2024-11-10` | 返回起止区间内所有交易日 | HTTP 200，`data=[]` | 交易日历数据缺失或接口未实现；需加载交易日历并返回结果。 |
| `POST /api/tasks/{id}/cancel`（附带） | `POST /api/tasks/<新建任务>/cancel` | 返回 `code=0` 并进入 `cancelled` 状态 | `{"code":-1,"message":"任务不存在或已结束"}` | 新建的任务在取消请求之前已变为 `success`；需要在后台提升任务状态同步或在取消接口增加幂等处理。 |

## 3. 后续建议
1. 确认 Go 服务端是否已合并 `server_api_extended.go` 中对应处理函数；若不存在，实现并注册路由。
2. `trade-history/full` 建议：
   - 支持 `start/limit` 或游标模式，避免一次性拉取全部数据。
   - 增加服务器端超时/流式写出，客户端可适当提升超时或按交易日分批调用。
3. `workday/range` 需依赖交易日历数据源（`trading_calendar` 表或本地 JSON）；调用前加载并返回。
4. 任务取消接口应支持任务已结束时返回成功或明确状态，便于脚本幂等调用。
5. 修复后重新执行 `test_tdx_all_api.py` 并更新 `tmp/tdx_api_test_results.json`，同步文档状态。

## 4. 参考
- 测试脚本：`scripts/test_tdx_all_api.py`
- 自动化输出：`tmp/tdx_api_test_results.json`
- 相关文档：`tdx_doc/API_接口文档.md`, `tdx_doc/API_集成指南.md`
