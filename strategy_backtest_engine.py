"""
策略回测引擎模块
负责策略的历史数据回测、信号生成、交易模拟和指标计算
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import json
import sys
import os

# 导入项目现有模块（只读访问）
from unified_data_access import UnifiedDataAccess
from strategy_indicators import calculate_all_indicators
from strategy_db import BacktestDB, StrategyDB, init_database, get_db


class RuleEngine:
    """条件评估引擎 - 解析和评估JSON格式的策略规则"""
    
    OPERATORS = {
        '>': lambda a, b: a > b,
        '<': lambda a, b: a < b,
        '>=': lambda a, b: a >= b,
        '<=': lambda a, b: a <= b,
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
        'cross_above': lambda curr_a, curr_b, prev_a, prev_b: (prev_a <= prev_b and curr_a > curr_b),
        'cross_below': lambda curr_a, curr_b, prev_a, prev_b: (prev_a >= prev_b and curr_a < curr_b),
    }
    
    @staticmethod
    def evaluate_condition(condition: Dict, indicators: Dict, prev_indicators: Optional[Dict] = None) -> bool:
        """
        评估单个条件
        
        Args:
            condition: 条件配置 {'left': 'close', 'operator': '>', 'right': 'ma20'}
            indicators: 当前指标值字典
            prev_indicators: 前一期指标值字典（用于跨越运算符）
            
        Returns:
            bool: 条件是否满足
        """
        try:
            operator = condition.get('operator')
            if operator not in RuleEngine.OPERATORS:
                return False
            
            # 获取左值
            left_value = RuleEngine._get_value(condition['left'], indicators)
            if left_value is None or pd.isna(left_value):
                return False
            
            # 获取右值
            right_value = RuleEngine._get_value(condition['right'], indicators)
            if right_value is None or pd.isna(right_value):
                return False
            
            # 跨越运算符需要前一期数据
            if operator in ['cross_above', 'cross_below']:
                if prev_indicators is None:
                    return False
                prev_left = RuleEngine._get_value(condition['left'], prev_indicators)
                prev_right = RuleEngine._get_value(condition['right'], prev_indicators)
                if prev_left is None or prev_right is None:
                    return False
                return RuleEngine.OPERATORS[operator](left_value, right_value, prev_left, prev_right)
            else:
                return RuleEngine.OPERATORS[operator](left_value, right_value)
                
        except Exception as e:
            print(f"❌ 条件评估错误: {e}")
            return False
    
    @staticmethod
    def _get_value(key: Any, indicators: Dict) -> Optional[float]:
        """
        获取指标值或数值
        
        Args:
            key: 键名（字符串）或数值
            indicators: 指标字典
            
        Returns:
            float: 数值，None表示未找到
        """
        # 如果是数值，直接返回
        if isinstance(key, (int, float)):
            return float(key)
        
        # 如果是字符串，尝试转换为数值
        if isinstance(key, str):
            # 尝试解析为数字
            try:
                return float(key)
            except ValueError:
                pass
            
            # 从指标字典中获取
            key_lower = key.lower()
            if key_lower in indicators:
                return float(indicators[key_lower])
        
        return None
    
    @staticmethod
    def evaluate_rules(rules: Dict, indicators: Dict, prev_indicators: Optional[Dict] = None) -> Tuple[bool, List[Dict]]:
        """
        评估复合规则（支持AND/OR逻辑）
        
        Args:
            rules: 规则配置 {'operator': 'AND/OR', 'conditions': [...]}
            indicators: 当前指标值字典
            prev_indicators: 前一期指标值字典
            
        Returns:
            (bool, list): (是否满足, 匹配的条件列表)
        """
        if not rules or 'conditions' not in rules:
            return False, []
        
        logic_operator = rules.get('operator', 'AND').upper()
        conditions = rules['conditions']
        matched_conditions = []
        
        for condition in conditions:
            # 递归评估嵌套规则
            if 'operator' in condition and condition['operator'] in ['AND', 'OR']:
                result, sub_matched = RuleEngine.evaluate_rules(condition, indicators, prev_indicators)
                if result:
                    matched_conditions.extend(sub_matched)
            else:
                # 评估单个条件
                if RuleEngine.evaluate_condition(condition, indicators, prev_indicators):
                    matched_conditions.append(condition)
        
        # 根据逻辑运算符判断
        if logic_operator == 'AND':
            all_matched = len(matched_conditions) == len(conditions)
            return all_matched, matched_conditions if all_matched else []
        else:  # OR
            any_matched = len(matched_conditions) > 0
            return any_matched, matched_conditions


class BacktestEngine:
    """回测引擎 - 策略回测主流程"""
    
    def __init__(self):
        """初始化回测引擎"""
        self.data_access = UnifiedDataAccess()
        self.rule_engine = RuleEngine()
        
        # 确保数据库已初始化
        try:
            get_db()
        except:
            init_database()
    
    def run_backtest(self, strategy_id: int, stock_code: str, start_date: str, 
                     end_date: str, initial_capital: float = 100000) -> Dict:
        """
        执行回测
        
        Args:
            strategy_id: 策略ID
            stock_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            initial_capital: 初始资金
            
        Returns:
            dict: 回测结果
        """
        try:
            print(f"\n🚀 开始回测 - 策略ID: {strategy_id}, 股票: {stock_code}")
            
            # 1. 获取策略配置
            strategy_result = StrategyDB.get_strategy(strategy_id)
            if not strategy_result['success']:
                return {'success': False, 'error': '策略不存在'}
            
            strategy = strategy_result['strategy']
            print(f"📋 策略名称: {strategy['name']}")
            
            # 2. 获取历史数据
            print(f"📊 获取历史数据: {start_date} - {end_date}")
            df = self.data_access.get_daily_backtest_data(
                symbol=stock_code,
                start_date=start_date,
                end_date=end_date,
                adjust='qfq'  # 前复权
            )
            
            if df is None or len(df) == 0:
                return {'success': False, 'error': '无法获取历史数据'}
            
            print(f"✅ 获取到 {len(df)} 条数据")
            
            # 3. 计算技术指标
            print("📈 计算技术指标...")
            df = calculate_all_indicators(df)
            
            # 4. 执行回测模拟
            print("🔄 执行交易模拟...")
            backtest_result = self._simulate_trading(
                df=df,
                strategy=strategy,
                stock_code=stock_code,
                initial_capital=initial_capital
            )
            
            if not backtest_result['success']:
                return backtest_result
            
            # 5. 保存回测结果到数据库
            print("💾 保存回测结果...")
            save_result = BacktestDB.save_backtest_result({
                'strategy_id': strategy_id,
                'stock_code': stock_code,
                'stock_name': backtest_result.get('stock_name', stock_code),
                'start_date': start_date,
                'end_date': end_date,
                'initial_capital': initial_capital,
                'final_capital': backtest_result['final_capital'],
                'total_return': backtest_result['total_return'],
                'annual_return': backtest_result['annual_return'],
                'max_drawdown': backtest_result['max_drawdown'],
                'sharpe_ratio': backtest_result['sharpe_ratio'],
                'total_trades': backtest_result['total_trades'],
                'win_trades': backtest_result['win_trades'],
                'lose_trades': backtest_result['lose_trades'],
                'win_rate': backtest_result['win_rate'],
                'profit_loss_ratio': backtest_result['profit_loss_ratio'],
                'avg_holding_days': backtest_result['avg_holding_days'],
                'period_returns': json.dumps(backtest_result['period_returns']),
                'trade_details': json.dumps(backtest_result['trade_details'], ensure_ascii=False)
            })
            
            if save_result['success']:
                backtest_result['backtest_id'] = save_result['backtest_id']
                print(f"✅ 回测完成! ID: {save_result['backtest_id']}")
            
            return backtest_result
            
        except Exception as e:
            print(f"❌ 回测执行错误: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def _simulate_trading(self, df: pd.DataFrame, strategy: Dict, 
                         stock_code: str, initial_capital: float) -> Dict:
        """
        模拟交易执行
        
        Args:
            df: 带指标的历史数据
            strategy: 策略配置
            stock_code: 股票代码
            initial_capital: 初始资金
            
        Returns:
            dict: 交易模拟结果
        """
        try:
            # 解析策略条件
            entry_conditions = json.loads(strategy['entry_conditions'])
            exit_conditions = json.loads(strategy.get('exit_conditions', '{}'))
            
            # 交易账户
            cash = initial_capital
            position = 0  # 持仓数量
            position_cost = 0  # 持仓成本
            
            # 交易记录
            trades = []
            equity_curve = []  # 权益曲线
            
            # 交易成本参数
            commission_rate = 0.0003  # 佣金费率 0.03%
            min_commission = 5  # 最低佣金 5元
            stamp_tax_rate = 0.001  # 印花税 0.1% (仅卖出)
            
            # 遍历历史数据
            for i in range(1, len(df)):
                current_row = df.iloc[i]
                prev_row = df.iloc[i-1]
                
                # 构建指标字典
                current_indicators = current_row.to_dict()
                prev_indicators = prev_row.to_dict()
                
                date = current_indicators['date']
                close_price = current_indicators['close']
                
                # 检查入场信号
                if position == 0:  # 空仓状态
                    entry_matched, entry_rules = self.rule_engine.evaluate_rules(
                        entry_conditions, current_indicators, prev_indicators
                    )
                    
                    if entry_matched:
                        # 全仓买入
                        buy_amount = cash * 0.99  # 预留1%防止不足
                        shares = int(buy_amount / close_price / 100) * 100  # 买入100股整数倍
                        
                        if shares >= 100:
                            cost = shares * close_price
                            commission = max(cost * commission_rate, min_commission)
                            total_cost = cost + commission
                            
                            if total_cost <= cash:
                                position = shares
                                position_cost = close_price
                                cash -= total_cost
                                
                                trades.append({
                                    'date': date,
                                    'type': 'BUY',
                                    'price': close_price,
                                    'shares': shares,
                                    'amount': cost,
                                    'commission': commission,
                                    'matched_rules': entry_rules
                                })
                                print(f"  📈 {date} 买入: {shares}股 @ {close_price:.2f}元")
                
                # 检查退出信号
                elif position > 0:  # 持仓状态
                    exit_matched = False
                    exit_rules = []
                    
                    # 评估退出条件
                    if exit_conditions and 'conditions' in exit_conditions:
                        exit_matched, exit_rules = self.rule_engine.evaluate_rules(
                            exit_conditions, current_indicators, prev_indicators
                        )
                    
                    # 简单止盈止损（如果没有退出条件）
                    if not exit_matched and not exit_conditions.get('conditions'):
                        profit_pct = (close_price - position_cost) / position_cost
                        if profit_pct >= 0.10:  # 止盈10%
                            exit_matched = True
                            exit_rules = [{'reason': '止盈10%'}]
                        elif profit_pct <= -0.05:  # 止损5%
                            exit_matched = True
                            exit_rules = [{'reason': '止损5%'}]
                    
                    if exit_matched:
                        # 卖出
                        sell_amount = position * close_price
                        commission = max(sell_amount * commission_rate, min_commission)
                        stamp_tax = sell_amount * stamp_tax_rate
                        total_fee = commission + stamp_tax
                        cash += sell_amount - total_fee
                        
                        profit = (close_price - position_cost) * position
                        profit_pct = (close_price - position_cost) / position_cost
                        
                        trades.append({
                            'date': date,
                            'type': 'SELL',
                            'price': close_price,
                            'shares': position,
                            'amount': sell_amount,
                            'commission': commission,
                            'stamp_tax': stamp_tax,
                            'profit': profit,
                            'profit_pct': profit_pct,
                            'matched_rules': exit_rules
                        })
                        print(f"  📉 {date} 卖出: {position}股 @ {close_price:.2f}元, 盈亏: {profit:.2f}元 ({profit_pct*100:.2f}%)")
                        
                        position = 0
                        position_cost = 0
                
                # 计算当前总权益
                current_equity = cash + (position * close_price if position > 0 else 0)
                equity_curve.append({
                    'date': date,
                    'equity': current_equity,
                    'cash': cash,
                    'position_value': position * close_price if position > 0 else 0
                })
            
            # 如果最后仍有持仓，按最后价格卖出
            if position > 0:
                last_row = df.iloc[-1]
                last_price = last_row['close']
                last_date = last_row['date']
                
                sell_amount = position * last_price
                commission = max(sell_amount * commission_rate, min_commission)
                stamp_tax = sell_amount * stamp_tax_rate
                cash += sell_amount - commission - stamp_tax
                
                profit = (last_price - position_cost) * position
                profit_pct = (last_price - position_cost) / position_cost
                
                trades.append({
                    'date': last_date,
                    'type': 'SELL',
                    'price': last_price,
                    'shares': position,
                    'amount': sell_amount,
                    'commission': commission,
                    'stamp_tax': stamp_tax,
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'matched_rules': [{'reason': '回测结束强制平仓'}]
                })
                print(f"  📉 {last_date} 强制平仓: {position}股 @ {last_price:.2f}元")
                
                position = 0
            
            # 计算回测指标
            final_capital = cash
            total_return = (final_capital - initial_capital) / initial_capital
            
            # 计算年化收益率
            days = len(df)
            annual_return = ((1 + total_return) ** (365 / days) - 1) if days > 0 else 0
            
            # 计算最大回撤
            max_drawdown = self._calculate_max_drawdown(equity_curve)
            
            # 计算夏普比率
            sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
            
            # 交易统计
            total_trades = len([t for t in trades if t['type'] == 'BUY'])
            win_trades = len([t for t in trades if t['type'] == 'SELL' and t.get('profit', 0) > 0])
            lose_trades = len([t for t in trades if t['type'] == 'SELL' and t.get('profit', 0) <= 0])
            win_rate = win_trades / total_trades if total_trades > 0 else 0
            
            # 盈亏比
            avg_profit = np.mean([t.get('profit', 0) for t in trades if t['type'] == 'SELL' and t.get('profit', 0) > 0]) if win_trades > 0 else 0
            avg_loss = abs(np.mean([t.get('profit', 0) for t in trades if t['type'] == 'SELL' and t.get('profit', 0) < 0])) if lose_trades > 0 else 0
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
            
            # 平均持仓天数
            holding_periods = []
            for i in range(0, len(trades), 2):
                if i + 1 < len(trades):
                    buy_date = pd.to_datetime(trades[i]['date'])
                    sell_date = pd.to_datetime(trades[i+1]['date'])
                    holding_periods.append((sell_date - buy_date).days)
            avg_holding_days = np.mean(holding_periods) if holding_periods else 0
            
            return {
                'success': True,
                'stock_name': stock_code,
                'final_capital': final_capital,
                'total_return': total_return,
                'annual_return': annual_return,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'total_trades': total_trades,
                'win_trades': win_trades,
                'lose_trades': lose_trades,
                'win_rate': win_rate,
                'profit_loss_ratio': profit_loss_ratio,
                'avg_holding_days': avg_holding_days,
                'period_returns': equity_curve,
                'trade_details': trades
            }
            
        except Exception as e:
            print(f"❌ 交易模拟错误: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def _calculate_max_drawdown(self, equity_curve: List[Dict]) -> float:
        """计算最大回撤"""
        if not equity_curve:
            return 0.0
        
        equities = [e['equity'] for e in equity_curve]
        peak = equities[0]
        max_dd = 0
        
        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, equity_curve: List[Dict], risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        if len(equity_curve) < 2:
            return 0.0
        
        # 计算日收益率
        equities = [e['equity'] for e in equity_curve]
        returns = [(equities[i] - equities[i-1]) / equities[i-1] for i in range(1, len(equities))]
        
        if not returns:
            return 0.0
        
        # 年化收益率和波动率
        mean_return = np.mean(returns) * 252  # 年化
        std_return = np.std(returns) * np.sqrt(252)  # 年化波动率
        
        if std_return == 0:
            return 0.0
        
        sharpe = (mean_return - risk_free_rate) / std_return
        return sharpe


# 测试代码
if __name__ == '__main__':
    print("=== 策略回测引擎测试 ===\n")
    
    # 初始化数据库
    init_database()
    
    # 创建测试策略
    test_strategy = {
        'uuid': 'test_ma_cross_001',
        'name': '均线金叉策略',
        'type': 'trading',
        'description': '5日均线上穿20日均线买入，下穿卖出',
        'logic_description': '当短期均线上穿长期均线时买入，下穿时卖出',
        'entry_conditions': {
            'operator': 'AND',
            'conditions': [
                {'left': 'ma5', 'operator': 'cross_above', 'right': 'ma20'}
            ]
        },
        'exit_conditions': {
            'operator': 'AND',
            'conditions': [
                {'left': 'ma5', 'operator': 'cross_below', 'right': 'ma20'}
            ]
        },
        'required_indicators': ['ma5', 'ma20'],
        'parameters': {}
    }
    
    # 保存策略
    result = StrategyDB.create_strategy(test_strategy)
    if result['success']:
        strategy_id = result['strategy_id']
        print(f"✅ 测试策略已创建, ID: {strategy_id}\n")
        
        # 执行回测
        engine = BacktestEngine()
        backtest_result = engine.run_backtest(
            strategy_id=strategy_id,
            stock_code='600519',  # 贵州茅台
            start_date='20230101',
            end_date='20231231',
            initial_capital=100000
        )
        
        if backtest_result['success']:
            print(f"\n📊 回测结果汇总:")
            print(f"   总收益率: {backtest_result['total_return']*100:.2f}%")
            print(f"   年化收益: {backtest_result['annual_return']*100:.2f}%")
            print(f"   最大回撤: {backtest_result['max_drawdown']*100:.2f}%")
            print(f"   夏普比率: {backtest_result['sharpe_ratio']:.2f}")
            print(f"   交易次数: {backtest_result['total_trades']}")
            print(f"   胜率: {backtest_result['win_rate']*100:.2f}%")
            print(f"   盈亏比: {backtest_result['profit_loss_ratio']:.2f}")
            print(f"   平均持仓: {backtest_result['avg_holding_days']:.1f}天")
        else:
            print(f"❌ 回测失败: {backtest_result.get('error')}")
    else:
        print(f"❌ 策略创建失败: {result.get('error')}")
