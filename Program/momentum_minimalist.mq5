// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © kelvinyue37

//@version=6
indicator(title="Momentum Minimalist", shorttitle="MM", overlay=false)

// Moving Averages Inputs
ma1Length = input.int(title="Short-Term MA Length", defval=50, minval=1, group="Moving Averages")
ma1Type = input.string(title="Short-Term MA Type", defval="SMA", options=["SMA", "EMA", "VWMA"], group="Moving Averages")
ma2Length = input.int(title="Long-Term MA Length", defval=200, minval=1, group="Moving Averages")
ma2Type = input.string(title="Long-Term MA Type", defval="SMA", options=["SMA", "EMA", "VWMA"], group="Moving Averages")
ma1Color = color.blue
ma2Color = color.yellow

// Function to Calculate Moving Averages
getMovingAverage(src, length, maType) =>
    switch maType
        "SMA"  => ta.sma(src, length)
        "EMA"  => ta.ema(src, length)
        "VWMA" => ta.vwma(src, length)
        => ta.sma(src, length)

// Plot Moving Averages
closeMa1 = getMovingAverage(close, ma1Length, ma1Type)
plot(closeMa1, color=ma1Color, force_overlay=true)
closeMa2 = getMovingAverage(close, ma2Length, ma2Type)
plot(closeMa2, color=ma2Color, force_overlay=true)

// Uptrend Verification
ma2_up = closeMa2 > closeMa2[1]
is_uptrend = close > closeMa1 and close > closeMa2 and closeMa1 > closeMa2 and ma2_up

// Market Breadth Indicators
// MMTH: Regime Filter (% Stocks > 200 SMA).
// MMFI: Oversold Trigger (% Stocks > 50 SMA).
mmth = request.security("MMTH", timeframe.period, close)
mmfi = request.security("MMFI", timeframe.period, close)

// Plot Market Breadth Indicators
plot(mmth, title="MMTH", color = mmth < 50 ? color.red : color.green, linewidth=2)
plot(mmfi, title="MMFI", color=color.blue, linewidth=1)

// Reference Lines
hline(50, color=color.gray, linestyle=hline.style_dashed)
hline(10, color=color.red, linewidth=2)

// Background Colour for Bear Market
bgcolor(mmth < 50 ? color.new(color.red, 50) : na)

// Volatility-Adjusted Momentum Inputs
period_mom_long = 252
period_mom_short = 21
period_vol = 60

// 252-21 Day Return
ret_252_21 = (close[period_mom_short] / close[period_mom_long]) - 1.0

// 60-Day Volatility
daily_ret = close / close[1] - 1.0
vol = ta.stdev(daily_ret, period_vol)
vol_adj_mom = vol != 0 ? ret_252_21 / vol : na

// Weekly Z-Score Inputs
period_week_zscore = input.int(52, "Lookback Period (Weeks)", minval=2, group="Outlier Detection")

// Function to Calculate Weekly Z-Score
calc_weekly_stats() =>
    // Calculate Weekly Return
    weekly_ret = (close / close[1]) - 1.0
    
    // Compute Mean and Standard Deviation
    mean_ret = ta.sma(weekly_ret, period_week_zscore)
    std_ret  = ta.stdev(weekly_ret, period_week_zscore)
    
    // Compute Current Z-Score
    z = std_ret != 0 ? (weekly_ret - mean_ret) / std_ret : 0.0
    z

// Get Weekly Z-Score
week_zscore = request.security(syminfo.tickerid, "W", calc_weekly_stats())

// Display Summary Table
var table board = table.new(position.top_right, 2, 4, bgcolor=color.new(color.black, 5), border_width=1)
if barstate.islast
    // Regime Status (MMTH)
    table.cell(board, 0, 0, "MMTH", text_color=color.white)
    table.cell(board, 1, 0, str.tostring(mmth, "#.##"), text_color = mmth < 50 ? color.red : color.green)

    // Volatility-Adjusted Momentum (R/σ)
    table.cell(board, 0, 1, "R/σ", text_color=color.white)
    table.cell(board, 1, 1, str.tostring(vol_adj_mom, "#.##"), text_color=color.aqua)

    // Outlier Detection (Weekly Z-Score)
    table.cell(board, 0, 2, "Weekly Z-Score", text_color=color.white)
    table.cell(board, 1, 2, str.tostring(week_zscore, "#.##") + "σ", text_color = week_zscore > 2.0 ? color.red : color.green)

    // Uptrend Check
    table.cell(board, 0, 3, "Uptrend Check", text_color=color.white)
    table.cell(board, 1, 3, is_uptrend ? "PASSED" : "FAILED", text_color = is_uptrend ? color.green : color.red)