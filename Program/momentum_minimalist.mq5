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

// Function: Calculate Moving Averages
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
period_mom_long = input.int(252, "Long-Term Momentum Lookback (Days)", minval=21, group="Volatility-Adjusted Momentum")
period_mom_short = input.int(21, "Short-Term Momentum Lookback (Days)", minval=1, group="Volatility-Adjusted Momentum")
period_vol = input.int(60, "Volatility Lookback (Days)", minval=1, group="Volatility-Adjusted Momentum")

// 252-21 Momentum
mom = (close[period_mom_short - 1] / close[period_mom_long - 1]) - 1.0

// 60-Day Volatility
daily_ret = close / close[1] - 1.0
vol = ta.stdev(daily_ret, period_vol)
vol_adj_mom = vol != 0 ? mom / vol : na

// Weekly Return Z-Score Inputs
period_week_zscore = input.int(52, "Z-Score Lookback (Weeks)", minval=2, group="Weekly Return Z-Score")
days_per_week = input.int(5, "Days Per Week", minval=1, group="Weekly Return Z-Score")

// Function: Compute "Weekly" Z-Score Using Rolling 5-Day Sampling
calc_weekly_zscore(_period, _days) =>
    // How many daily bars we need
    lookback = _period * _days + _days

    // Store prices
    var float[] prices = array.new_float()

    // Clear array on each bar
    array.clear(prices)

    // Sample backward from most recent bar
    for i = 0 to lookback by _days
        if not na(close[i])
            array.push(prices, close[i])

    // Reverse to chronological order (oldest -> newest)
    array.reverse(prices)

    // Compute returns
    var float[] returns = array.new_float()
    array.clear(returns)

    sz = array.size(prices)

    if sz > 1
        for i = 1 to sz - 1
            p0 = array.get(prices, i - 1)
            p1 = array.get(prices, i)
            ret = (p1 / p0) - 1.0
            array.push(returns, ret)

    // Keep only last _period returns
    while array.size(returns) > _period
        array.shift(returns)

    // Compute mean
    float mean = 0.0
    int n = array.size(returns)

    if n > 0
        for i = 0 to n - 1
            mean += array.get(returns, i)
        mean := mean / n

    // Compute standard deviation
    float variance = 0.0

    if n > 1
        for i = 0 to n - 1
            diff = array.get(returns, i) - mean
            variance += diff * diff
        variance := variance / (n - 1)
    std = math.sqrt(variance)

    // Most recent return
    recent_ret = n > 0 ? array.get(returns, n - 1) : na

    // Z-score
    z = (std != 0 and not na(recent_ret)) ? (recent_ret - mean) / std : 0.0
    z

// Compute Z-Score
week_zscore = calc_weekly_zscore(period_week_zscore, days_per_week)

// Display Summary Table
var table board = table.new(position.top_right, 2, 4, bgcolor=color.new(color.black, 5), border_width=1)
if barstate.islast
    // Regime Status (MMTH)
    table.cell(board, 0, 0, "MMTH", text_color=color.white)
    table.cell(board, 1, 0, str.tostring(mmth, "#.##"), text_color = mmth < 50 ? color.red : color.green)

    // Volatility-Adjusted Momentum
    table.cell(board, 0, 1, "R₂₅₂₋₂₁/σ₆₀", text_color=color.white)
    table.cell(board, 1, 1, str.tostring(mom, "#.##") + "/" + str.tostring(vol, "#.###") + "=" + str.tostring(vol_adj_mom, "#.##"), text_color=color.aqua)

    // Outlier Detection (Weekly Z-Score)
    table.cell(board, 0, 2, "Weekly Z-Score", text_color=color.white)
    table.cell(board, 1, 2, str.tostring(week_zscore, "#.##") + "σ", text_color = week_zscore > 2.0 or week_zscore < -2.0 ? color.red : color.green)

    // Uptrend Check
    table.cell(board, 0, 3, "Uptrend Check", text_color=color.white)
    table.cell(board, 1, 3, is_uptrend ? "PASSED" : "FAILED", text_color = is_uptrend ? color.green : color.red)