"""
策略管理数据库模块
负责策略、回测结果、信号记录的数据持久化
"""

from peewee import *
import os
from datetime import datetime
import json

# 数据库文件路径（独立数据库，符合模块隔离原则）
DB_PATH = 'strategy_management.db'

# 创建数据库连接
db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    """基础模型类"""
    class Meta:
        database = db


class Strategy(BaseModel):
    """策略表 - 存储策略定义和配置"""
    uuid = CharField(unique=True, index=True)
    name = CharField()
    type = CharField()  # selection/trading
    category = CharField(null=True)
    description = TextField()
    logic_description = TextField()  # AI生成的浅显描述
    author = CharField(default='user')
    status = CharField(default='active')  # active/inactive/testing
    entry_conditions = TextField()  # JSON格式
    exit_conditions = TextField(null=True)  # JSON格式
    required_indicators = TextField()  # JSON数组
    parameters = TextField()  # JSON格式
    risk_warning = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    total_backtests = IntegerField(default=0)
    avg_return = FloatField(null=True)
    avg_win_rate = FloatField(null=True)
    avg_max_drawdown = FloatField(null=True)
    
    class Meta:
        table_name = 'strategies'


class BacktestResult(BaseModel):
    """回测结果表 - 存储回测详细结果"""
    strategy = ForeignKeyField(Strategy, backref='backtests')
    stock_code = CharField(index=True)
    stock_name = CharField()
    backtest_date = DateTimeField(default=datetime.now)
    start_date = CharField()
    end_date = CharField()
    initial_capital = FloatField(default=100000)
    final_capital = FloatField(null=True)
    total_return = FloatField(null=True)
    annual_return = FloatField(null=True)
    max_drawdown = FloatField(null=True)
    sharpe_ratio = FloatField(null=True)
    total_trades = IntegerField(default=0)
    win_trades = IntegerField(default=0)
    lose_trades = IntegerField(default=0)
    win_rate = FloatField(null=True)
    profit_loss_ratio = FloatField(null=True)
    avg_holding_days = FloatField(null=True)
    period_returns = TextField()  # JSON格式存储各周期收益
    trade_details = TextField()  # JSON格式存储交易明细
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'backtest_results'
        indexes = (
            (('strategy', 'stock_code'), False),
        )


class StrategySignal(BaseModel):
    """策略信号表 - 记录每个交易信号"""
    backtest = ForeignKeyField(BacktestResult, backref='signals')
    strategy = ForeignKeyField(Strategy)
    stock_code = CharField()
    signal_date = CharField()
    signal_type = CharField()  # entry/exit
    signal_price = FloatField()
    indicators = TextField()  # JSON格式存储当时指标值
    matched_rules = TextField()  # JSON格式存储匹配的规则
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'strategy_signals'


def init_database():
    """初始化数据库，创建表结构"""
    db.connect()
    db.create_tables([Strategy, BacktestResult, StrategySignal])
    print(f"✅ 策略数据库初始化完成: {DB_PATH}")
    return True


def get_db():
    """获取数据库连接"""
    if db.is_closed():
        db.connect()
    return db


class StrategyDB:
    """策略数据库操作类"""
    
    @staticmethod
    def create_strategy(strategy_data):
        """
        创建新策略
        
        Args:
            strategy_data: 策略数据字典
            
        Returns:
            dict: {success: bool, strategy_id: int, error: str}
        """
        try:
            strategy = Strategy.create(
                uuid=strategy_data['uuid'],
                name=strategy_data['name'],
                type=strategy_data.get('type', 'trading'),
                category=strategy_data.get('category'),
                description=strategy_data['description'],
                logic_description=strategy_data.get('logic_description', ''),
                author=strategy_data.get('author', 'user'),
                status=strategy_data.get('status', 'active'),
                entry_conditions=json.dumps(strategy_data['entry_conditions'], ensure_ascii=False),
                exit_conditions=json.dumps(strategy_data.get('exit_conditions', {}), ensure_ascii=False),
                required_indicators=json.dumps(strategy_data['required_indicators'], ensure_ascii=False),
                parameters=json.dumps(strategy_data.get('parameters', {}), ensure_ascii=False),
                risk_warning=strategy_data.get('risk_warning')
            )
            return {'success': True, 'strategy_id': strategy.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_strategy(strategy_id):
        """
        获取策略详情
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            dict: {success: bool, strategy: dict, error: str}
        """
        try:
            strategy = Strategy.get_by_id(strategy_id)
            return {
                'success': True,
                'strategy': StrategyDB._strategy_to_dict(strategy)
            }
        except Strategy.DoesNotExist:
            return {'success': False, 'error': '策略不存在'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def list_strategies(filters=None):
        """
        列出所有策略
        
        Args:
            filters: 筛选条件字典 {type, status, category}
            
        Returns:
            dict: {success: bool, strategies: list}
        """
        try:
            query = Strategy.select()
            
            if filters:
                if 'type' in filters and filters['type']:
                    query = query.where(Strategy.type == filters['type'])
                if 'status' in filters and filters['status']:
                    query = query.where(Strategy.status == filters['status'])
                if 'category' in filters and filters['category']:
                    query = query.where(Strategy.category == filters['category'])
            
            strategies = [StrategyDB._strategy_to_dict(s) for s in query]
            return {'success': True, 'strategies': strategies}
        except Exception as e:
            return {'success': False, 'error': str(e), 'strategies': []}
    
    @staticmethod
    def update_strategy(strategy_id, updates):
        """
        更新策略
        
        Args:
            strategy_id: 策略ID
            updates: 更新数据字典
            
        Returns:
            dict: {success: bool, error: str}
        """
        try:
            strategy = Strategy.get_by_id(strategy_id)
            for key, value in updates.items():
                if hasattr(strategy, key):
                    # JSON字段需要序列化
                    if key in ['entry_conditions', 'exit_conditions', 'required_indicators', 'parameters']:
                        setattr(strategy, key, json.dumps(value, ensure_ascii=False))
                    else:
                        setattr(strategy, key, value)
            strategy.updated_at = datetime.now()
            strategy.save()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_strategy(strategy_id):
        """
        删除策略及其相关数据
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            dict: {success: bool, error: str}
        """
        try:
            strategy = Strategy.get_by_id(strategy_id)
            # 删除相关的回测结果和信号
            BacktestResult.delete().where(BacktestResult.strategy == strategy).execute()
            StrategySignal.delete().where(StrategySignal.strategy == strategy).execute()
            strategy.delete_instance()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _strategy_to_dict(strategy):
        """将策略对象转换为字典"""
        return {
            'id': strategy.id,
            'uuid': strategy.uuid,
            'name': strategy.name,
            'type': strategy.type,
            'category': strategy.category,
            'description': strategy.description,
            'logic_description': strategy.logic_description,
            'author': strategy.author,
            'status': strategy.status,
            'entry_conditions': json.loads(strategy.entry_conditions),
            'exit_conditions': json.loads(strategy.exit_conditions) if strategy.exit_conditions else {},
            'required_indicators': json.loads(strategy.required_indicators),
            'parameters': json.loads(strategy.parameters),
            'risk_warning': strategy.risk_warning,
            'created_at': strategy.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': strategy.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'total_backtests': strategy.total_backtests,
            'avg_return': strategy.avg_return,
            'avg_win_rate': strategy.avg_win_rate,
            'avg_max_drawdown': strategy.avg_max_drawdown
        }


class BacktestDB:
    """回测结果数据库操作类"""
    
    @staticmethod
    def save_backtest_result(result_data):
        """
        保存回测结果
        
        Args:
            result_data: 回测结果数据字典
            
        Returns:
            dict: {success: bool, backtest_id: int, error: str}
        """
        try:
            result = BacktestResult.create(
                strategy=result_data['strategy_id'],
                stock_code=result_data['stock_code'],
                stock_name=result_data['stock_name'],
                start_date=result_data['start_date'],
                end_date=result_data['end_date'],
                initial_capital=result_data.get('initial_capital', 100000),
                final_capital=result_data.get('final_capital'),
                total_return=result_data.get('total_return'),
                annual_return=result_data.get('annual_return'),
                max_drawdown=result_data.get('max_drawdown'),
                sharpe_ratio=result_data.get('sharpe_ratio'),
                total_trades=result_data.get('total_trades', 0),
                win_trades=result_data.get('win_trades', 0),
                lose_trades=result_data.get('lose_trades', 0),
                win_rate=result_data.get('win_rate'),
                profit_loss_ratio=result_data.get('profit_loss_ratio'),
                avg_holding_days=result_data.get('avg_holding_days'),
                period_returns=json.dumps(result_data.get('period_returns', {}), ensure_ascii=False),
                trade_details=json.dumps(result_data.get('trade_details', []), ensure_ascii=False)
            )
            
            # 更新策略统计信息
            BacktestDB._update_strategy_stats(result_data['strategy_id'])
            
            return {'success': True, 'backtest_id': result.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _update_strategy_stats(strategy_id):
        """更新策略的统计信息"""
        try:
            strategy = Strategy.get_by_id(strategy_id)
            backtests = BacktestResult.select().where(BacktestResult.strategy == strategy)
            
            if backtests.count() > 0:
                total_backtests = backtests.count()
                
                # 计算平均值(过滤None值)
                returns = [b.total_return for b in backtests if b.total_return is not None]
                win_rates = [b.win_rate for b in backtests if b.win_rate is not None]
                drawdowns = [b.max_drawdown for b in backtests if b.max_drawdown is not None]
                
                strategy.total_backtests = total_backtests
                strategy.avg_return = sum(returns) / len(returns) if returns else None
                strategy.avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else None
                strategy.avg_max_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
                strategy.save()
        except Exception as e:
            print(f"⚠️ 更新策略统计信息失败: {e}")


# 主程序入口
if __name__ == '__main__':
    # 初始化数据库
    init_database()
    
    # 测试创建策略
    import uuid
    test_strategy = {
        'uuid': str(uuid.uuid4()),
        'name': '测试均线突破策略',
        'type': 'trading',
        'description': '股价突破20日均线买入',
        'logic_description': '当股价向上突破20天平均价格时买入',
        'entry_conditions': {
            'logic': 'AND',
            'rules': [{'indicator': 'CLOSE', 'operator': '>', 'value': 'MA20'}]
        },
        'required_indicators': ['MA20']
    }
    
    result = StrategyDB.create_strategy(test_strategy)
    if result['success']:
        print(f"✅ 测试策略创建成功，ID: {result['strategy_id']}")
        
        # 测试查询
        query_result = StrategyDB.list_strategies()
        print(f"✅ 查询到 {len(query_result['strategies'])} 个策略")
    else:
        print(f"❌ 策略创建失败: {result['error']}")
"""
策略管理数据库模块
负责策略、回测结果、信号记录的数据持久化
"""

from peewee import *
import os
from datetime import datetime
import json

# 数据库文件路径
DB_PATH = 'strategy.db'

# 创建数据库连接
db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    """基础模型类"""
    class Meta:
        database = db


class Strategy(BaseModel):
    """策略表 - 存储策略定义和配置"""
    uuid = CharField(unique=True, index=True)
    name = CharField()
    type = CharField()  # selection/trading
    category = CharField(null=True)
    description = TextField()
    logic_description = TextField()  # AI生成的浅显描述
    author = CharField(default='user')
    status = CharField(default='active')  # active/inactive/testing
    entry_conditions = TextField()  # JSON格式
    exit_conditions = TextField(null=True)  # JSON格式
    required_indicators = TextField()  # JSON数组
    parameters = TextField()  # JSON格式
    risk_warning = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    total_backtests = IntegerField(default=0)
    avg_return = FloatField(null=True)
    avg_win_rate = FloatField(null=True)
    avg_max_drawdown = FloatField(null=True)
    
    class Meta:
        table_name = 'strategies'


class BacktestResult(BaseModel):
    """回测结果表 - 存储回测详细结果"""
    strategy = ForeignKeyField(Strategy, backref='backtests')
    stock_code = CharField(index=True)
    stock_name = CharField()
    backtest_date = DateTimeField(default=datetime.now)
    start_date = CharField()
    end_date = CharField()
    initial_capital = FloatField(default=100000)
    final_capital = FloatField(null=True)
    total_return = FloatField(null=True)
    annual_return = FloatField(null=True)
    max_drawdown = FloatField(null=True)
    sharpe_ratio = FloatField(null=True)
    total_trades = IntegerField(default=0)
    win_trades = IntegerField(default=0)
    lose_trades = IntegerField(default=0)
    win_rate = FloatField(null=True)
    profit_loss_ratio = FloatField(null=True)
    avg_holding_days = FloatField(null=True)
    period_returns = TextField()  # JSON格式存储各周期收益
    trade_details = TextField()  # JSON格式存储交易明细
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'backtest_results'
        indexes = (
            (('strategy', 'stock_code'), False),
        )


class StrategySignal(BaseModel):
    """策略信号表 - 记录每个交易信号"""
    backtest = ForeignKeyField(BacktestResult, backref='signals')
    strategy = ForeignKeyField(Strategy)
    stock_code = CharField()
    signal_date = CharField()
    signal_type = CharField()  # entry/exit
    signal_price = FloatField()
    indicators = TextField()  # JSON格式存储当时指标值
    matched_rules = TextField()  # JSON格式存储匹配的规则
    created_at = DateTimeField(default=datetime.now)
    
    class Meta:
        table_name = 'strategy_signals'


def init_database():
    """初始化数据库，创建表结构"""
    db.connect()
    db.create_tables([Strategy, BacktestResult, StrategySignal])
    print(f"✅ 策略数据库初始化完成: {DB_PATH}")
    return True


def get_db():
    """获取数据库连接"""
    if db.is_closed():
        db.connect()
    return db


class StrategyDB:
    """策略数据库操作类"""
    
    @staticmethod
    def create_strategy(strategy_data):
        """
        创建新策略
        
        Args:
            strategy_data: 策略数据字典
            
        Returns:
            dict: {success: bool, strategy_id: int, error: str}
        """
        try:
            strategy = Strategy.create(
                uuid=strategy_data['uuid'],
                name=strategy_data['name'],
                type=strategy_data.get('type', 'trading'),
                category=strategy_data.get('category'),
                description=strategy_data['description'],
                logic_description=strategy_data.get('logic_description', ''),
                author=strategy_data.get('author', 'user'),
                status=strategy_data.get('status', 'active'),
                entry_conditions=json.dumps(strategy_data['entry_conditions'], ensure_ascii=False),
                exit_conditions=json.dumps(strategy_data.get('exit_conditions', {}), ensure_ascii=False),
                required_indicators=json.dumps(strategy_data['required_indicators'], ensure_ascii=False),
                parameters=json.dumps(strategy_data.get('parameters', {}), ensure_ascii=False),
                risk_warning=strategy_data.get('risk_warning')
            )
            return {'success': True, 'strategy_id': strategy.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_strategy(strategy_id):
        """
        获取策略详情
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            dict: {success: bool, strategy: dict, error: str}
        """
        try:
            strategy = Strategy.get_by_id(strategy_id)
            return {
                'success': True,
                'strategy': StrategyDB._strategy_to_dict(strategy)
            }
        except Strategy.DoesNotExist:
            return {'success': False, 'error': '策略不存在'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def list_strategies(filters=None):
        """
        列出所有策略
        
        Args:
            filters: 筛选条件字典 {type, status, category}
            
        Returns:
            dict: {success: bool, strategies: list}
        """
        try:
            query = Strategy.select()
            
            if filters:
                if 'type' in filters and filters['type']:
                    query = query.where(Strategy.type == filters['type'])
                if 'status' in filters and filters['status']:
                    query = query.where(Strategy.status == filters['status'])
                if 'category' in filters and filters['category']:
                    query = query.where(Strategy.category == filters['category'])
            
            strategies = [StrategyDB._strategy_to_dict(s) for s in query]
            return {'success': True, 'strategies': strategies}
        except Exception as e:
            return {'success': False, 'error': str(e), 'strategies': []}
    
    @staticmethod
    def update_strategy(strategy_id, updates):
        """
        更新策略
        
        Args:
            strategy_id: 策略ID
            updates: 更新数据字典
            
        Returns:
            dict: {success: bool, error: str}
        """
        try:
            strategy = Strategy.get_by_id(strategy_id)
            for key, value in updates.items():
                if hasattr(strategy, key):
                    # JSON字段需要序列化
                    if key in ['entry_conditions', 'exit_conditions', 'required_indicators', 'parameters']:
                        setattr(strategy, key, json.dumps(value, ensure_ascii=False))
                    else:
                        setattr(strategy, key, value)
            strategy.updated_at = datetime.now()
            strategy.save()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_strategy(strategy_id):
        """
        删除策略及其相关数据
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            dict: {success: bool, error: str}
        """
        try:
            strategy = Strategy.get_by_id(strategy_id)
            # 删除相关的回测结果和信号
            BacktestResult.delete().where(BacktestResult.strategy == strategy).execute()
            StrategySignal.delete().where(StrategySignal.strategy == strategy).execute()
            strategy.delete_instance()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _strategy_to_dict(strategy):
        """将策略对象转换为字典"""
        return {
            'id': strategy.id,
            'uuid': strategy.uuid,
            'name': strategy.name,
            'type': strategy.type,
            'category': strategy.category,
            'description': strategy.description,
            'logic_description': strategy.logic_description,
            'author': strategy.author,
            'status': strategy.status,
            'entry_conditions': json.loads(strategy.entry_conditions),
            'exit_conditions': json.loads(strategy.exit_conditions) if strategy.exit_conditions else {},
            'required_indicators': json.loads(strategy.required_indicators),
            'parameters': json.loads(strategy.parameters),
            'risk_warning': strategy.risk_warning,
            'created_at': strategy.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': strategy.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'total_backtests': strategy.total_backtests,
            'avg_return': strategy.avg_return,
            'avg_win_rate': strategy.avg_win_rate,
            'avg_max_drawdown': strategy.avg_max_drawdown
        }


class BacktestDB:
    """回测结果数据库操作类"""
    
    @staticmethod
    def save_backtest_result(result_data):
        """
        保存回测结果
        
        Args:
            result_data: 回测结果数据字典
            
        Returns:
            dict: {success: bool, backtest_id: int, error: str}
        """
        try:
            result = BacktestResult.create(
                strategy=result_data['strategy_id'],
                stock_code=result_data['stock_code'],
                stock_name=result_data['stock_name'],
                start_date=result_data['start_date'],
                end_date=result_data['end_date'],
                initial_capital=result_data.get('initial_capital', 100000),
                final_capital=result_data.get('final_capital'),
                total_return=result_data.get('total_return'),
                annual_return=result_data.get('annual_return'),
                max_drawdown=result_data.get('max_drawdown'),
                sharpe_ratio=result_data.get('sharpe_ratio'),
                total_trades=result_data.get('total_trades', 0),
                win_trades=result_data.get('win_trades', 0),
                lose_trades=result_data.get('lose_trades', 0),
                win_rate=result_data.get('win_rate'),
                profit_loss_ratio=result_data.get('profit_loss_ratio'),
                avg_holding_days=result_data.get('avg_holding_days'),
                period_returns=json.dumps(result_data.get('period_returns', {}), ensure_ascii=False),
                trade_details=json.dumps(result_data.get('trade_details', []), ensure_ascii=False)
            )
            
            # 更新策略统计信息
            BacktestDB._update_strategy_stats(result_data['strategy_id'])
            
            return {'success': True, 'backtest_id': result.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def _update_strategy_stats(strategy_id):
        """更新策略的统计信息"""
        try:
            strategy = Strategy.get_by_id(strategy_id)
            backtests = BacktestResult.select().where(BacktestResult.strategy == strategy)
            
            if backtests.count() > 0:
                total_backtests = backtests.count()
                
                # 计算平均值(过滤None值)
                returns = [b.total_return for b in backtests if b.total_return is not None]
                win_rates = [b.win_rate for b in backtests if b.win_rate is not None]
                drawdowns = [b.max_drawdown for b in backtests if b.max_drawdown is not None]
                
                strategy.total_backtests = total_backtests
                strategy.avg_return = sum(returns) / len(returns) if returns else None
                strategy.avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else None
                strategy.avg_max_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
                strategy.save()
        except Exception as e:
            print(f"⚠️ 更新策略统计信息失败: {e}")


# 主程序入口
if __name__ == '__main__':
    # 初始化数据库
    init_database()
    
    # 测试创建策略
    import uuid
    test_strategy = {
        'uuid': str(uuid.uuid4()),
        'name': '测试均线突破策略',
        'type': 'trading',
        'description': '股价突破20日均线买入',
        'logic_description': '当股价向上突破20天平均价格时买入',
        'entry_conditions': {
            'logic': 'AND',
            'rules': [{'indicator': 'CLOSE', 'operator': '>', 'value': 'MA20'}]
        },
        'required_indicators': ['MA20']
    }
    
    result = StrategyDB.create_strategy(test_strategy)
    if result['success']:
        print(f"✅ 测试策略创建成功，ID: {result['strategy_id']}")
        
        # 测试查询
        query_result = StrategyDB.list_strategies()
        print(f"✅ 查询到 {len(query_result['strategies'])} 个策略")
    else:
        print(f"❌ 策略创建失败: {result['error']}")
