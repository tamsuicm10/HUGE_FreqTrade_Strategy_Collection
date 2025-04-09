from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from datetime import datetime, timedelta
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from typing import Optional


class kodok(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '5m'

    minimal_roi = {"0": 0.5}  
    stoploss = -0.5           
    can_short = True

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.08
    trailing_only_offset_is_reached = True

    startup_candle_count = 200
    process_only_new_candles = True
    position_adjustment_enable = True
    max_entry_position_adjustment = 1  # 1 kali DCA = 2 posisi total

    leverage_value = 10.0
    last_profit_trade_time: Optional[datetime] = None
    delay_after_profit = timedelta(hours=1)

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, **kwargs) -> float:
        return min(self.leverage_value, max_leverage)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_12'] = ta.EMA(dataframe['close'], timeperiod=12)
        dataframe['ema_34'] = ta.EMA(dataframe['close'], timeperiod=34)
        dataframe['ema_100'] = ta.EMA(dataframe['close'], timeperiod=100)
        dataframe['adx'] = ta.ADX(dataframe)
    
        dataframe['signal_long'] = (
            qtpylib.crossed_above(dataframe['ema_12'], dataframe['ema_34']) &
            (dataframe['ema_12'] > dataframe['ema_100']) &
            (dataframe['ema_34'] > dataframe['ema_100'])
        ).astype(int)
      
        dataframe['signal_short'] = (
            qtpylib.crossed_below(dataframe['ema_12'], dataframe['ema_34']) &
            (dataframe['ema_12'] < dataframe['ema_100']) &
            (dataframe['ema_34'] < dataframe['ema_100'])
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        now = datetime.utcnow()
        delay_active = self.last_profit_trade_time and (now < self.last_profit_trade_time + self.delay_after_profit)

        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        if not delay_active:
            dataframe.loc[
                (dataframe['signal_long'] == 1) & (dataframe['adx'] > 20),
                'enter_long'
            ] = 1

            dataframe.loc[
                (dataframe['signal_short'] == 1) & (dataframe['adx'] > 20),
                'enter_short'
            ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe

    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float,
                current_profit: float, **kwargs):
        if trade.nr_of_successful_entries >= 1:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1]

            if trade.is_short and last_candle['signal_long'] == 1:
                return "Exit Short (Reversal)"
            if not trade.is_short and last_candle['signal_short'] == 1:
                return "Exit Long (Reversal)"
              
        if current_profit > 0.1:
            self.last_profit_trade_time = current_time

        return None
