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
int hFastMA, hSlowMA, hRSI, hMACD, hStochastic, hBollingerBands, hATR; // hFastMA, hSlowMA are from old logic, hMACD is needed again. Added hATR

// Global Arrays for Indicator Values
double arrFastMA[], arrSlowMA[], arrRSI[], arrMACDMain[], arrMACDSignal[], arrStochasticMain[], arrStochasticSignal[]; // arrFastMA, arrSlowMA for old logic, arrMACD needed
double arrATR[]; // For ATR values
double arrBBUpper[], arrBBMiddle[], arrBBLower[];
long arrVolume[]; // For Real Volume data

// Pivot Point Variables
double pivot_PP, pivot_S1, pivot_R1, pivot_S2, pivot_R2, pivot_S3, pivot_R3;
static datetime lastPivotRecalcTime = 0; // Tracks the D1 bar open time for which pivots were last calculated

// Input Parameters
//--- Trading Settings ---
enum EnumTradingMode
  {
   MODE_AUTOMATIC,      // Fully Automatic Trading
   MODE_MANUAL_ALERTS // Manual Trading (Alerts Only)
  };
input EnumTradingMode inpTradingMode = MODE_AUTOMATIC; // Trading Mode

// --- Stop Loss & Take Profit Settings ---
enum EnumSLTPMode { MODE_PIPS, MODE_ATR };
input EnumSLTPMode inpSLTPMode = MODE_PIPS;      // SL/TP Calculation Mode
input int      inpStopLossPips = 15;          // Stop Loss in Pips (Default for Reversal/Scalp)
input int      inpTakeProfitPips = 30;         // Take Profit in Pips (Default for Reversal/Scalp)
input int      inpATRPeriodSLTP = 14;             // ATR Period for SL/TP
input double   inpATRMultiplierSL = 2.0;          // ATR Multiplier for Stop Loss
input double   inpATRMultiplierTP = 3.0;          // ATR Multiplier for Take Profit

//--- Indicator Settings: Bollinger Bands ---
input int      inpBBPeriod = 20;               // Bollinger Bands Period
input double   inpBBDeviations = 2.0;         // Bollinger Bands Deviations
input int      inpBBShift = 0;                 // Bollinger Bands Shift (usually 0)
input ENUM_APPLIED_PRICE inpBBPrice = PRICE_CLOSE; // Bollinger Bands Applied Price

//--- Pivot Point Settings ---
input int inpPivotPointBufferPips = 5; // Buffer in pips for pivot point reaction

//--- Reversal Signal Thresholds (RSI/Stochastic) ---
input double   inpRSIReversalOverbought = 70.0;      // RSI Overbought Level for Reversal
input double   inpRSIReversalOversold = 30.0;        // RSI Oversold Level for Reversal
input double   inpStochasticReversalOverbought = 80.0; // Stochastic Overbought for Reversal
input double   inpStochasticReversalOversold = 20.0;   // Stochastic Oversold for Reversal

// --- Secondary Confirmation Settings ---
input bool inpEnableVolumeConfirmation = true;  // Enable Volume Confirmation
input int  inpVolumeLookbackPeriod = 20;       // Lookback period for average volume
input double inpVolumeMultiplier = 1.5;         // Multiplier for current volume vs. average
input bool inpEnableMACDConfirmation = true;   // Enable MACD Confirmation
// Note: MACD parameters like inpMACDFastEMAPeriod should exist from original EA structure. Assuming they do.

input ulong    inpMagicNumber = 12345; // Magic Number

enum EnumLotSizingStrategy {
    LOT_STRATEGY_FIXED,     // Fixed Lot Size
    LOT_STRATEGY_PERCENT_EQUITY // Percentage of Equity
};

input EnumLotSizingStrategy inpLotSizingStrategy = LOT_STRATEGY_FIXED; // Lot Sizing Strategy
input double   inpFixedLotSize = 0.01;        // Fixed Lot Size
input double   inpEquityPercentage = 1.0;     // Percentage of Equity for Lot Sizing (e.g., 1.0 for 1%)
// input int      inpStopLossPips = 50;          // Stop Loss in Pips - Replaced by new SLTP settings above
// input int      inpTakeProfitPips = 100;         // Take Profit in Pips - Replaced by new SLTP settings above
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

//--- Signal Thresholds (Original - can be kept for other modes or removed if only reversal is used) ---
// input double   inpRSIOverbought = 70.0;      // RSI Overbought Level (Original)
// input double   inpRSIOversold = 30.0;        // RSI Oversold Level (Original)

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

   hBollingerBands = iBands(_Symbol, _Period, inpBBPeriod, inpBBShift, inpBBDeviations, inpBBPrice);
   if(hBollingerBands == INVALID_HANDLE) { Print("Error initializing Bollinger Bands"); return(INIT_FAILED); }

   // Set arrays as series
   ArraySetAsSeries(arrFastMA, true);
   ArraySetAsSeries(arrSlowMA, true);
   ArraySetAsSeries(arrRSI, true);
   ArraySetAsSeries(arrMACDMain, true);
   ArraySetAsSeries(arrMACDSignal, true);
   ArraySetAsSeries(arrStochasticMain, true);
   ArraySetAsSeries(arrStochasticSignal, true);
   ArraySetAsSeries(arrBBUpper, true);
   ArraySetAsSeries(arrBBMiddle, true);
   ArraySetAsSeries(arrBBLower, true);
   ArraySetAsSeries(arrVolume, true); // Set series for Volume array
   ArraySetAsSeries(arrATR, true);    // Set series for ATR array

   // Ensure MACD is initialized (it might have been removed if not used by core signal)
   // Assuming MACD inputs (inpMACDFastEMAPeriod, etc.) are present globally
   hMACD = iMACD(_Symbol, _Period, inpMACDFastEMAPeriod, inpMACDSlowEMAPeriod, inpMACDSignalMAPeriod, inpMACDPrice);
   if(hMACD == INVALID_HANDLE) { Print("Error initializing MACD for confirmation"); return(INIT_FAILED); }

   hATR = iATR(_Symbol, _Period, inpATRPeriodSLTP);
   if(hATR == INVALID_HANDLE) { Print("Error initializing ATR indicator: ", GetLastError()); return(INIT_FAILED); }

   // arrMACDMain and arrMACDSignal should already be set as series if hMACD init is here.

   // Initial Pivot Calculation
   if(Bars(_Symbol, PERIOD_D1) > 1) // Ensure previous day's bar exists for initial calculation
     {
      CalculateDailyPivotPoints(PERIOD_D1);
      lastPivotRecalcTime = iTime(_Symbol, PERIOD_D1, 0); // Set based on current D1 bar open
     }
   else
     {
      Print("Not enough D1 bars to calculate initial pivot points.");
     }


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
   IndicatorRelease(hBollingerBands);
   IndicatorRelease(hATR);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Recalculate pivot points at the start of a new D1 bar
   datetime currentD1BarOpen = iTime(_Symbol, PERIOD_D1, 0);
   if(lastPivotRecalcTime != currentD1BarOpen)
     {
      if(Bars(_Symbol, PERIOD_D1) > 1) // Make sure previous day's bar exists for calculation
        {
         CalculateDailyPivotPoints(PERIOD_D1);
         lastPivotRecalcTime = currentD1BarOpen;
        }
     }

//--- Main trading logic here
   // Copy indicator buffers
   if(CopyBuffer(hFastMA, 0, 0, 3, arrFastMA) <= 0) { Print("Error copying Fast MA buffer"); return; }
   if(CopyBuffer(hSlowMA, 0, 0, 3, arrSlowMA) <= 0) { Print("Error copying Slow MA buffer"); return; }
   if(CopyBuffer(hRSI, 0, 0, 3, arrRSI) <= 0) { Print("Error copying RSI buffer"); return; }
   if(CopyBuffer(hMACD, 0, 0, 3, arrMACDMain) <= 0) { Print("Error copying MACD Main buffer"); return; }
   if(CopyBuffer(hMACD, 1, 0, 3, arrMACDSignal) <= 0) { Print("Error copying MACD Signal buffer"); return; }
   if(CopyBuffer(hStochastic, 0, 0, 3, arrStochasticMain) <= 0) { Print("Error copying Stochastic Main buffer"); return; }
   if(CopyBuffer(hStochastic, 1, 0, 3, arrStochasticSignal) <= 0) { Print("Error copying Stochastic Signal buffer"); return; }
   if(CopyBuffer(hBollingerBands, 0, 0, 3, arrBBUpper) <= 0) { Print("Error copying BB Upper buffer"); return; } // UPPER_BAND
   if(CopyBuffer(hBollingerBands, 1, 0, 3, arrBBMiddle) <= 0) { Print("Error copying BB Middle buffer"); return; } // BASE_LINE / Middle
   if(CopyBuffer(hBollingerBands, 2, 0, 3, arrBBLower) <= 0) { Print("Error copying BB Lower buffer"); return; } // LOWER_BAND

   // Copy Volume Data
   // Copy enough data: inpVolumeLookbackPeriod for average + signal bar [1] + current bar [0]
   // So, inpVolumeLookbackPeriod previous bars means indices from 2 to inpVolumeLookbackPeriod+1
   // Total elements to copy: inpVolumeLookbackPeriod + 2
   int volDataToCopy = inpVolumeLookbackPeriod + 2;
   if(CopyRealVolume(_Symbol, _Period, 0, volDataToCopy, arrVolume) < volDataToCopy)
     { Print("Error copying volume data, not enough bars or error. Needed: ", volDataToCopy, " Got: ", ArraySize(arrVolume)); return; }

   // Ensure MACD data is copied (arrMACDMain, arrMACDSignal should be populated)
   // This was already part of the OnTick if MACD handle (hMACD) is valid and initialized.
   // Redundant CopyBuffer calls for MACD here if they are already above. Let's ensure they are there.
   // The existing CopyBuffer for hMACD should be fine if hMACD is properly initialized.
   // if(CopyBuffer(hMACD, 0, 0, 3, arrMACDMain) <= 0) { Print("Error copying MACD Main buffer for confirmation"); return; }
   // if(CopyBuffer(hMACD, 1, 0, 3, arrMACDSignal) <= 0) { Print("Error copying MACD Signal buffer for confirmation"); return; }
   // The above MACD copy calls are likely already present from original structure. If not, they'd be needed.
   // For this subtask, I'm focusing on adding the logic that USES these, assuming they are populated.

   // Copy ATR Buffer
   if(CopyBuffer(hATR, 0, 0, 3, arrATR) < 3)
     {
      Print("Error copying ATR buffer: ", GetLastError());
      return;
     }

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
   // 0-1 Reversal Signal Logic
   // Ensure we have enough data for all indicators including BB. Low[1], High[1] are predefined.
   if(ArraySize(arrRSI) < 3 || ArraySize(arrStochasticMain) < 3 || ArraySize(arrStochasticSignal) < 3 || ArraySize(arrBBLower) < 2 || ArraySize(arrBBUpper) < 2 || Bars(_Symbol, _Period) < 3 )
     {
      Print("Not enough data in indicator arrays for Reversal signal check.");
      return false;
     }

   // 1. RSI Oversold
   bool rsi_condition = arrRSI[1] < inpRSIReversalOversold;

   // 2. Stochastic Oversold & Bullish Cross
   bool stochastic_condition = arrStochasticMain[1] < inpStochasticReversalOversold &&
                               arrStochasticSignal[1] < inpStochasticReversalOversold &&
                               arrStochasticMain[1] > arrStochasticSignal[1] && // Main crossed above Signal
                               arrStochasticMain[2] <= arrStochasticSignal[2]; // Main was below or equal to Signal on bar before

   // 3. Bollinger Band Lower Touch/Near
   bool bb_condition = Low[1] <= arrBBLower[1];

   // 4. Pivot Point Support Reaction
   double identifiedPivot_buy = 0;
   bool pivot_raw_hit = IsPriceNearPivot(Low[1], identifiedPivot_buy);
   bool pivot_is_support = (identifiedPivot_buy == pivot_PP || identifiedPivot_buy == pivot_S1 || identifiedPivot_buy == pivot_S2 || identifiedPivot_buy == pivot_S3);
   bool pivot_condition = pivot_raw_hit && pivot_is_support;

   bool coreSignal = rsi_condition && stochastic_condition && bb_condition && pivot_condition;

   if (!coreSignal) return false;

   if(coreSignal) // For clarity in logs, print core passed before checking secondary
     {
      Print("Core Reversal Buy Conditions Met: RSI=", rsi_condition, ", Stoch=", stochastic_condition, ", BB=", bb_condition, ", Pivot=", pivot_condition, " (Level: ", identifiedPivot_buy, ")");
     }

   // Secondary Confirmations
   if (inpEnableVolumeConfirmation)
     {
      // Ensure enough data: arrVolume[0] is current, [1] is signal bar, [2]...[LB_Period+1] are for avg
      if (inpVolumeLookbackPeriod + 1 >= ArraySize(arrVolume) || ArraySize(arrVolume) < inpVolumeLookbackPeriod + 2 )
        { Print("Not enough volume data for average. ArraySize: ", ArraySize(arrVolume), " Needed for lookback+signal: ", inpVolumeLookbackPeriod + 2); return false;}

      double avgVolume = 0;
      for (int i = 1; i <= inpVolumeLookbackPeriod; i++)
        {
         avgVolume += arrVolume[i + 1]; // Sum volumes from index 2 to inpVolumeLookbackPeriod + 1
        }
      avgVolume /= inpVolumeLookbackPeriod;

      if (arrVolume[1] < avgVolume * inpVolumeMultiplier)
        {
         Print("Volume confirmation FAILED for Buy. Signal Bar Volume: ", arrVolume[1], " Avg Volume: ", avgVolume, " Required Multiplier: ", inpVolumeMultiplier);
         return false;
        }
      Print("Volume confirmation PASSED for Buy. Signal Bar Volume: ", arrVolume[1], " Avg Volume: ", avgVolume);
     }

   if (inpEnableMACDConfirmation)
     {
      // Ensure arrMACDMain and arrMACDSignal have at least 3 elements for index [2] for crossover check
      if(ArraySize(arrMACDMain) < 3 || ArraySize(arrMACDSignal) < 3) { Print("Not enough MACD data for confirmation."); return false; }

      bool macd_buy_cross = arrMACDMain[1] > arrMACDSignal[1] && arrMACDMain[2] <= arrMACDSignal[2];
      if (!macd_buy_cross)
        {
         Print("MACD confirmation FAILED for Buy. Main[1]:", arrMACDMain[1], " Sig[1]:", arrMACDSignal[1], " Main[2]:", arrMACDMain[2], " Sig[2]:", arrMACDSignal[2]);
         return false;
        }
      Print("MACD confirmation PASSED for Buy.");
     }
   return true; // Core signal AND enabled confirmations are true
  }
//+------------------------------------------------------------------+
//| Check for Sell Signal                                            |
//+------------------------------------------------------------------+
bool CheckSellSignal()
  {
   // 0-1 Reversal Signal Logic for Sell
   // Ensure we have enough data for all indicators including BB. Low[1], High[1] are predefined.
   if(ArraySize(arrRSI) < 3 || ArraySize(arrStochasticMain) < 3 || ArraySize(arrStochasticSignal) < 3 || ArraySize(arrBBLower) < 2 || ArraySize(arrBBUpper) < 2 || Bars(_Symbol, _Period) < 3)
     {
      Print("Not enough data in indicator arrays for Reversal signal check.");
      return false;
     }

   // 1. RSI Overbought
   bool rsi_condition_sell = arrRSI[1] > inpRSIReversalOverbought;

   // 2. Stochastic Overbought & Bearish Cross
   bool stochastic_condition_sell = arrStochasticMain[1] > inpStochasticReversalOverbought &&
                                    arrStochasticSignal[1] > inpStochasticReversalOverbought &&
                                    arrStochasticMain[1] < arrStochasticSignal[1] && // Main crossed below Signal
                                    arrStochasticMain[2] >= arrStochasticSignal[2]; // Main was above or equal to Signal on bar before

   // 3. Bollinger Band Upper Touch/Near
   bool bb_condition_sell = High[1] >= arrBBUpper[1];

   // 4. Pivot Point Resistance Reaction
   double identifiedPivot_sell = 0;
   bool pivot_raw_hit_sell = IsPriceNearPivot(High[1], identifiedPivot_sell);
   bool pivot_is_resistance = (identifiedPivot_sell == pivot_PP || identifiedPivot_sell == pivot_R1 || identifiedPivot_sell == pivot_R2 || identifiedPivot_sell == pivot_R3);
   bool pivot_condition_sell = pivot_raw_hit_sell && pivot_is_resistance;

   bool coreSignal = rsi_condition_sell && stochastic_condition_sell && bb_condition_sell && pivot_condition_sell;

   if (!coreSignal) return false;

   if(coreSignal) // For clarity in logs
     {
      Print("Core Reversal Sell Conditions Met: RSI=", rsi_condition_sell, ", Stoch=", stochastic_condition_sell, ", BB=", bb_condition_sell, ", Pivot=", pivot_condition_sell, " (Level: ", identifiedPivot_sell, ")");
     }

   // Secondary Confirmations
   if (inpEnableVolumeConfirmation)
     {
      if (inpVolumeLookbackPeriod + 1 >= ArraySize(arrVolume) || ArraySize(arrVolume) < inpVolumeLookbackPeriod + 2)
         { Print("Not enough volume data for average. ArraySize: ", ArraySize(arrVolume), " Needed for lookback+signal: ", inpVolumeLookbackPeriod + 2); return false;}

      double avgVolume = 0;
      for (int i = 1; i <= inpVolumeLookbackPeriod; i++)
        {
         avgVolume += arrVolume[i + 1];
        }
      avgVolume /= inpVolumeLookbackPeriod;

      if (arrVolume[1] < avgVolume * inpVolumeMultiplier)
        {
         Print("Volume confirmation FAILED for Sell. Signal Bar Volume: ", arrVolume[1], " Avg Volume: ", avgVolume, " Required Multiplier: ", inpVolumeMultiplier);
         return false;
        }
      Print("Volume confirmation PASSED for Sell. Signal Bar Volume: ", arrVolume[1], " Avg Volume: ", avgVolume);
     }

   if (inpEnableMACDConfirmation)
     {
      if(ArraySize(arrMACDMain) < 3 || ArraySize(arrMACDSignal) < 3) { Print("Not enough MACD data for confirmation."); return false; }

      bool macd_sell_cross = arrMACDMain[1] < arrMACDSignal[1] && arrMACDMain[2] >= arrMACDSignal[2];
      if (!macd_sell_cross)
        {
         Print("MACD confirmation FAILED for Sell. Main[1]:", arrMACDMain[1], " Sig[1]:", arrMACDSignal[1], " Main[2]:", arrMACDMain[2], " Sig[2]:", arrMACDSignal[2]);
         return false;
        }
      Print("MACD confirmation PASSED for Sell.");
     }
   return true; // Core signal AND enabled confirmations are true
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
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   trade.SetExpertMagicNumber(inpMagicNumber);
   trade.SetDeviationInPoints(5); // Or make this an input parameter

   double stopLossValue = 0;
   double takeProfitValue = 0;

   if (inpSLTPMode == MODE_ATR)
     {
      if (ArraySize(arrATR) < 1 || arrATR[1] <= 0) // Check if ATR value is valid (use index 1 for last closed bar)
        {
         Print("ATR value not available or invalid for SL/TP calculation (ATR[1]=", arrATR[1],"). Defaulting to Pips mode for this trade.");
         stopLossValue = inpStopLossPips * point;
         takeProfitValue = inpTakeProfitPips * point;
        }
      else
        {
         stopLossValue = arrATR[1] * inpATRMultiplierSL;
         takeProfitValue = arrATR[1] * inpATRMultiplierTP;
         Print("ATR SL/TP distances calculated: SL=", NormalizeDouble(stopLossValue/point,1)," pips, TP=", NormalizeDouble(takeProfitValue/point,1)," pips. ATR val on bar [1]: ", arrATR[1]);
        }
     }
   else // MODE_PIPS
     {
      stopLossValue = inpStopLossPips * point;
      takeProfitValue = inpTakeProfitPips * point;
      Print("Pips SL/TP distances: SL=", inpStopLossPips," pips, TP=", inpTakeProfitPips," pips.");
     }

   double currentPriceAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double currentPriceBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(orderType == ORDER_TYPE_BUY)
     {
      price = currentPriceAsk; // Buy orders filled at Ask
      if (inpStopLossPips > 0 || (inpSLTPMode == MODE_ATR && inpATRMultiplierSL > 0))
         sl = currentPriceBid - stopLossValue; // SL for Buy relative to Bid
      if (inpTakeProfitPips > 0 || (inpSLTPMode == MODE_ATR && inpATRMultiplierTP > 0))
         tp = currentPriceBid + takeProfitValue; // TP for Buy relative to Bid
      comment = "Buy Order by EA";
     }
   else // ORDER_TYPE_SELL
     {
      price = currentPriceBid; // Sell orders filled at Bid
      if (inpStopLossPips > 0 || (inpSLTPMode == MODE_ATR && inpATRMultiplierSL > 0))
         sl = currentPriceAsk + stopLossValue; // SL for Sell relative to Ask
      if (inpTakeProfitPips > 0 || (inpSLTPMode == MODE_ATR && inpATRMultiplierTP > 0))
         tp = currentPriceAsk - takeProfitValue; // TP for Sell relative to Ask
      comment = "Sell Order by EA";
     }

   // Adjust SL and TP to be valid if they are too close to the market
   // CTrade class handles this internally when placing orders, but good to be aware
   // For example, if sl or tp is 0, CTrade won't set it.
   // If sl or tp is too close, CTrade might adjust or fail.
   // The logic below for adjusting SL/TP if too close is now effectively handled by CTrade.
   // We can remove the manual adjustment here if we rely on CTrade's behavior.
   // Let's keep the manual adjustment for clarity and control.
   double stopLevelPips = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      double stopLevelPoints = stopLevelPips * point;

   if(orderType == ORDER_TYPE_BUY)
     {
      // For BUY: sl must be less than price - stopLevelPoints, tp must be greater than price + stopLevelPoints
      if(sl != 0.0 && price - sl < stopLevelPoints)
        {
         Print("SL for BUY order (", NormalizeDouble(sl, _Digits), ") too close to price (", NormalizeDouble(price, _Digits), "). Adjusting. Min distance: ", stopLevelPoints/point, " pips.");
         sl = price - stopLevelPoints; // price here is Ask
        }
      if(tp != 0.0 && tp - price < stopLevelPoints)
        {
         Print("TP for BUY order (", NormalizeDouble(tp, _Digits), ") too close to price (", NormalizeDouble(price, _Digits), "). Adjusting. Min distance: ", stopLevelPoints/point, " pips.");
         tp = price + stopLevelPoints;
        }

      if(!trade.Buy(lot, _Symbol, price, sl, tp, comment))
        {
         Print("Buy order failed: ", trade.ResultRetcode(), " - ", trade.ResultComment(), ". SL: ", sl, " TP: ", tp, " Price: ", price);
        }
      else
        {
         Print("Buy order placed successfully. Ticket: ", trade.ResultOrder(), ". SL: ", sl, " TP: ", tp);
        }
     }
   else if(orderType == ORDER_TYPE_SELL)
     {
      // For SELL: sl must be greater than price + stopLevelPoints, tp must be less than price - stopLevelPoints
      if(sl != 0.0 && sl - price < stopLevelPoints)
        {
         Print("SL for SELL order (", NormalizeDouble(sl, _Digits), ") too close to price (", NormalizeDouble(price, _Digits), "). Adjusting. Min distance: ", stopLevelPoints/point, " pips.");
         sl = price + stopLevelPoints; // price here is Bid
        }
      if(tp != 0.0 && price - tp < stopLevelPoints)
        {
         Print("TP for SELL order (", NormalizeDouble(tp, _Digits), ") too close to price (", NormalizeDouble(price, _Digits), "). Adjusting. Min distance: ", stopLevelPoints/point, " pips.");
         tp = price - stopLevelPoints;
        }

      if(!trade.Sell(lot, _Symbol, price, sl, tp, comment))
        {
         Print("Sell order failed: ", trade.ResultRetcode(), " - ", trade.ResultComment(), ". SL: ", sl, " TP: ", tp, " Price: ", price);
        }
      else
        {
         Print("Sell order placed successfully. Ticket: ", trade.ResultOrder(), ". SL: ", sl, " TP: ", tp);
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
                     if (currentPrice - newSL < stopLevelPoints && stopLevelPoints > 0) // check stopLevelPoints > 0 to avoid issues on some symbols
                       {
                        newSL = currentPrice - stopLevelPoints;
                        Print("Trailing SL for BUY (ticket: ", ticket, ") adjusted to avoid being too close. New SL: ", NormalizeDouble(newSL, _Digits));
                       }

                     if(newSL != currentSL) // Check if modification is actually needed
                       {
                        if(trade.PositionModify(ticket, newSL, currentTP))
                          {
                           Print("Trailing stop for BUY position ", ticket, " modified. New SL: ", NormalizeDouble(newSL, _Digits));
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
                     if (newSL - currentPrice < stopLevelPoints && stopLevelPoints > 0) // check stopLevelPoints > 0
                       {
                        newSL = currentPrice + stopLevelPoints;
                        Print("Trailing SL for SELL (ticket: ", ticket, ") adjusted to avoid being too close. New SL: ", NormalizeDouble(newSL, _Digits));
                       }

                     if(newSL != currentSL) // Check if modification is actually needed
                       {
                        if(trade.PositionModify(ticket, newSL, currentTP))
                          {
                           Print("Trailing stop for SELL position ", ticket, " modified. New SL: ", NormalizeDouble(newSL, _Digits));
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
//| Calculate Daily Pivot Points                                     |
//+------------------------------------------------------------------+
void CalculateDailyPivotPoints(ENUM_TIMEFRAMES pivot_timeframe = PERIOD_D1)
  {
   datetime prev_day_bar_time = iTime(_Symbol, pivot_timeframe, 1); // Time of the previous D1 bar
   if(prev_day_bar_time == 0 && Bars(_Symbol, pivot_timeframe) < 2) // Not enough history
     {
      Print("Cannot calculate Pivot Points: Not enough history for timeframe ", EnumToString(pivot_timeframe));
      return;
     }

   double prev_high = iHigh(_Symbol, pivot_timeframe, 1);
   double prev_low = iLow(_Symbol, pivot_timeframe, 1);
   double prev_close = iClose(_Symbol, pivot_timeframe, 1);

   if(prev_high == 0 || prev_low == 0 || prev_close == 0) // Should not happen if prev_day_bar_time is valid
     {
      Print("Cannot calculate Pivot Points: Data for previous bar is zero. High: ", prev_high, " Low: ", prev_low, " Close: ", prev_close);
      return;
     }

   pivot_PP = (prev_high + prev_low + prev_close) / 3.0;
   pivot_R1 = (2.0 * pivot_PP) - prev_low;
   pivot_S1 = (2.0 * pivot_PP) - prev_high;
   pivot_R2 = pivot_PP + (prev_high - prev_low);
   pivot_S2 = pivot_PP - (prev_high - prev_low);
   pivot_R3 = prev_high + 2.0 * (pivot_PP - prev_low);
   pivot_S3 = prev_low - 2.0 * (prev_high - pivot_PP);

   // Storing the open time of the D1 bar for which these pivots are calculated (i.e., the previous D1 bar)
   // lastPivotRecalcTime will store the open time of the *current* D1 bar when this function is called
   // This means pivot_DayCalculated isn't strictly needed if lastPivotRecalcTime is used correctly.

   Print("Pivot Points Calculated using data from D1 bar @ ", TimeToString(prev_day_bar_time),": PP=",NormalizeDouble(pivot_PP,_Digits), ", S1=",NormalizeDouble(pivot_S1,_Digits),", R1=",NormalizeDouble(pivot_R1,_Digits));
   // Print("S2=",NormalizeDouble(pivot_S2,_Digits),", R2=",NormalizeDouble(pivot_R2,_Digits), ", S3=",NormalizeDouble(pivot_S3,_Digits),", R3=",NormalizeDouble(pivot_R3,_Digits));
  }
//+------------------------------------------------------------------+
//| Check if Price is Near a Pivot Level                             |
//+------------------------------------------------------------------+
bool IsPriceNearPivot(double price, double& identifiedPivotLevel)
  {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double buffer = inpPivotPointBufferPips * point;

   if(MathAbs(price - pivot_PP) <= buffer) { identifiedPivotLevel = pivot_PP; return true; }
   if(MathAbs(price - pivot_S1) <= buffer) { identifiedPivotLevel = pivot_S1; return true; }
   if(MathAbs(price - pivot_R1) <= buffer) { identifiedPivotLevel = pivot_R1; return true; }
   if(MathAbs(price - pivot_S2) <= buffer) { identifiedPivotLevel = pivot_S2; return true; }
   if(MathAbs(price - pivot_R2) <= buffer) { identifiedPivotLevel = pivot_R2; return true; }
   if(MathAbs(price - pivot_S3) <= buffer) { identifiedPivotLevel = pivot_S3; return true; }
   if(MathAbs(price - pivot_R3) <= buffer) { identifiedPivotLevel = pivot_R3; return true; }

   identifiedPivotLevel = 0.0;
   return false;
  }
//+------------------------------------------------------------------+
