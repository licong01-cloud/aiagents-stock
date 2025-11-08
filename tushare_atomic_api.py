"""
Tushare Atomic API Module

- 独立于现有统一数据获取模块，不修改任何现有代码
- 每个接口原子化封装，可独立调用或在上层组合
- 支持环境变量 TUSHARE_TOKEN 或显式传入 token 初始化
- 对所有接口提供统一的 pro.query(api_name, **params) 泛化调用
- 为股票数据、ETF 专题、指数专题、大模型语料专题建立元数据注册与示例

使用示例：
    from tushare_atomic_api import TushareAtomicClient
    cli = TushareAtomicClient()  # 或 TushareAtomicClient(token="YOUR_TOKEN")
    df = cli.call("daily", ts_code="000001.SZ", start_date="20240101", end_date="20241231")

注意：
- 本模块仅聚焦接口访问与字段/内容说明，不处理积分限制与重试策略
- 针对文档命名差异，保留官方文档链接，优先使用 pro.query 的 api_name 直连
- 若 SDK 中未提供专用便捷方法，均可使用 cli.call("api_name", **params)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import sys
import traceback

import pandas as pd

try:
    import tushare as ts
except Exception as _e:  # 延迟到使用时报错
    ts = None  # type: ignore


@dataclass
class EndpointMeta:
    name: str
    category: str
    doc_url: Optional[str] = None
    description: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)  # 参数:说明
    returns: Dict[str, str] = field(default_factory=dict)  # 字段:说明


class TushareAtomicClient:
    """Tushare 原子化访问客户端。

    - 支持环境变量 TUSHARE_TOKEN 初始化；也支持显式传入 token
    - 统一的 call(api_name, **params) 访问入口
    - 提供常用接口的便捷封装方法（等价于 call）
    - 提供 meta 注册与查询，便于快速了解字段含义与参数说明
    """

    def __init__(self, token: Optional[str] = None) -> None:
        if ts is None:
            raise ImportError("tushare 库未安装，请先 pip install tushare")
        self.token: str = token or os.getenv("TUSHARE_TOKEN", "").strip()
        if not self.token:
            raise EnvironmentError("未检测到 TUSHARE_TOKEN，请在环境变量配置或传入 token 参数")
        ts.set_token(self.token)
        self._pro = ts.pro_api()

    # -------------------- 通用与组合能力 --------------------
    def call(self, api_name: str, **params) -> pd.DataFrame:
        """通过 pro.query 直接调用任意 API
        Args:
            api_name: Tushare API 名称（如 'daily', 'index_dailybasic'）
            **params: 接口参数（与文档一致）
        Returns:
            pd.DataFrame，原样返回
        """
        return self._pro.query(api_name, **params)

    def compose(self, *steps: Callable[["TushareAtomicClient"], Any]) -> List[Any]:
        """顺序执行一组步骤（上层可用于组合原子接口）"""
        out: List[Any] = []
        for step in steps:
            out.append(step(self))
        return out

    # -------------------- 便捷封装：股票数据 --------------------
    def stock_basic(self, **params) -> pd.DataFrame:
        """股票基础列表
        文档: https://tushare.pro/document/2?doc_id=25
        典型参数: exchange, list_status, fields
        常见返回: ts_code, symbol, name, area, industry, market, list_date, is_hs
        """
        return self.call("stock_basic", **params)

    def trade_cal(self, **params) -> pd.DataFrame:
        """交易日历
        文档: https://tushare.pro/document/2?doc_id=26
        参数: exchange, start_date, end_date
        返回: exchange, cal_date, is_open, pretrade_date
        """
        return self.call("trade_cal", **params)

    def stock_st(self, **params) -> pd.DataFrame:
        """ST 股票列表
        文档: https://tushare.pro/document/2?doc_id=397
        参数: trade_date
        返回: ts_code, name, type, type_name 等
        """
        return self.call("stock_st", **params)

    def stock_hsgt(self, **params) -> pd.DataFrame:
        """沪深港通股票列表
        文档: https://tushare.pro/document/2?doc_id=398
        参数: trade_date, type
        返回: ts_code, name, type, type_name 等
        """
        return self.call("stock_hsgt", **params)

    def bse_mapping(self, **params) -> pd.DataFrame:
        """北交所新旧代码对照
        文档: https://tushare.pro/document/2?doc_id=375
        参数: o_code, n_code
        返回: name, o_code, n_code, list_date 等
        """
        return self.call("bse_mapping", **params)

    def namechange(self, **params) -> pd.DataFrame:
        """股票曾用名
        文档: https://tushare.pro/document/2?doc_id=100
        参数: ts_code, start_date, end_date
        返回: ts_code, name, start_date, end_date, change_reason
        """
        return self.call("namechange", **params)

    def stock_company(self, **params) -> pd.DataFrame:
        """上市公司基本信息
        文档: https://tushare.pro/document/2?doc_id=112
        参数: ts_code, exchange
        返回: chairman, manager, secretary, reg_capital, setup_date, province, city, website 等
        """
        return self.call("stock_company", **params)

    def new_share(self, **params) -> pd.DataFrame:
        """IPO 新股列表
        文档: https://tushare.pro/document/2?doc_id=123
        参数: start_date, end_date
        返回: ts_code, sub_code, name, ipo_date, issue_date, amount, market_amount
        """
        return self.call("new_share", **params)

    def daily(self, **params) -> pd.DataFrame:
        """日线行情
        文档: https://tushare.pro/document/2?doc_id=27
        参数: ts_code, trade_date, start_date, end_date
        返回: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        """
        return self.call("daily", **params)

    def stk_week_month_adj(self, **params) -> pd.DataFrame:
        """复权周/月线行情
        文档: https://tushare.pro/document/2?doc_id=365
        参数: ts_code, freq, start_date, end_date
        返回: 复权周/月K数据
        """
        return self.call("stk_week_month_adj", **params)

    def stk_weekly_monthly(self, **params) -> pd.DataFrame:
        """周/月线行情（每日更新）
        文档: https://tushare.pro/document/2?doc_id=336
        参数: trade_date, freq, ts_code
        返回: trade_date, end_date, close, change, pct_chg 等
        """
        return self.call("stk_weekly_monthly", **params)

    def bak_basic(self, **params) -> pd.DataFrame:
        """备用行情-基础信息（退市等扩展口径）
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: trade_date, ts_code 等
        返回: 不同于常规模块的扩展基础口径
        """
        return self.call("bak_basic", **params)

    def bak_daily(self, **params) -> pd.DataFrame:
        """备用行情-日线
        文档: https://tushare.pro/document/2?doc_id=255
        参数: trade_date, start_date, end_date, ts_code
        返回: 与常规模块口径差异的日线字段
        """
        return self.call("bak_daily", **params)

    def bak_weekly(self, **params) -> pd.DataFrame:
        """备用行情-周线
        文档: https://tushare.pro/document/2?doc_id=171
        参数: trade_date, start_date, end_date, ts_code
        返回: 备用口径周线指标
        """
        return self.call("bak_weekly", **params)

    def bak_monthly(self, **params) -> pd.DataFrame:
        """备用行情-月线
        文档: https://tushare.pro/document/2?doc_id=171
        参数: trade_date, start_date, end_date, ts_code
        返回: 备用口径月线指标
        """
        return self.call("bak_monthly", **params)

    def weekly(self, **params) -> pd.DataFrame:
        """周线行情
        文档: https://tushare.pro/document/2?doc_id=27
        参数: ts_code, start_date, end_date
        返回: open, high, low, close, vol, amount
        """
        return self.call("weekly", **params)

    def monthly(self, **params) -> pd.DataFrame:
        """月线行情
        文档: https://tushare.pro/document/2?doc_id=27
        参数: ts_code, start_date, end_date
        返回: open, high, low, close, vol, amount
        """
        return self.call("monthly", **params)

    def pro_bar(self, **params) -> pd.DataFrame:
        """通用行情（集成接口，含分钟/复权等）
        文档: https://tushare.pro/document/2?doc_id=109
        参数: ts_code, start_date, end_date, asset, adj, freq, ma 等
        返回: 按参数返回的行情数据
        """
        if ts is None:
            raise ImportError("tushare 库未安装，请先 pip install tushare")
        return ts.pro_bar(**params)

    def stk_mins(self, **params) -> pd.DataFrame:
        """A股历史分钟行情
        文档: https://tushare.pro/document/2?doc_id=370
        参数: ts_code, freq, start_date, end_date
        返回: trade_time, open, high, low, close, vol, amount 等
        """
        return self.call("stk_mins", **params)

    def rt_min(self, **params) -> pd.DataFrame:
        """A股实时分钟行情
        文档: https://tushare.pro/document/2?doc_id=374
        参数: ts_code, freq
        返回: trade_time, open, high, low, close, vol, amount 等
        """
        if not hasattr(self._pro, "rt_min"):
            raise AttributeError("tushare pro 实例不支持 rt_min，请检查版本/权限")
        return getattr(self._pro, "rt_min")(**params)

    def rt_min_daily(self, **params) -> pd.DataFrame:
        """A股当日实时分钟全量行情
        文档: https://tushare.pro/document/2?doc_id=374
        参数: ts_code, freq
        返回: trade_time, open, high, low, close, vol, amount 等
        """
        if not hasattr(self._pro, "rt_min_daily"):
            raise AttributeError("tushare pro 实例不支持 rt_min_daily，请检查版本/权限")
        return getattr(self._pro, "rt_min_daily")(**params)

    def rt_k(self, **params) -> pd.DataFrame:
        """沪深京实时日线行情
        文档: https://tushare.pro/document/2?doc_id=372
        参数: ts_code
        返回: name, pre_close, open, high, low, close, vol, amount, num
        """
        if not hasattr(self._pro, "rt_k"):
            raise AttributeError("tushare pro 实例不支持 rt_k，请检查版本/权限")
        return getattr(self._pro, "rt_k")(**params)

    def rt_stock_k(self, **params) -> pd.DataFrame:
        """兼容入口：同 rt_k"""
        return self.rt_k(**params)

    def adj_factor(self, **params) -> pd.DataFrame:
        """复权因子
        文档: https://tushare.pro/document/2?doc_id=28
        参数: ts_code, trade_date, start_date, end_date
        返回: ts_code, trade_date, adj_factor
        """
        return self.call("adj_factor", **params)

    def suspend_d(self, **params) -> pd.DataFrame:
        """停复牌信息
        文档: https://tushare.pro/document/2?doc_id=31
        参数: ts_code, trade_date, start_date, end_date
        返回: ts_code, suspend_date, resume_date, suspend_reason
        """
        return self.call("suspend_d", **params)

    def stk_limit(self, **params) -> pd.DataFrame:
        """涨跌停价格
        文档: https://tushare.pro/document/2?doc_id=183
        参数: ts_code, trade_date, start_date, end_date
        返回: up_limit, down_limit 等
        """
        return self.call("stk_limit", **params)

    def daily_basic(self, **params) -> pd.DataFrame:
        """每日行情指标
        文档: https://tushare.pro/document/2?doc_id=32
        参数: ts_code, trade_date, start_date, end_date, fields
        返回: turnover_rate, volume_ratio, pe, pe_ttm, pb, total_mv, circ_mv 等
        """
        return self.call("daily_basic", **params)

    def daily_info(self, **params) -> pd.DataFrame:
        """市场每日统计（沪深市场成交额/量等合计）
        文档: https://tushare.pro/document/2?doc_id=258
        参数: start_date, end_date
        返回: ts_code(如 SH_MARKET/SZ_MARKET), trade_date, vol, amount 等
        """
        return self.call("daily_info", **params)

    def moneyflow(self, **params) -> pd.DataFrame:
        """个股主力资金流向（收盘后更新）
        文档: https://tushare.pro/document/2?doc_id=170
        参数: ts_code, trade_date, start_date, end_date
        返回: buy_sm_vol, sell_sm_vol, buy_md_vol, buy_lg_vol, buy_elg_vol, net_mf_vol 等
        """
        return self.call("moneyflow", **params)

    def moneyflow_ths(self, **params) -> pd.DataFrame:
        """资金流（同花顺口径）
        文档: https://tushare.pro/document/2?doc_id=348
        参数: ts_code, trade_date, start_date, end_date
        返回: 不同口径的净流入、净额字段
        """
        return self.call("moneyflow_ths", **params)

    def moneyflow_dc(self, **params) -> pd.DataFrame:
        """大单成交（资金流明细/大单）
        文档: https://tushare.pro/document/2?doc_id=349
        参数: ts_code, trade_date, start_date, end_date
        返回: 大单买卖成交与净额
        """
        return self.call("moneyflow_dc", **params)

    # -------- 财务报表与指标（股票基础专题内） --------
    def income(self, **params) -> pd.DataFrame:
        """利润表
        文档: https://tushare.pro/document/2?doc_id=33
        参数: ts_code, period, start_date, end_date
        返回: 营业收入、营业利润、净利润等
        """
        return self.call("income", **params)

    def balancesheet(self, **params) -> pd.DataFrame:
        """资产负债表
        文档: https://tushare.pro/document/2?doc_id=36
        参数: ts_code, period, start_date, end_date
        返回: 资产、负债、所有者权益等
        """
        return self.call("balancesheet", **params)

    def cashflow(self, **params) -> pd.DataFrame:
        """现金流量表
        文档: https://tushare.pro/document/2?doc_id=44
        参数: ts_code, period, start_date, end_date
        返回: 经营/投资/筹资现金流量等
        """
        return self.call("cashflow", **params)

    def fina_indicator(self, **params) -> pd.DataFrame:
        """财务指标数据
        文档: https://tushare.pro/document/2?doc_id=79
        参数: ts_code, period, start_date, end_date
        返回: roe, roa, grossprofit_margin 等
        """
        return self.call("fina_indicator", **params)

    def fina_audit(self, **params) -> pd.DataFrame:
        """财务审计意见
        文档: https://tushare.pro/document/2?doc_id=80
        参数: ts_code, period, start_date, end_date
        返回: audit_result, auditor 等
        """
        return self.call("fina_audit", **params)

    def dividend(self, **params) -> pd.DataFrame:
        """分红送股
        文档: https://tushare.pro/document/2?doc_id=103
        参数: ts_code, end_date, imp_ann_date
        返回: 分红送转方案等
        """
        return self.call("dividend", **params)

    def forecast(self, **params) -> pd.DataFrame:
        """业绩预告
        文档: https://tushare.pro/document/2?doc_id=45
        参数: ts_code, period, ann_date
        返回: 预告类型、变动幅度等
        """
        return self.call("forecast", **params)

    def express(self, **params) -> pd.DataFrame:
        """业绩快报
        文档: https://tushare.pro/document/2?doc_id=46
        参数: ts_code, period, ann_date
        返回: 营收/利润快报等
        """
        return self.call("express", **params)

    def fina_mainbz(self, **params) -> pd.DataFrame:
        """主营业务构成
        文档: https://tushare.pro/document/2?doc_id=81
        参数: ts_code, period, type
        返回: bz_item, bz_sales, bz_profit, bz_cost 等
        """
        return self.call("fina_mainbz", **params)

    def announcement(self, **params) -> pd.DataFrame:
        """上市公司公告
        文档: https://tushare.pro/document/2?doc_id=176
        参数: ts_code, ann_date, start_date, end_date, category
        返回: 公告标题、摘要、公告类型、公告链接等
        """
        return self.call("announcement", **params)

    def stk_managers(self, **params) -> pd.DataFrame:
        """管理层信息
        文档: https://tushare.pro/document/2?doc_id=193
        参数: ts_code, ann_date, start_date, end_date
        返回: name, gender, edu, title, begin_date, end_date 等
        """
        return self.call("stk_managers", **params)

    def stk_rewards(self, **params) -> pd.DataFrame:
        """管理层薪酬/持股
        文档: https://tushare.pro/document/2?doc_id=194
        参数: ts_code, ann_date, start_date, end_date
        返回: name, title, reward, holding 等
        """
        return self.call("stk_rewards", **params)

    def concept(self, **params) -> pd.DataFrame:
        """概念列表（板块/主题）
        文档: https://tushare.pro/document/2?doc_id=147
        参数: src
        返回: code, name, src 等
        """
        return self.call("concept", **params)

    def concept_detail(self, **params) -> pd.DataFrame:
        """概念成分明细
        文档: https://tushare.pro/document/2?doc_id=148
        参数: id/code, ts_code
        返回: id, ts_code, name, in_date, out_date 等
        """
        return self.call("concept_detail", **params)

    def moneyflow_hsgt(self, **params) -> pd.DataFrame:
        """沪深港通资金流向（日）
        文档: https://tushare.pro/document/2?doc_id=47
        参数: trade_date, start_date, end_date
        返回: north_money, south_money 等
        """
        return self.call("moneyflow_hsgt", **params)

    def hsgt_top10(self, **params) -> pd.DataFrame:
        """沪深港通每日前十大成交股
        文档: https://tushare.pro/document/2?doc_id=48
        参数: trade_date, market
        返回: ts_code, name, net_amount, buy, sell 等
        """
        return self.call("hsgt_top10", **params)

    def hk_hold(self, **params) -> pd.DataFrame:
        """沪深港通持股明细（港资持股）
        文档: https://tushare.pro/document/2?doc_id=188
        参数: ts_code, trade_date, start_date, end_date
        返回: vol, ratio 等
        """
        return self.call("hk_hold", **params)

    def ggt_daily(self, **params) -> pd.DataFrame:
        """港股通每日交易统计
        文档: https://tushare.pro/document/2?doc_id=196
        参数: trade_date, start_date, end_date
        返回: hgt_amount, sgt_amount, north_money, south_money 等
        """
        return self.call("ggt_daily", **params)

    def ggt_top10(self, **params) -> pd.DataFrame:
        """港股通每日前十大成交股
        文档: https://tushare.pro/document/2?doc_id=49
        参数: trade_date
        返回: ts_code, name, net_amount, buy, sell 等
        """
        return self.call("ggt_top10", **params)

    def ggt_monthly(self, **params) -> pd.DataFrame:
        """港股通每月成交统计
        文档: https://tushare.pro/document/2?doc_id=50
        参数: month
        返回: 月度成交情况
        """
        return self.call("ggt_monthly", **params)

    def block_trade(self, **params) -> pd.DataFrame:
        """大宗交易
        文档: https://tushare.pro/document/2?doc_id=161
        参数: ts_code, trade_date, start_date, end_date
        返回: price, vol, amount, buyer, seller 等
        """
        return self.call("block_trade", **params)

    def repurchase(self, **params) -> pd.DataFrame:
        """股份回购
        文档: https://tushare.pro/document/2?doc_id=124
        参数: ts_code, ann_date, start_date, end_date
        返回: 回购方案与进度等
        """
        return self.call("repurchase", **params)

    def pledge_stat(self, **params) -> pd.DataFrame:
        """股权质押统计
        文档: https://tushare.pro/document/2?doc_id=110
        参数: ts_code
        返回: 质押数量、比例等
        """
        return self.call("pledge_stat", **params)

    def pledge_detail(self, **params) -> pd.DataFrame:
        """股权质押明细
        文档: https://tushare.pro/document/2?doc_id=111
        参数: ts_code
        返回: 质押起始日、数量、质权人等
        """
        return self.call("pledge_detail", **params)

    def stk_holdernumber(self, **params) -> pd.DataFrame:
        """股东户数
        文档: https://tushare.pro/document/2?doc_id=166
        参数: ts_code, enddate, start_date, end_date
        返回: enddate, holder_num 等
        """
        return self.call("stk_holdernumber", **params)

    def stk_holdertrade(self, **params) -> pd.DataFrame:
        """股东增减持统计
        文档: https://tushare.pro/document/2?doc_id=175
        参数: ts_code, ann_date, start_date, end_date
        返回: holder_name, in_de, change_vol, change_ratio 等
        """
        return self.call("stk_holdertrade", **params)

    def top10_holders(self, **params) -> pd.DataFrame:
        """前十大股东
        文档: https://tushare.pro/document/2?doc_id=61
        参数: ts_code, period, ann_date
        返回: holder_name, hold_ratio, hold_amount 等
        """
        return self.call("top10_holders", **params)

    def top10_floatholders(self, **params) -> pd.DataFrame:
        """前十大流通股东
        文档: https://tushare.pro/document/2?doc_id=62
        参数: ts_code, period, ann_date
        返回: holder_name, hold_ratio, hold_amount 等
        """
        return self.call("top10_floatholders", **params)

    def limit_list_d(self, **params) -> pd.DataFrame:
        """每日涨跌停与炸板统计
        文档: https://tushare.pro/document/2?doc_id=298
        参数: trade_date, start_date, end_date
        返回: ts_code, name, close, pct_change, limit, is_new, first_time, last_time 等
        """
        return self.call("limit_list_d", **params)

    def top_list(self, **params) -> pd.DataFrame:
        """龙虎榜每日明细（上榜个股）
        文档: https://tushare.pro/document/2?doc_id=51
        参数: trade_date, ts_code
        返回: 买卖金额、净额、类型、原因等
        """
        return self.call("top_list", **params)

    def top_inst(self, **params) -> pd.DataFrame:
        """龙虎榜机构成交明细
        文档: https://tushare.pro/document/2?doc_id=52
        参数: trade_date, ts_code
        返回: 机构买卖金额与席位等
        """
        return self.call("top_inst", **params)

    def ths_index(self, **params) -> pd.DataFrame:
        """同花顺概念/行业指数列表
        文档: https://tushare.pro/document/2?doc_id=278
        参数: ts_code, exchange, type 等
        返回: ts_code, name, count, exchange, type 等
        """
        return self.call("ths_index", **params)

    def ths_member(self, **params) -> pd.DataFrame:
        """同花顺概念/行业成分明细
        文档: https://tushare.pro/document/2?doc_id=279
        参数: ts_code（概念/行业代码）
        返回: ts_code(成分股), name, in_date, out_date 等
        """
        return self.call("ths_member", **params)

    def hk_daily_adj(self, **params) -> pd.DataFrame:
        """港股复权行情（含市值/换手等指标）
        文档: https://tushare.pro/document/2?doc_id=339
        参数: ts_code, start_date, end_date, trade_date
        返回: open, high, low, close, vol, amount, turnover_rate 等
        """
        return self.call("hk_daily_adj", **params)

    def hk_mins(self, **params) -> pd.DataFrame:
        """港股分钟行情
        文档: https://tushare.pro/document/2?doc_id=304
        参数: ts_code, freq, start_date, end_date
        返回: trade_time, open, high, low, close, vol, amount
        """
        return self.call("hk_mins", **params)

    def margin(self, **params) -> pd.DataFrame:
        """融资融券汇总（市场级）
        文档: https://tushare.pro/document/2?doc_id=58
        参数: trade_date, start_date, end_date
        返回: rzye(融资余额), rzmre(融资买入额), rqye(融券余额), rqmcl(融券卖出量) 等
        """
        return self.call("margin", **params)

    def margin_detail(self, **params) -> pd.DataFrame:
        """融资融券明细（个股级）
        文档: https://tushare.pro/document/2?doc_id=59
        参数: ts_code, trade_date, start_date, end_date
        返回: rzye, rzmre, rzche, rqye, rqmcl, rqchl 等
        """
        return self.call("margin_detail", **params)

    def margin_secs(self, **params) -> pd.DataFrame:
        """融资融券标的（盘前更新）
        文档: https://tushare.pro/document/2?doc_id=326
        参数: trade_date, exchange, ts_code
        返回: trade_date, ts_code, name, exchange 等
        """
        return self.call("margin_secs", **params)

    def margin_target(self, **params) -> pd.DataFrame:
        """融资融券标的列表
        文档: https://tushare.pro/document/2?doc_id=326  (同 margin_secs)
        参数: trade_date, exchange
        返回: 标的证券列表
        """
        return self.call("margin_target", **params)

    def margin_target_detail(self, **params) -> pd.DataFrame:
        """融资融券标的明细
        文档: https://tushare.pro/document/2
        参数: ts_code, trade_date
        返回: 融资融券标的细项
        """
        return self.call("margin_target_detail", **params)

    def margin_target_amt(self, **params) -> pd.DataFrame:
        """融资融券标的额度
        文档: https://tushare.pro/document/2
        参数: ts_code, trade_date
        返回: 可融可券额度等
        """
        return self.call("margin_target_amt", **params)

    def margin_pledge_stat(self, **params) -> pd.DataFrame:
        """融资融券质押统计
        文档: https://tushare.pro/document/2
        参数: trade_date
        返回: 质押总体情况
        """
        return self.call("margin_pledge_stat", **params)

    def margin_pledge_detail(self, **params) -> pd.DataFrame:
        """融资融券质押明细
        文档: https://tushare.pro/document/2
        参数: trade_date, member_type
        返回: 质押明细数据
        """
        return self.call("margin_pledge_detail", **params)

    def margin_inter_stat(self, **params) -> pd.DataFrame:
        """融资融券互联互通统计
        文档: https://tushare.pro/document/2
        参数: trade_date
        返回: 互联互通统计
        """
        return self.call("margin_inter_stat", **params)

    def margin_inter_detail(self, **params) -> pd.DataFrame:
        """融资融券互联互通明细
        文档: https://tushare.pro/document/2
        参数: trade_date
        返回: 互联互通明细
        """
        return self.call("margin_inter_detail", **params)

    def margin_collateral(self, **params) -> pd.DataFrame:
        """融资融券担保物
        文档: https://tushare.pro/document/2
        参数: trade_date
        返回: 担保物明细
        """
        return self.call("margin_collateral", **params)

    def stock_account(self, **params) -> pd.DataFrame:
        """股票开户数据（新版）
        文档: https://tushare.pro/document/2?doc_id=164
        参数: start_date, end_date
        返回: weekly_new, total, weekly_hold, weekly_trade
        """
        return self.call("stock_account", **params)

    def stock_account_old(self, **params) -> pd.DataFrame:
        """股票开户数据（旧版）
        文档: https://tushare.pro/document/2
        参数: date
        返回: 开户数据（老口径）
        """
        return self.call("stock_account_old", **params)

    def broker_recommend(self, **params) -> pd.DataFrame:
        """券商金股推荐
        文档: https://tushare.pro/document/2?doc_id=267
        参数: month, broker
        返回: 券商推荐列表
        """
        return self.call("broker_recommend", **params)

    def broker_recommend_detail(self, **params) -> pd.DataFrame:
        """券商金股推荐明细
        文档: https://tushare.pro/document/2?doc_id=267
        参数: ts_code, month
        返回: 推荐明细
        """
        return self.call("broker_recommend_detail", **params)

    def report_rc(self, **params) -> pd.DataFrame:
        """券商盈利预测数据（研报结构化）
        文档: https://tushare.pro/document/2?doc_id=292
        参数: ts_code, ann_date, start_date, end_date, period
        返回: org_name, quarter, eps, roe, pe, pb, rating 等
        """
        return self.call("report_rc", **params)

    def cyq_perf(self, **params) -> pd.DataFrame:
        """每日筹码平均成本与胜率
        文档: https://tushare.pro/document/2?doc_id=293
        参数: ts_code, start_date, end_date
        返回: his_low, his_high, cost_5pct, cost_95pct, weight_avg, winner_rate 等
        """
        return self.call("cyq_perf", **params)

    def cyq_chips(self, **params) -> pd.DataFrame:
        """每日筹码分布
        文档: https://tushare.pro/document/2?doc_id=294
        参数: ts_code, start_date, end_date
        返回: price, percent 等
        """
        return self.call("cyq_chips", **params)

    def ccass_hold(self, **params) -> pd.DataFrame:
        """中央结算系统持股汇总
        文档: https://tushare.pro/document/2?doc_id=295
        参数: ts_code, start_date, end_date
        返回: shareholding, hold_nums, hold_ratio 等
        """
        return self.call("ccass_hold", **params)

    def ccass_hold_detail(self, **params) -> pd.DataFrame:
        """中央结算系统持股明细
        文档: https://tushare.pro/document/2?doc_id=274
        参数: ts_code, trade_date, start_date, end_date
        返回: col_participant_id, col_participant_name, col_shareholding 等
        """
        return self.call("ccass_hold_detail", **params)

    def stk_factor(self, **params) -> pd.DataFrame:
        """股票每日技术面因子
        文档: https://tushare.pro/document/2?doc_id=296
        参数: ts_code, trade_date, start_date, end_date, fields
        返回: macd, kdj_k, kdj_d, kdj_j 等技术指标
        """
        return self.call("stk_factor", **params)

    def stk_factor_pro(self, **params) -> pd.DataFrame:
        """股票每日技术面因子（专业版）
        文档: https://tushare.pro/document/2?doc_id=328
        参数: ts_code, trade_date, start_date, end_date, fields
        返回: 指标字段（含前后复权/多周期因子）
        """
        return self.call("stk_factor_pro", **params)

    def stk_auction_o(self, **params) -> pd.DataFrame:
        """股票开盘集合竞价数据
        文档: https://tushare.pro/document/2?doc_id=353
        参数: trade_date, ts_code
        返回: open, high, low, close, vol, amount, vwap 等
        """
        return self.call("stk_auction_o", **params)

    def stk_auction_c(self, **params) -> pd.DataFrame:
        """股票收盘集合竞价数据
        文档: https://tushare.pro/document/2?doc_id=354
        参数: trade_date, ts_code
        返回: close, high, low, vol, amount, vwap 等
        """
        return self.call("stk_auction_c", **params)

    def shhk_daily(self, **params) -> pd.DataFrame:
        """沪深港通指数日度指标
        文档: https://tushare.pro/document/2?doc_id=399
        参数: trade_date, start_date, end_date, market
        返回: north_money, south_money, prem_ratio, ah_p 等
        """
        return self.call("shhk_daily", **params)

    def stk_nineturn(self, **params) -> pd.DataFrame:
        """神奇九转指标
        文档: https://tushare.pro/document/2?doc_id=364
        参数: ts_code, freq, trade_date, start_date, end_date, fields
        返回: up_count, down_count, nine_up_turn, nine_down_turn 等
        """
        return self.call("stk_nineturn", **params)

    def stk_ah_comparison(self, **params) -> pd.DataFrame:
        """AH股比价
        文档: https://tushare.pro/document/2?doc_id=399
        参数: trade_date, ts_code, hk_code, start_date, end_date
        返回: ah_comparison, ah_premium, hk_close, close 等
        """
        return self.call("stk_ah_comparison", **params)

    def stk_surv(self, **params) -> pd.DataFrame:
        """机构调研数据
        文档: https://tushare.pro/document/2?doc_id=275
        参数: ts_code, trade_date, start_date, end_date, fields
        返回: surv_date, fund_visitors, rece_place, rece_mode, rece_org 等
        """
        return self.call("stk_surv", **params)

    def stock_mx(self, **params) -> pd.DataFrame:
        """动能因子数据
        文档: https://tushare.pro/document/2?doc_id=300
        参数: ts_code, trade_date, start_date, end_date
        返回: mx_grade, com_stock, evd_v, zt_sum_z, wma250_z 等
        """
        return self.call("stock_mx", **params)

    def share_float(self, **params) -> pd.DataFrame:
        """限售股解禁/流通股本变动
        文档: https://tushare.pro/document/2?doc_id=108  (若具体 doc_id 以官方为准)
        参数: ts_code, start_date, end_date
        返回: float_date, float_share, reason 等
        """
        return self.call("share_float", **params)

    def float_share(self, **params) -> pd.DataFrame:
        """流通股本变动（另一口径，如有）
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, start_date, end_date
        返回: float_date, float_share 等
        """
        return self.call("float_share", **params)

    def stk_premarket(self, **params) -> pd.DataFrame:
        """盘前股本情况
        文档: https://tushare.pro/document/2?doc_id=329
        参数: trade_date
        返回: total_share, float_share, pre_close, up_limit, down_limit 等
        """
        return self.call("stk_premarket", **params)

    def stk_restrict(self, **params) -> pd.DataFrame:
        """限售股解禁计划
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, end_date, start_date
        返回: restric_type, restric_share, restric_ratio, ann_date, float_date 等
        """
        return self.call("stk_restrict", **params)

    def hs_const(self, **params) -> pd.DataFrame:
        """沪深股通成份股
        文档: https://tushare.pro/document/2?doc_id=104
        参数: hs_type (SH/SZ), is_new
        返回: ts_code, hs_type, in_date, out_date, is_new 等
        """
        return self.call("hs_const", **params)

    # -------------------- 便捷封装：指数专题 --------------------
    def index_basic(self, **params) -> pd.DataFrame:
        """指数基础信息
        文档: https://tushare.pro/document/2?doc_id=94
        参数: market, publisher, category 等
        返回: ts_code, name, fullname, market, publisher, category
        """
        return self.call("index_basic", **params)

    def index_daily(self, **params) -> pd.DataFrame:
        """指数日线
        文档: https://tushare.pro/document/2?doc_id=95
        参数: ts_code, trade_date, start_date, end_date
        返回: open, high, low, close, pre_close, change, pct_chg, vol, amount
        """
        return self.call("index_daily", **params)

    def index_dailybasic(self, **params) -> pd.DataFrame:
        """指数每日指标
        文档: https://tushare.pro/document/2?doc_id=96
        参数: ts_code, trade_date, start_date, end_date
        返回: turnover_rate, turnover_rate_f, pe, pe_ttm, pb, total_mv, float_mv, free_share
        """
        return self.call("index_dailybasic", **params)

    def index_weight(self, **params) -> pd.DataFrame:
        """指数成分权重
        文档: https://tushare.pro/document/2?doc_id=97
        参数: index_code, trade_date, start_date, end_date
        返回: index_code, con_code, trade_date, weight
        """
        return self.call("index_weight", **params)

    def index_classify(self, **params) -> pd.DataFrame:
        """指数分类/列表（扩展）
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: src, category, market 等
        返回: 根据文档为准
        """
        return self.call("index_classify", **params)

    def index_member(self, **params) -> pd.DataFrame:
        """指数成分明细（便于获取成分股列表）
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: index_code, trade_date
        返回: index_code, con_code, in_date, out_date 等
        """
        return self.call("index_member", **params)

    def index_weekly(self, **params) -> pd.DataFrame:
        """指数周线
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, start_date, end_date
        返回: open, high, low, close, vol, amount
        """
        return self.call("index_weekly", **params)

    def index_monthly(self, **params) -> pd.DataFrame:
        """指数月线
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, start_date, end_date
        返回: open, high, low, close, vol, amount
        """
        return self.call("index_monthly", **params)

    # -------------------- 便捷封装：ETF 专题 --------------------
    def fund_basic(self, **params) -> pd.DataFrame:
        """基金基础信息（可用于筛选 ETF）
        文档: https://tushare.pro/document/2?doc_id=43
        过滤: params 中可通过 "market" 或 "fund_type" 过滤 ETF（以文档为准）
        返回: ts_code, name, fund_type, market, list_date 等
        """
        return self.call("fund_basic", **params)

    def fund_daily(self, **params) -> pd.DataFrame:
        """基金/ETF 日线行情
        文档: https://tushare.pro/document/2?doc_id=185
        参数: ts_code, trade_date, start_date, end_date
        返回: open, high, low, close, vol, amount
        """
        return self.call("fund_daily", **params)

    def rt_etf_k(self, **params) -> pd.DataFrame:
        """ETF 实时日线行情
        文档: https://tushare.pro/document/2?doc_id=400
        参数: ts_code, topic
        返回: 实时 ETF 日线 K 数据
        """
        if not hasattr(self._pro, "rt_etf_k"):
            raise AttributeError("tushare pro 实例不支持 rt_etf_k，请检查版本/权限")
        return getattr(self._pro, "rt_etf_k")(**params)

    def fund_nav(self, **params) -> pd.DataFrame:
        """基金净值（部分 ETF 提供/取决于文档）
        文档: https://tushare.pro/document/2?doc_id=44  (若 ETF 专题另有专用文档，以专用为准)
        参数: ts_code, nav_date, start_date, end_date
        返回: ts_code, nav, accum_nav 等
        """
        return self.call("fund_nav", **params)

    def fund_div(self, **params) -> pd.DataFrame:
        """基金分红信息（ETF/基金）
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, ann_date, record_date, ex_date
        返回: 分红方案、每份分红、登记/除权日期等
        """
        return self.call("fund_div", **params)

    def fund_portfolio(self, **params) -> pd.DataFrame:
        """基金/ETF 持仓（若 ETF 专题提供相应表，以其为准）
        文档: https://tushare.pro/document/2?doc_id=47  (示意：请以实际 ETF 持仓接口文档为准)
        参数: ts_code, period
        返回: 持仓明细
        """
        return self.call("fund_portfolio", **params)

    def fund_adj(self, **params) -> pd.DataFrame:
        """基金/ETF 复权因子
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, trade_date, start_date, end_date
        返回: adj_factor 等
        """
        return self.call("fund_adj", **params)

    def fund_share(self, **params) -> pd.DataFrame:
        """基金份额变动（部分 ETF 适用）
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, start_date, end_date
        返回: trade_date, share, change 等
        """
        return self.call("fund_share", **params)

    def fund_company(self, **params) -> pd.DataFrame:
        """基金公司
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: name, fields
        返回: 基金公司信息
        """
        return self.call("fund_company", **params)

    def fund_manager(self, **params) -> pd.DataFrame:
        """基金经理信息
        文档: https://tushare.pro/document/2  (以实际子页为准)
        参数: ts_code, mger_name
        返回: 任职时间、管理基金等
        """
        return self.call("fund_manager", **params)

    # -------------------- 便捷封装：大模型语料专题 --------------------
    def llm_corpus(self, api_name: str, **params) -> pd.DataFrame:
        """大模型语料专题的统一入口（占位）
        说明：Tushare 大模型语料专题包含多个子表，名称可能更新，请使用通用 call：
            cli.call(api_name, **params)
        或通过本方法：cli.llm_corpus("<api_name>", **params)
        我们在元数据注册中提供可能的文档链接与描述，供快速导航。
        """
        return self.call(api_name, **params)

    # -------------------- 元数据注册（用于说明/导航/自检） --------------------

# 分类常量
CATEGORY_STOCK = "stock"
CATEGORY_INDEX = "index"
CATEGORY_ETF = "etf"
CATEGORY_LLM = "llm_corpus"

# 注册表：为每个接口提供文档链接与字段说明（示例/常见字段），便于参考
ENDPOINTS: Dict[str, EndpointMeta] = {
    # 沪深股票（部分清单，完整请参照文档左侧目录；未知项可通过 cli.call 直连）
    "stock_basic": EndpointMeta(
        name="stock_basic", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=25",
        description="股票基础列表",
        params={"exchange": "交易所代码", "list_status": "上市状态", "fields": "返回列"},
        returns={"ts_code": "TS 代码", "name": "名称", "industry": "行业", "list_date": "上市日期"}
    ),
    "trade_cal": EndpointMeta(
        name="trade_cal", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=26",
        description="交易日历",
        params={"exchange": "交易所", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"cal_date": "日期", "is_open": "是否交易日", "pretrade_date": "上一个交易日"}
    ),
    "stock_st": EndpointMeta(
        name="stock_st", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=397",
        description="ST 股票列表",
        params={"trade_date": "交易日"},
        returns={"ts_code": "TS代码", "name": "名称", "type": "类型", "type_name": "类型描述"}
    ),
    "stock_hsgt": EndpointMeta(
        name="stock_hsgt", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=398",
        description="沪深港通股票列表",
        params={"trade_date": "交易日", "type": "列表类型"},
        returns={"ts_code": "TS代码", "name": "名称", "type": "类型", "type_name": "类型描述"}
    ),
    "bse_mapping": EndpointMeta(
        name="bse_mapping", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=375",
        description="北交所新旧代码对照",
        params={"o_code": "旧代码", "n_code": "新代码"},
        returns={"name": "名称", "o_code": "旧代码", "n_code": "新代码", "list_date": "上市日期"}
    ),
    "namechange": EndpointMeta(
        name="namechange", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=100",
        description="股票曾用名",
        params={"ts_code": "TS代码", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"name": "名称", "start_date": "开始日期", "end_date": "结束日期"}
    ),
    "stock_company": EndpointMeta(
        name="stock_company", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=112",
        description="上市公司基本信息",
        params={"ts_code": "TS代码", "exchange": "交易所"},
        returns={}
    ),
    "new_share": EndpointMeta(
        name="new_share", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=123",
        description="IPO 新股列表",
        params={"start_date": "开始日期", "end_date": "结束日期"},
        returns={"ts_code": "TS代码", "ipo_date": "申购日期", "issue_date": "上市日期"}
    ),
    "daily": EndpointMeta(
        name="daily", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=27",
        description="日线行情",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "vol": "成交量", "amount": "成交额"}
    ),
    "bak_basic": EndpointMeta(
        name="bak_basic", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=262",
        description="备用行情-基础信息",
        params={"trade_date": "交易日", "ts_code": "TS代码"},
        returns={}
    ),
    "bak_daily": EndpointMeta(
        name="bak_daily", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=255",
        description="备用行情-日线",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "bak_weekly": EndpointMeta(
        name="bak_weekly", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=171",
        description="备用行情-周线",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "bak_monthly": EndpointMeta(
        name="bak_monthly", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=171",
        description="备用行情-月线",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "weekly": EndpointMeta(
        name="weekly", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=27",
        description="周线行情",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={"open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "vol": "成交量", "amount": "成交额"}
    ),
    "monthly": EndpointMeta(
        name="monthly", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=27",
        description="月线行情",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={"open": "开盘", "close": "收盘", "high": "最高", "low": "最低", "vol": "成交量", "amount": "成交额"}
    ),
    "pro_bar": EndpointMeta(
        name="pro_bar", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=109",
        description="通用行情集成接口（含分钟/复权）",
        params={"ts_code": "代码", "start_date": "开始", "end_date": "结束", "asset": "资产类型", "adj": "复权", "freq": "频率"},
        returns={}
    ),
    "stk_mins": EndpointMeta(
        name="stk_mins", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=370",
        description="A股历史分钟行情",
        params={"ts_code": "TS代码", "freq": "频率", "start_date": "开始", "end_date": "结束"},
        returns={"trade_time": "时间", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "vol": "成交量", "amount": "成交额"}
    ),
    "stk_week_month_adj": EndpointMeta(
        name="stk_week_month_adj", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=365",
        description="复权周/月线行情（每日更新）",
        params={"ts_code": "TS代码", "freq": "频率", "start_date": "开始", "end_date": "结束"},
        returns={"open_qfq": "前复权开盘", "close_qfq": "前复权收盘", "open_hfq": "后复权开盘", "close_hfq": "后复权收盘", "vol": "成交量", "amount": "成交额"}
    ),
    "stk_weekly_monthly": EndpointMeta(
        name="stk_weekly_monthly", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=336",
        description="周/月线行情（每日更新）",
        params={"trade_date": "交易日", "freq": "频率", "ts_code": "TS代码"},
        returns={"end_date": "区间结束日", "close": "收盘价", "change": "涨跌额", "pct_chg": "涨跌幅", "amount": "成交额"}
    ),
    "rt_min": EndpointMeta(
        name="rt_min", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=374",
        description="A股实时分钟行情",
        params={"ts_code": "TS代码", "freq": "频率"},
        returns={}
    ),
    "rt_min_daily": EndpointMeta(
        name="rt_min_daily", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=374",
        description="A股实时分钟-当日全量",
        params={"ts_code": "TS代码", "freq": "频率"},
        returns={}
    ),
    "rt_k": EndpointMeta(
        name="rt_k", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=372",
        description="沪深京实时日线行情",
        params={"ts_code": "代码/通配"},
        returns={"name": "股票名称", "pre_close": "前收", "open": "开盘", "high": "最高", "low": "最低", "close": "最新价", "vol": "成交量", "amount": "成交额", "num": "成交笔数"}
    ),
    "adj_factor": EndpointMeta(
        name="adj_factor", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=28",
        description="复权因子",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={"adj_factor": "复权因子"}
    ),
    "suspend_d": EndpointMeta(
        name="suspend_d", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=31",
        description="停复牌信息",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={"suspend_date": "停牌日期", "resume_date": "复牌日期", "suspend_reason": "原因"}
    ),
    "stk_limit": EndpointMeta(
        name="stk_limit", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=183",
        description="涨跌停价格",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"up_limit": "涨停价", "down_limit": "跌停价"}
    ),
    "daily_basic": EndpointMeta(
        name="daily_basic", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=32",
        description="每日行情指标",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束", "fields": "返回列"},
        returns={"turnover_rate": "换手率", "pe": "市盈率", "pb": "市净率", "total_mv": "总市值", "circ_mv": "流通市值"}
    ),
    "daily_info": EndpointMeta(
        name="daily_info", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=258",
        description="市场每日统计（沪深合计）",
        params={"start_date": "开始", "end_date": "结束"},
        returns={"ts_code": "市场代码", "trade_date": "交易日", "vol": "成交量(亿股)", "amount": "成交额(亿元)"}
    ),
    "moneyflow": EndpointMeta(
        name="moneyflow", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=170",
        description="个股主力资金流向",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"buy_elg_vol": "超大单买入量", "buy_lg_vol": "大单买入量", "net_mf_vol": "资金净流入量"}
    ),
    "moneyflow_ths": EndpointMeta(
        name="moneyflow_ths", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=348",
        description="资金流（同花顺口径）",
        params={"ts_code": "TS代码", "trade_date": "交易日"},
        returns={}
    ),
    "moneyflow_dc": EndpointMeta(
        name="moneyflow_dc", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=349",
        description="大单成交（资金流明细/大单）",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "income": EndpointMeta(
        name="income", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=33",
        description="利润表",
        params={"ts_code": "TS代码", "period": "期间", "start_date": "开始", "end_date": "结束"},
        returns={"revenue": "营业收入", "op_profit": "营业利润", "n_income": "净利润"}
    ),
    "balancesheet": EndpointMeta(
        name="balancesheet", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=36",
        description="资产负债表",
        params={"ts_code": "TS代码", "period": "期间", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "cashflow": EndpointMeta(
        name="cashflow", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=44",
        description="现金流量表",
        params={"ts_code": "TS代码", "period": "期间", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "fina_indicator": EndpointMeta(
        name="fina_indicator", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=79",
        description="财务指标数据",
        params={"ts_code": "TS代码", "period": "期间", "start_date": "开始", "end_date": "结束"},
        returns={"roe": "净资产收益率", "roa": "总资产收益率", "grossprofit_margin": "毛利率"}
    ),
    "fina_audit": EndpointMeta(
        name="fina_audit", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=80",
        description="财务审计意见",
        params={"ts_code": "TS代码", "period": "期间", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "dividend": EndpointMeta(
        name="dividend", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=103",
        description="分红送股",
        params={"ts_code": "TS代码", "end_date": "截止日期", "imp_ann_date": "公告日期"},
        returns={}
    ),
    "forecast": EndpointMeta(
        name="forecast", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=45",
        description="业绩预告",
        params={"ts_code": "TS代码", "period": "期间", "ann_date": "公告日期"},
        returns={}
    ),
    "express": EndpointMeta(
        name="express", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=46",
        description="业绩快报",
        params={"ts_code": "TS代码", "period": "期间", "ann_date": "公告日期"},
        returns={}
    ),
    "fina_mainbz": EndpointMeta(
        name="fina_mainbz", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=81",
        description="主营业务构成",
        params={"ts_code": "TS代码", "period": "报告期", "type": "类别"},
        returns={}
    ),
    "announcement": EndpointMeta(
        name="announcement", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=176",
        description="上市公司公告",
        params={"ts_code": "TS代码", "ann_date": "公告日", "start_date": "开始", "end_date": "结束", "category": "类别"},
        returns={}
    ),
    "stk_managers": EndpointMeta(
        name="stk_managers", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=193",
        description="管理层信息",
        params={"ts_code": "TS代码", "ann_date": "公告日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "stk_rewards": EndpointMeta(
        name="stk_rewards", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=194",
        description="管理层薪酬/持股",
        params={"ts_code": "TS代码", "ann_date": "公告日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "concept": EndpointMeta(
        name="concept", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=147",
        description="概念列表（板块/主题）",
        params={"src": "来源"},
        returns={"code": "概念代码", "name": "概念名称", "src": "来源"}
    ),
    "concept_detail": EndpointMeta(
        name="concept_detail", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=148",
        description="概念成分明细",
        params={"id": "概念ID", "code": "概念代码", "ts_code": "股票代码"},
        returns={"ts_code": "成分股", "in_date": "纳入日期", "out_date": "剔除日期"}
    ),
    "moneyflow_hsgt": EndpointMeta(
        name="moneyflow_hsgt", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=47",
        description="沪深港通资金流向（日）",
        params={"trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"north_money": "北向资金(净)", "south_money": "南向资金(净)"}
    ),
    "hsgt_top10": EndpointMeta(
        name="hsgt_top10", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=48",
        description="沪深港通每日前十大成交股",
        params={"trade_date": "交易日", "market": "市场"},
        returns={"ts_code": "股票代码", "net_amount": "净成交额"}
    ),
    "hk_hold": EndpointMeta(
        name="hk_hold", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=188",
        description="沪深港通持股明细（港资持股）",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"vol": "持股数量", "ratio": "持股比例"}
    ),
    "ggt_daily": EndpointMeta(
        name="ggt_daily", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=196",
        description="港股通每日交易统计",
        params={"trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "ggt_top10": EndpointMeta(
        name="ggt_top10", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=49",
        description="港股通每日前十大成交股",
        params={"trade_date": "交易日"},
        returns={}
    ),
    "ggt_monthly": EndpointMeta(
        name="ggt_monthly", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=197",
        description="港股通每月成交统计",
        params={"month": "月份(YYYYMM)"},
        returns={}
    ),
    "hk_tradecal": EndpointMeta(
        name="hk_tradecal", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=250",
        description="港股交易日历",
        params={"start_date": "开始日期", "end_date": "结束日期"},
        returns={"cal_date": "日期", "is_open": "是否开市", "pretrade_date": "上一交易日"}
    ),
    "block_trade": EndpointMeta(
        name="block_trade", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=161",
        description="大宗交易",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"price": "成交价", "vol": "成交量", "amount": "成交额"}
    ),
    "repurchase": EndpointMeta(
        name="repurchase", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=124",
        description="股份回购",
        params={"ts_code": "TS代码", "ann_date": "公告日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "pledge_stat": EndpointMeta(
        name="pledge_stat", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=110",
        description="股权质押统计",
        params={"ts_code": "TS代码"},
        returns={}
    ),
    "pledge_detail": EndpointMeta(
        name="pledge_detail", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=111",
        description="股权质押明细",
        params={"ts_code": "TS代码"},
        returns={}
    ),
    "stk_holdernumber": EndpointMeta(
        name="stk_holdernumber", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=166",
        description="股东户数",
        params={"ts_code": "TS代码", "enddate": "截止日", "start_date": "开始", "end_date": "结束"},
        returns={"enddate": "截止日", "holder_num": "股东户数"}
    ),
    "stk_holdertrade": EndpointMeta(
        name="stk_holdertrade", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=175",
        description="股东增减持统计",
        params={"ts_code": "TS代码", "ann_date": "公告日", "start_date": "开始", "end_date": "结束"},
        returns={"holder_name": "股东名称", "in_de": "增减类型", "change_vol": "变动数量", "change_ratio": "变动比例"}
    ),
    "top10_holders": EndpointMeta(
        name="top10_holders", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=61",
        description="前十大股东",
        params={"ts_code": "TS代码", "period": "报告期", "ann_date": "公告日"},
        returns={}
    ),
    "top10_floatholders": EndpointMeta(
        name="top10_floatholders", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=62",
        description="前十大流通股东",
        params={"ts_code": "TS代码", "period": "报告期", "ann_date": "公告日"},
        returns={}
    ),
    "limit_list_d": EndpointMeta(
        name="limit_list_d", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=298",
        description="每日涨跌停与炸板统计",
        params={"trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "top_list": EndpointMeta(
        name="top_list", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=106",
        description="龙虎榜每日明细（个股上榜）",
        params={"trade_date": "交易日", "ts_code": "股票代码"},
        returns={}
    ),
    "top_inst": EndpointMeta(
        name="top_inst", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=107",
        description="龙虎榜机构成交明细",
        params={"trade_date": "交易日", "ts_code": "股票代码"},
        returns={}
    ),
    "broker_recommend": EndpointMeta(
        name="broker_recommend", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=267",
        description="券商金股推荐",
        params={"month": "月份(YYYY-MM)", "broker": "券商名称，可选"},
        returns={"ts_code": "股票代码", "name": "股票名称", "industry": "行业", "market": "市场", "weight": "权重"}
    ),
    "broker_recommend_detail": EndpointMeta(
        name="broker_recommend_detail", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=267",
        description="券商金股推荐明细",
        params={"ts_code": "股票代码", "month": "月份(YYYY-MM)", "broker": "券商名称"},
        returns={"trade_date": "推荐日期", "target_price": "目标价", "rating": "评级", "industry": "行业"}
    ),
    "report_rc": EndpointMeta(
        name="report_rc", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=292",
        description="券商盈利预测数据",
        params={"ts_code": "TS代码", "ann_date": "公告日期", "start_date": "开始日期", "end_date": "结束日期", "period": "报告期"},
        returns={"report_date": "研报日期", "org_name": "券商机构", "quarter": "报告季度", "eps": "每股收益预测", "pe": "预测市盈率", "pb": "预测市净率", "rating": "投资评级", "target_price": "目标价"}
    ),
    "cyq_perf": EndpointMeta(
        name="cyq_perf", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=293",
        description="每日筹码平均成本及胜率",
        params={"ts_code": "TS代码", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"trade_date": "交易日期", "his_low": "历史最低价", "his_high": "历史最高价", "cost_5pct": "5%成本价", "cost_95pct": "95%成本价", "weight_avg": "加权平均成本", "winner_rate": "胜率"}
    ),
    "cyq_chips": EndpointMeta(
        name="cyq_chips", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=294",
        description="每日筹码分布",
        params={"ts_code": "TS代码", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"trade_date": "交易日期", "price": "价格档位", "percent": "筹码占比"}
    ),
    "ccass_hold": EndpointMeta(
        name="ccass_hold", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=295",
        description="中央结算系统持股汇总",
        params={"ts_code": "港股代码", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"trade_date": "交易日期", "shareholding": "持股数量", "hold_nums": "参与席位数", "hold_ratio": "持股比例"}
    ),
    "ccass_hold_detail": EndpointMeta(
        name="ccass_hold_detail", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=274",
        description="中央结算系统持股明细",
        params={"ts_code": "港股代码", "trade_date": "交易日期", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"col_participant_id": "参与者ID", "col_participant_name": "参与者名称", "col_shareholding": "持股数量"}
    ),
    "stk_factor": EndpointMeta(
        name="stk_factor", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=296",
        description="股票每日技术面因子",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始日期", "end_date": "结束日期", "fields": "字段列表"},
        returns={"macd": "指数平滑异同移动平均", "kdj_k": "K 值", "kdj_d": "D 值", "kdj_j": "J 值"}
    ),
    "stk_factor_pro": EndpointMeta(
        name="stk_factor_pro", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=328",
        description="股票每日技术面因子（专业版）",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始日期", "end_date": "结束日期", "fields": "字段列表"},
        returns={}
    ),
    "stk_auction_o": EndpointMeta(
        name="stk_auction_o", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=353",
        description="股票开盘集合竞价数据",
        params={"trade_date": "交易日", "ts_code": "TS代码"},
        returns={"open": "开盘价", "high": "最高价", "low": "最低价", "close": "成交价", "vol": "成交量", "amount": "成交额", "vwap": "成交均价"}
    ),
    "stk_auction_c": EndpointMeta(
        name="stk_auction_c", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=354",
        description="股票收盘集合竞价数据",
        params={"trade_date": "交易日", "ts_code": "TS代码"},
        returns={"close": "收盘价", "high": "最高价", "low": "最低价", "vol": "成交量", "amount": "成交额", "vwap": "成交均价"}
    ),
    "shhk_daily": EndpointMeta(
        name="shhk_daily", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=399",
        description="沪深港通指数日度指标",
        params={"trade_date": "交易日", "start_date": "开始日期", "end_date": "结束日期", "market": "市场"},
        returns={"north_money": "北向资金净流入", "south_money": "南向资金净流入", "prem_ratio": "AH溢价率", "ah_p": "AH比价"}
    ),
    "stk_nineturn": EndpointMeta(
        name="stk_nineturn", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=364",
        description="神奇九转指标",
        params={"ts_code": "TS代码", "freq": "频率(daily/60min)", "trade_date": "交易日", "start_date": "开始日期", "end_date": "结束日期", "fields": "字段列表"},
        returns={"up_count": "向上计数", "down_count": "向下计数", "nine_up_turn": "九转向上反转", "nine_down_turn": "九转向下反转"}
    ),
    "stk_ah_comparison": EndpointMeta(
        name="stk_ah_comparison", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=399",
        description="AH股比价",
        params={"trade_date": "交易日", "ts_code": "A股代码", "hk_code": "港股代码", "start_date": "开始日期", "end_date": "结束日期"},
        returns={"ah_comparison": "AH比价", "ah_premium": "AH溢价率", "hk_close": "港股收盘价", "close": "A股收盘价"}
    ),
    "stk_surv": EndpointMeta(
        name="stk_surv", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=275",
        description="机构调研数据",
        params={"ts_code": "TS代码", "trade_date": "调研日期", "start_date": "开始日期", "end_date": "结束日期", "fields": "字段列表"},
        returns={"surv_date": "调研日期", "fund_visitors": "调研人员", "rece_place": "接待地点", "rece_mode": "接待方式", "rece_org": "接待机构"}
    ),
    "stock_mx": EndpointMeta(
        name="stock_mx", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=300",
        description="动能因子数据",
        params={"ts_code": "股票代码", "trade_date": "交易日期", "start_date": "开始日期", "end_date": "结束日期"},
        returns={
            "mx_grade": "动能评级(1高/2中/3低/4弱)",
            "com_stock": "行业轮动指标",
            "evd_v": "速度指标，衡量股价变化速度",
            "zt_sum_z": "极值指标，短期均线离差值",
            "wma250_z": "偏离指标，中期均线偏离度"
        }
    ),
    "ths_index": EndpointMeta(
        name="ths_index", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=278",
        description="同花顺概念/行业指数列表",
        params={"exchange": "市场", "type": "类型", "ts_code": "代码"},
        returns={}
    ),
    "ths_member": EndpointMeta(
        name="ths_member", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=279",
        description="同花顺概念/行业成分明细",
        params={"ts_code": "概念/行业代码"},
        returns={}
    ),
    "hk_daily_adj": EndpointMeta(
        name="hk_daily_adj", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=339",
        description="港股复权行情（含市值/换手等）",
        params={"ts_code": "代码", "start_date": "开始", "end_date": "结束", "trade_date": "交易日"},
        returns={}
    ),
    "hk_mins": EndpointMeta(
        name="hk_mins", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=304",
        description="港股分钟行情",
        params={"ts_code": "代码", "freq": "频率", "start_date": "开始", "end_date": "结束"},
        returns={"trade_time": "时间", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "vol": "成交量", "amount": "成交额"}
    ),
    "margin": EndpointMeta(
        name="margin", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=58",
        description="融资融券汇总（市场级）",
        params={"trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"rzye": "融资余额", "rzmre": "融资买入额", "rqye": "融券余额", "rqmcl": "融券卖出量"}
    ),
    "margin_detail": EndpointMeta(
        name="margin_detail", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=59",
        description="融资融券明细（个股）",
        params={"ts_code": "TS代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"rzye": "融资余额", "rzmre": "融资买入额", "rzche": "融资偿还额", "rqye": "融券余额", "rqmcl": "融券卖出量", "rqchl": "融券偿还量"}
    ),
    "margin_secs": EndpointMeta(
        name="margin_secs", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=326",
        description="融资融券标的（盘前更新）",
        params={"trade_date": "交易日", "exchange": "交易所", "ts_code": "TS代码"},
        returns={"name": "证券名称", "exchange": "交易所"}
    ),
    "share_float": EndpointMeta(
        name="share_float", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=108",
        description="限售股解禁/流通股本变动",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={"float_date": "解禁日期", "float_share": "解禁股数", "reason": "原因"}
    ),
    "float_share": EndpointMeta(
        name="float_share", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2",
        description="流通股本变动（另一口径）",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "stk_premarket": EndpointMeta(
        name="stk_premarket", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=329",
        description="盘前股本情况",
        params={"trade_date": "交易日"},
        returns={"total_share": "总股本", "float_share": "流通股本", "pre_close": "前收盘", "up_limit": "涨停价", "down_limit": "跌停价"}
    ),
    "stk_restrict": EndpointMeta(
        name="stk_restrict", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2",
        description="限售股解禁计划",
        params={"ts_code": "TS代码", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "hs_const": EndpointMeta(
        name="hs_const", category=CATEGORY_STOCK, doc_url="https://tushare.pro/document/2?doc_id=104",
        description="沪深股通成份股",
        params={"hs_type": "SH/SZ", "is_new": "是否最新"},
        returns={"ts_code": "TS代码", "in_date": "纳入日期", "out_date": "剔除日期", "is_new": "是否最新"}
    ),

    # 指数专题
    "index_basic": EndpointMeta(
        name="index_basic", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2?doc_id=94",
        description="指数基础信息",
        params={"market": "市场", "publisher": "发布方", "category": "类别"},
        returns={"ts_code": "指数代码", "name": "指数名称", "market": "市场"}
    ),
    "index_daily": EndpointMeta(
        name="index_daily", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2?doc_id=95",
        description="指数日线",
        params={"ts_code": "指数代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"open": "开盘", "close": "收盘", "vol": "成交量", "amount": "成交额"}
    ),
    "index_dailybasic": EndpointMeta(
        name="index_dailybasic", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2?doc_id=96",
        description="指数每日指标",
        params={"ts_code": "指数代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"turnover_rate": "换手率", "pe": "市盈率", "pb": "市净率", "total_mv": "总市值"}
    ),
    "index_weight": EndpointMeta(
        name="index_weight", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2?doc_id=97",
        description="指数成分权重",
        params={"index_code": "指数代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"index_code": "指数代码", "con_code": "成分股代码", "trade_date": "交易日", "weight": "权重"}
    ),
    "index_classify": EndpointMeta(
        name="index_classify", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2",
        description="指数分类/列表",
        params={"src": "来源", "category": "类别", "market": "市场"},
        returns={}
    ),
    "index_member": EndpointMeta(
        name="index_member", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2",
        description="指数成分明细",
        params={"index_code": "指数代码", "trade_date": "交易日"},
        returns={"con_code": "成分股", "in_date": "纳入", "out_date": "剔除"}
    ),
    "index_weekly": EndpointMeta(
        name="index_weekly", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2",
        description="指数周线",
        params={"ts_code": "指数代码", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "index_monthly": EndpointMeta(
        name="index_monthly", category=CATEGORY_INDEX, doc_url="https://tushare.pro/document/2",
        description="指数月线",
        params={"ts_code": "指数代码", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),

    # ETF 专题（部分 ETF 接口与 fund_* 共用，按官方文档为准）
    "fund_basic": EndpointMeta(
        name="fund_basic", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2?doc_id=43",
        description="基金基础（筛选 ETF）",
        params={"market": "市场", "fund_type": "基金类型"},
        returns={"ts_code": "代码", "name": "名称", "fund_type": "类型", "market": "市场"}
    ),
    "fund_daily": EndpointMeta(
        name="fund_daily", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2?doc_id=185",
        description="基金/ETF 日线",
        params={"ts_code": "代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={"open": "开盘", "close": "收盘", "vol": "成交量", "amount": "成交额"}
    ),
    "fund_nav": EndpointMeta(
        name="fund_nav", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2?doc_id=44",
        description="基金净值（部分 ETF）",
        params={"ts_code": "代码", "nav_date": "净值日期", "start_date": "开始", "end_date": "结束"},
        returns={"nav": "单位净值", "accum_nav": "累计净值"}
    ),
    "fund_div": EndpointMeta(
        name="fund_div", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2",
        description="基金分红",
        params={"ts_code": "基金代码", "ann_date": "公告日", "record_date": "登记日", "ex_date": "除权日"},
        returns={}
    ),
    "fund_portfolio": EndpointMeta(
        name="fund_portfolio", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2?doc_id=47",
        description="基金/ETF 持仓（以 ETF 文档为准）",
        params={"ts_code": "代码", "period": "报告期"},
        returns={}
    ),
    "fund_adj": EndpointMeta(
        name="fund_adj", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2",
        description="基金/ETF 复权因子",
        params={"ts_code": "代码", "trade_date": "交易日", "start_date": "开始", "end_date": "结束"},
        returns={}
    ),
    "rt_etf_k": EndpointMeta(
        name="rt_etf_k", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2?doc_id=400",
        description="ETF 实时日线行情",
        params={"ts_code": "代码/通配", "topic": "主题"},
        returns={"name": "ETF 名称", "pre_close": "前收", "open": "开盘", "high": "最高", "low": "最低", "close": "最新价", "vol": "成交量", "amount": "成交额", "num": "成交笔数"}
    ),
    "fund_share": EndpointMeta(
        name="fund_share", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2",
        description="基金份额变动",
        params={"ts_code": "代码", "start_date": "开始", "end_date": "结束"},
        returns={"trade_date": "日期", "share": "份额", "change": "变动"}
    ),
    "fund_company": EndpointMeta(
        name="fund_company", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2",
        description="基金公司",
        params={"name": "公司名"},
        returns={}
    ),
    "fund_manager": EndpointMeta(
        name="fund_manager", category=CATEGORY_ETF, doc_url="https://tushare.pro/document/2",
        description="基金经理",
        params={"ts_code": "基金代码", "mger_name": "经理名"},
        returns={}
    ),

    # 大模型语料（占位，依照官方专题不断补充）
    # 由于专题较新，表名可能更新，建议使用 cli.call("<api_name>") 通用方式
    # 这里仅登记一个示意项：
    "llm_example": EndpointMeta(
        name="llm_example", category=CATEGORY_LLM, doc_url="https://tushare.pro/document/2",
        description="大模型语料专题示意接口（请以官网实际子表为准）",
        params={}, returns={}
    ),
}


def get_endpoint_meta(name: str) -> Optional[EndpointMeta]:
    """获取接口元信息（用于查看参数和返回字段说明）"""
    return ENDPOINTS.get(name)


def export_endpoints_markdown() -> str:
    """将当前 ENDPOINTS 导出为 Markdown 清单文本（按分类分组）。
    可用于在 README 中粘贴“接口总览”。
    """
    groups: Dict[str, List[EndpointMeta]] = {}
    for ep in ENDPOINTS.values():
        groups.setdefault(ep.category, []).append(ep)
    # 固定分类顺序
    order = [CATEGORY_STOCK, CATEGORY_INDEX, CATEGORY_ETF, CATEGORY_LLM]
    lines: List[str] = ["## 接口总览（自动导出）\n"]
    for cat in order:
        items = groups.get(cat, [])
        if not items:
            continue
        lines.append(f"- **{cat}**")
        # 名称按字母序
        for ep in sorted(items, key=lambda x: x.name.lower()):
            link = f" ({ep.doc_url})" if ep.doc_url else ""
            lines.append(f"  - {ep.name}{link}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _endpoint_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for meta in ENDPOINTS.values():
        counts[meta.category] = counts.get(meta.category, 0) + 1
    return counts


def main(argv: Optional[List[str]] = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Tushare Atomic API 辅助脚本")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="输出 README 所需的接口总览 Markdown",
    )
    parser.add_argument(
        "--counts",
        action="store_true",
        help="仅打印当前分类统计（默认自动启用）",
    )
    args = parser.parse_args(argv)

    print("[INFO] Tushare Atomic CLI 启动")
    try:
        counts = _endpoint_counts()
        print("[INFO] 当前接口数量：")
        for category in [CATEGORY_STOCK, CATEGORY_INDEX, CATEGORY_ETF, CATEGORY_LLM]:
            if category in counts:
                print(f"  - {category}: {counts[category]}")
        if args.markdown:
            print("[INFO] 导出 Markdown 索引...")
            print(export_endpoints_markdown())
        elif args.counts:
            print("[INFO] 已按要求输出分类统计")
        print("[INFO] 任务完成")
    except Exception as exc:
        print(f"[ERROR] 执行失败: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = [
    "TushareAtomicClient",
    "EndpointMeta",
    "get_endpoint_meta",
    "export_endpoints_markdown",
    "main",
    "ENDPOINTS",
    "CATEGORY_STOCK", "CATEGORY_INDEX", "CATEGORY_ETF", "CATEGORY_LLM",
]
