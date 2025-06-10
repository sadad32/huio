//+------------------------------------------------------------------+
//|                                             CustomTradingEA.mq5 |
//|                                                          User |
//|                                                          User |
//+------------------------------------------------------------------+
#property copyright "User"
#property link      "User"
#property version   "1.00"
#property description "Custom Trading EA with multiple indicators and modes."

#include <Trade\Trade.mqh>
CTrade trade;

// Global Variables for Indicator Handles
int hFastMA, hSlowMA, hRSI, hMACD, hStochastic;

// Global Arrays for Indicator Values
double arrFastMA[], arrSlowMA[], arrRSI[], arrMACDMain[], arrMACDSignal[], arrStochasticMain[], arrStochasticSignal[];

// Input Parameters
//--- Trading Settings ---
enum EnumTradingMode
  {
   MODE_AUTOMATIC,      // Fully Automatic Trading
   MODE_MANUAL_ALERTS // Manual Trading (Alerts Only)
  };
input EnumTradingMode inpTradingMode = MODE_AUTOMATIC; // Trading Mode

input ulong    inpMagicNumber = 12345; // Magic Number

enum EnumLotSizingStrategy {
    LOT_STRATEGY_FIXED,     // Fixed Lot Size
    LOT_STRATEGY_PERCENT_EQUITY // Percentage of Equity
};

input EnumLotSizingStrategy inpLotSizingStrategy = LOT_STRATEGY_FIXED; // Lot Sizing Strategy
input double   inpFixedLotSize = 0.01;        // Fixed Lot Size
input double   inpEquityPercentage = 1.0;     // Percentage of Equity for Lot Sizing (e.g., 1.0 for 1%)
input int      inpStopLossPips = 50;          // Stop Loss in Pips
input int      inpTakeProfitPips = 100;         // Take Profit in Pips
input bool     inpEnableTrailingStop = true;   // Enable/Disable Trailing Stop
input int      inpTrailingStopTriggerPips = 20; // Pips in profit to trigger trailing stop
input int      inpTrailingStopStepPips = 5;   // Trailing Stop Step in Pips
// Input for timeframes might be better handled by chart timeframe or internal logic, will omit direct input for now and address in strategy section.

//--- Indicator Settings: Moving Averages ---
input int      inpFastMAPeriod = 10;           // Fast MA Period
input ENUM_MA_METHOD inpFastMAMethod = MODE_EMA; // Fast MA Method (EMA, SMA, etc.)
input ENUM_APPLIED_PRICE inpFastMAPrice = PRICE_CLOSE; // Fast MA Applied Price
input int      inpSlowMAPeriod = 20;           // Slow MA Period
input ENUM_MA_METHOD inpSlowMAMethod = MODE_EMA; // Slow MA Method
input ENUM_APPLIED_PRICE inpSlowMAPrice = PRICE_CLOSE; // Slow MA Applied Price

//--- Indicator Settings: RSI ---
input int      inpRSIPeriod = 14;            // RSI Period
input ENUM_APPLIED_PRICE inpRSIPrice = PRICE_CLOSE; // RSI Applied Price

//--- Indicator Settings: MACD ---
input int      inpMACDFastEMAPeriod = 12;    // MACD Fast EMA Period
input int      inpMACDSlowEMAPeriod = 26;    // MACD Slow EMA Period
input int      inpMACDSignalMAPeriod = 9;     // MACD Signal MA Period
input ENUM_APPLIED_PRICE inpMACDPrice = PRICE_CLOSE;// MACD Applied Price

//--- Indicator Settings: Stochastic ---
input int      inpStochasticKPeriod = 5;      // Stochastic %K Period
input int      inpStochasticDPeriod = 3;      // Stochastic %D Period
input int      inpStochasticSlowing = 3;      // Stochastic Slowing
input ENUM_MA_METHOD inpStochasticMAMethod = MODE_SMA; // Stochastic MA Method
input ENUM_STO_PRICE inpStochasticPriceField = STO_LOWHIGH; // Stochastic Price Field (Low/High or Close/Close)

//--- Signal Thresholds ---
input double   inpRSIOverbought = 70.0;      // RSI Overbought Level
input double   inpRSIOversold = 30.0;        // RSI Oversold Level

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- Initialization logic here
   hFastMA = iMA(_Symbol, _Period, inpFastMAPeriod, 0, inpFastMAMethod, inpFastMAPrice);
   if(hFastMA == INVALID_HANDLE) { Print("Error initializing Fast MA"); return(INIT_FAILED); }

   hSlowMA = iMA(_Symbol, _Period, inpSlowMAPeriod, 0, inpSlowMAMethod, inpSlowMAPrice);
   if(hSlowMA == INVALID_HANDLE) { Print("Error initializing Slow MA"); return(INIT_FAILED); }

   hRSI = iRSI(_Symbol, _Period, inpRSIPeriod, inpRSIPrice);
   if(hRSI == INVALID_HANDLE) { Print("Error initializing RSI"); return(INIT_FAILED); }

   hMACD = iMACD(_Symbol, _Period, inpMACDFastEMAPeriod, inpMACDSlowEMAPeriod, inpMACDSignalMAPeriod, inpMACDPrice);
   if(hMACD == INVALID_HANDLE) { Print("Error initializing MACD"); return(INIT_FAILED); }

   hStochastic = iStochastic(_Symbol, _Period, inpStochasticKPeriod, inpStochasticDPeriod, inpStochasticSlowing, inpStochasticMAMethod, inpStochasticPriceField);
   if(hStochastic == INVALID_HANDLE) { Print("Error initializing Stochastic"); return(INIT_FAILED); }

   // Set arrays as series
   ArraySetAsSeries(arrFastMA, true);
   ArraySetAsSeries(arrSlowMA, true);
   ArraySetAsSeries(arrRSI, true);
   ArraySetAsSeries(arrMACDMain, true);
   ArraySetAsSeries(arrMACDSignal, true);
   ArraySetAsSeries(arrStochasticMain, true);
   ArraySetAsSeries(arrStochasticSignal, true);

   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//--- Deinitialization logic here
   IndicatorRelease(hFastMA);
   IndicatorRelease(hSlowMA);
   IndicatorRelease(hRSI);
   IndicatorRelease(hMACD);
   IndicatorRelease(hStochastic);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
//--- Main trading logic here
   // Copy indicator buffers
   if(CopyBuffer(hFastMA, 0, 0, 3, arrFastMA) <= 0) { Print("Error copying Fast MA buffer"); return; }
   if(CopyBuffer(hSlowMA, 0, 0, 3, arrSlowMA) <= 0) { Print("Error copying Slow MA buffer"); return; }
   if(CopyBuffer(hRSI, 0, 0, 3, arrRSI) <= 0) { Print("Error copying RSI buffer"); return; }
   if(CopyBuffer(hMACD, 0, 0, 3, arrMACDMain) <= 0) { Print("Error copying MACD Main buffer"); return; }
   if(CopyBuffer(hMACD, 1, 0, 3, arrMACDSignal) <= 0) { Print("Error copying MACD Signal buffer"); return; }
   if(CopyBuffer(hStochastic, 0, 0, 3, arrStochasticMain) <= 0) { Print("Error copying Stochastic Main buffer"); return; }
   if(CopyBuffer(hStochastic, 1, 0, 3, arrStochasticSignal) <= 0) { Print("Error copying Stochastic Signal buffer"); return; }

   // Check for signals once per bar
   static datetime BarTime = 0;
   if (BarTime == iTime(_Symbol, _Period, 0)) return;
   BarTime = iTime(_Symbol, _Period, 0);

   // Check if a position already exists for this EA on this symbol
   bool positionExists = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i); // Get ticket first
      if(PositionSelectByTicket(ticket)) // Select position by ticket
        {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == inpMagicNumber)
           {
            positionExists = true;
            break;
           }
        }
     }

   if(CheckBuySignal() && !positionExists)
     {
      if(inpTradingMode == MODE_AUTOMATIC)
        {
         Print("BUY SIGNAL DETECTED (Automatic Trading) on ", _Symbol, " ", EnumToString(_Period), " at ", TimeToString(TimeCurrent()));
         ExecuteTrade(ORDER_TYPE_BUY);
        }
      else if(inpTradingMode == MODE_MANUAL_ALERTS)
        {
         double potentialSL_Buy = SymbolInfoDouble(_Symbol, SYMBOL_BID) - inpStopLossPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         double potentialTP_Buy = SymbolInfoDouble(_Symbol, SYMBOL_BID) + inpTakeProfitPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         if(inpStopLossPips == 0) potentialSL_Buy = 0.0;
         if(inpTakeProfitPips == 0) potentialTP_Buy = 0.0;
         string alertMsgBuy = StringFormat("MANUAL TRADE ALERT: %s %s\nPotential BUY Signal @ ~%.5f\nSL: %.5f (if > 0 else none)\nTP: %.5f (if > 0 else none)",
                                          _Symbol, EnumToString(_Period), SymbolInfoDouble(_Symbol, SYMBOL_ASK), potentialSL_Buy, potentialTP_Buy);
         Alert(alertMsgBuy);
         Print(alertMsgBuy); // Also print to Experts log
        }
     }

   if(CheckSellSignal() && !positionExists)
     {
      if(inpTradingMode == MODE_AUTOMATIC)
        {
         Print("SELL SIGNAL DETECTED (Automatic Trading) on ", _Symbol, " ", EnumToString(_Period), " at ", TimeToString(TimeCurrent()));
         ExecuteTrade(ORDER_TYPE_SELL);
        }
      else if(inpTradingMode == MODE_MANUAL_ALERTS)
        {
         double potentialSL_Sell = SymbolInfoDouble(_Symbol, SYMBOL_ASK) + inpStopLossPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         double potentialTP_Sell = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - inpTakeProfitPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         if(inpStopLossPips == 0) potentialSL_Sell = 0.0;
         if(inpTakeProfitPips == 0) potentialTP_Sell = 0.0;
         string alertMsgSell = StringFormat("MANUAL TRADE ALERT: %s %s\nPotential SELL Signal @ ~%.5f\nSL: %.5f (if > 0 else none)\nTP: %.5f (if > 0 else none)",
                                           _Symbol, EnumToString(_Period), SymbolInfoDouble(_Symbol, SYMBOL_BID), potentialSL_Sell, potentialTP_Sell);
         Alert(alertMsgSell);
         Print(alertMsgSell); // Also print to Experts log
        }
     }

   if(inpEnableTrailingStop && inpTradingMode == MODE_AUTOMATIC) // Trailing stop only makes sense for automatic trades
     {
      ManageTrailingStops();
     }
  }
//+------------------------------------------------------------------+
//| Check for Buy Signal                                             |
//+------------------------------------------------------------------+
bool CheckBuySignal()
  {
   // Ensure we have enough data. Index 1 is the last completed bar, index 2 is the one before that.
   // We need at least 2 bars of data for simple checks, 3 for crossover checks using [1] and [2].
   // CopyBuffer is already copying 3 bars, so arr*.Buffer[0,1,2] should be available.
   if(ArraySize(arrFastMA) < 2 || ArraySize(arrSlowMA) < 2 || ArraySize(arrRSI) < 2 || ArraySize(arrMACDMain) < 2 || ArraySize(arrMACDSignal) < 2)
     {
      Print("Not enough data in indicator arrays for signal check.");
      return false;
     }

   bool fastAboveslow = arrFastMA[1] > arrSlowMA[1];
   bool rsiOversold = arrRSI[1] < inpRSIOversold;
   bool macdBullish = arrMACDMain[1] > arrMACDSignal[1];
   // bool stochasticBullish = arrStochasticMain[1] > arrStochasticSignal[1] && arrStochasticMain[1] < 20; // Example

   return (fastAboveslow && rsiOversold && macdBullish);
  }
//+------------------------------------------------------------------+
//| Check for Sell Signal                                            |
//+------------------------------------------------------------------+
bool CheckSellSignal()
  {
   // Ensure we have enough data
   if(ArraySize(arrFastMA) < 2 || ArraySize(arrSlowMA) < 2 || ArraySize(arrRSI) < 2 || ArraySize(arrMACDMain) < 2 || ArraySize(arrMACDSignal) < 2)
     {
      Print("Not enough data in indicator arrays for signal check.");
      return false;
     }

   bool fastBelowslow = arrFastMA[1] < arrSlowMA[1];
   bool rsiOverbought = arrRSI[1] > inpRSIOverbought;
   bool macdBearish = arrMACDMain[1] < arrMACDSignal[1];
   // bool stochasticBearish = arrStochasticMain[1] < arrStochasticSignal[1] && arrStochasticMain[1] > 80; // Example

   return (fastBelowslow && rsiOverbought && macdBearish);
  }
//+------------------------------------------------------------------+
//| Helper function for Lot Size Calculation                         |
//+------------------------------------------------------------------+
double CalculateLotSize()
  {
   if(inpLotSizingStrategy == LOT_STRATEGY_FIXED)
      return NormalizeDouble(inpFixedLotSize, 2);

   if(inpLotSizingStrategy == LOT_STRATEGY_PERCENT_EQUITY)
     {
      double accountBalance = AccountInfoDouble(ACCOUNT_EQUITY);
      double riskAmount = accountBalance * (inpEquityPercentage / 100.0);

      // Ensure Stop Loss Pips is positive for calculation, otherwise, it makes no sense for risk %
      if (inpStopLossPips <= 0)
        {
         Print("Error: Stop Loss must be greater than 0 for Percentage of Equity lot sizing.");
         return 0.0; // Cannot calculate lot size without a valid SL
        }

      double stopLossDistance = inpStopLossPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);

      if(tickValue <= 0 || stopLossDistance <= 0) // Avoid division by zero or invalid values
        {
         Print("Error: Tick Value or Stop Loss Distance is zero or negative. Symbol: ", _Symbol, " TickValue: ", tickValue, " SL Distance: ", stopLossDistance);
         return 0.0;
        }

      double lotSize = riskAmount / (stopLossDistance / SymbolInfoDouble(_Symbol, SYMBOL_POINT) * tickValue);

      // Normalize lot size and check against min/max limits
      lotSize = NormalizeDouble(lotSize, 2); // Normalize to 2 decimal places first

      double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

      if (lotSize < minLot) lotSize = minLot;
      if (lotSize > maxLot) lotSize = maxLot;

      // Adjust to lot step
      lotSize = NormalizeDouble(floor(lotSize / lotStep) * lotStep, 2);

      if(lotSize < minLot) // After step adjustment, it might go below minLot if minLot itself is not a multiple of lotStep (rare, but possible)
        {
        Print("Warning: Calculated lot size ", lotSize, " after step adjustment is less than MinLot ", minLot, ". Adjusting to MinLot.");
        lotSize = minLot;
        }

      return lotSize;
     }
   return NormalizeDouble(inpFixedLotSize, 2); // Default fallback
  }
//+------------------------------------------------------------------+
//| Execute Trade Function                                           |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE orderType)
  {
   double lot = CalculateLotSize();
   if(lot <= 0)
     {
      Print("Error: Calculated lot size is 0 or less. Lot: ", lot);
      return;
     }

   double price = 0.0;
   double sl = 0.0;
   double tp = 0.0;
   string comment = "";

   trade.SetExpertMagicNumber(inpMagicNumber);
   trade.SetDeviationInPoints(5); // Or make this an input parameter

   if(orderType == ORDER_TYPE_BUY)
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(inpStopLossPips > 0)
         sl = SymbolInfoDouble(_Symbol, SYMBOL_BID) - inpStopLossPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      if(inpTakeProfitPips > 0)
         tp = SymbolInfoDouble(_Symbol, SYMBOL_BID) + inpTakeProfitPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      comment = "Buy Order by EA";

      // Adjust SL and TP to be valid if they are too close to the market
      double stopLevelPips = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double stopLevelPoints = stopLevelPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);

      if(sl != 0.0 && price - sl < stopLevelPoints)
        {
         Print("SL too close for BUY order, adjusting. Original SL: ", sl, ", Price: ", price, ", StopLevelPoints: ", stopLevelPoints);
         sl = price - stopLevelPoints;
        }
      if(tp != 0.0 && tp - price < stopLevelPoints)
        {
         Print("TP too close for BUY order, adjusting. Original TP: ", tp, ", Price: ", price, ", StopLevelPoints: ", stopLevelPoints);
         tp = price + stopLevelPoints;
        }

      if(!trade.Buy(lot, _Symbol, price, sl, tp, comment))
        {
         Print("Buy order failed: ", trade.ResultRetcode(), " - ", trade.ResultComment());
        }
      else
        {
         Print("Buy order placed successfully. Ticket: ", trade.ResultOrder());
        }
     }
   else if(orderType == ORDER_TYPE_SELL)
     {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(inpStopLossPips > 0)
         sl = SymbolInfoDouble(_Symbol, SYMBOL_ASK) + inpStopLossPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      if(inpTakeProfitPips > 0)
         tp = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - inpTakeProfitPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      comment = "Sell Order by EA";

      // Adjust SL and TP to be valid if they are too close to the market
      double stopLevelPips = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double stopLevelPoints = stopLevelPips * SymbolInfoDouble(_Symbol, SYMBOL_POINT);

      if(sl != 0.0 && sl - price < stopLevelPoints)
        {
         Print("SL too close for SELL order, adjusting. Original SL: ", sl, ", Price: ", price, ", StopLevelPoints: ", stopLevelPoints);
         sl = price + stopLevelPoints;
        }
      if(tp != 0.0 && price - tp < stopLevelPoints)
        {
         Print("TP too close for SELL order, adjusting. Original TP: ", tp, ", Price: ", price, ", StopLevelPoints: ", stopLevelPoints);
         tp = price - stopLevelPoints;
        }

      if(!trade.Sell(lot, _Symbol, price, sl, tp, comment))
        {
         Print("Sell order failed: ", trade.ResultRetcode(), " - ", trade.ResultComment());
        }
      else
        {
         Print("Sell order placed successfully. Ticket: ", trade.ResultOrder());
        }
     }
  }
//+------------------------------------------------------------------+
//| Manage Trailing Stops                                            |
//+------------------------------------------------------------------+
void ManageTrailingStops()
  {
   if(!inpEnableTrailingStop || inpTrailingStopTriggerPips <= 0 || inpTrailingStopStepPips <= 0)
      return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) // Ensure position is selected
        {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == inpMagicNumber)
           {
            ENUM_POSITION_TYPE positionType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            double currentSL = PositionGetDouble(POSITION_SL);
            double currentTP = PositionGetDouble(POSITION_TP); // Keep original TP
            double newSL = currentSL;
            double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

            if(positionType == POSITION_TYPE_BUY)
              {
               double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
               if(currentPrice > openPrice + inpTrailingStopTriggerPips * point)
                 {
                  double potentialNewSL = currentPrice - inpTrailingStopStepPips * point;
                  if(potentialNewSL > currentSL || currentSL == 0.0) // If new SL is better or SL not set
                    {
                     newSL = potentialNewSL;
                     // Ensure new SL is not too close to the market
                     double stopLevelPoints = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
                     if (currentPrice - newSL < stopLevelPoints)
                       {
                        newSL = currentPrice - stopLevelPoints;
                        Print("Trailing SL for BUY (ticket: ", ticket, ") adjusted to avoid being too close. New SL: ", newSL);
                       }

                     if(newSL != currentSL) // Check if modification is actually needed
                       {
                        if(trade.PositionModify(ticket, newSL, currentTP))
                          {
                           Print("Trailing stop for BUY position ", ticket, " modified. New SL: ", newSL);
                          }
                        else
                          {
                           Print("Error modifying trailing stop for BUY position ", ticket, ": ", trade.ResultRetcode(), " - ", trade.ResultComment());
                          }
                       }
                    }
                 }
              }
            else if(positionType == POSITION_TYPE_SELL)
              {
               double currentPrice = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
               if(currentPrice < openPrice - inpTrailingStopTriggerPips * point)
                 {
                  double potentialNewSL = currentPrice + inpTrailingStopStepPips * point;
                  if(potentialNewSL < currentSL || currentSL == 0.0) // If new SL is better or SL not set
                    {
                     newSL = potentialNewSL;
                     // Ensure new SL is not too close to the market
                     double stopLevelPoints = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
                     if (newSL - currentPrice < stopLevelPoints)
                       {
                        newSL = currentPrice + stopLevelPoints;
                        Print("Trailing SL for SELL (ticket: ", ticket, ") adjusted to avoid being too close. New SL: ", newSL);
                       }

                     if(newSL != currentSL) // Check if modification is actually needed
                       {
                        if(trade.PositionModify(ticket, newSL, currentTP))
                          {
                           Print("Trailing stop for SELL position ", ticket, " modified. New SL: ", newSL);
                          }
                        else
                          {
                           Print("Error modifying trailing stop for SELL position ", ticket, ": ", trade.ResultRetcode(), " - ", trade.ResultComment());
                          }
                       }
                    }
                 }
              }
           }
        }
      else
        {
         Print("Error selecting position by ticket ", ticket, " in ManageTrailingStops. Error code: ", GetLastError());
        }
     }
  }
//+------------------------------------------------------------------+
