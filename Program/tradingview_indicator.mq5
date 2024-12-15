// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © kelvinyue37

//@version=6
indicator(title="Moving Averages and Volume", shorttitle="MA & Vol", overlay=false)

// Input for color customization
color ma1Color = color.orange
color ma2Color = color.aqua
color ma3Color = color.fuchsia
color ma4Color = color.blue
color ma5Color = color.lime
color ma6Color = color.yellow
color bullishColor = color.new(color.teal, 50)
color bearishColor = color.new(color.red, 50)
color volSmaColor = color.purple

// Input for Close MA length and type
ma1Length = input.int(title="MA Length 1", defval=5, minval=1)
ma1Type = input.string(title="MA Type 1", defval="SMA", options=["SMA", "EMA"])
ma2Length = input.int(title="MA Length 2", defval=10, minval=1)
ma2Type = input.string(title="MA Type 2", defval="SMA", options=["SMA", "EMA"])
ma3Length = input.int(title="MA Length 3", defval=20, minval=1)
ma3Type = input.string(title="MA Type 3", defval="SMA", options=["SMA", "EMA"])
ma4Length = input.int(title="MA Length 4", defval=50, minval=1)
ma4Type = input.string(title="MA Type 4", defval="SMA", options=["SMA", "EMA"])
ma5Length = input.int(title="MA Length 5", defval=100, minval=1)
ma5Type = input.string(title="MA Type 5", defval="SMA", options=["SMA", "EMA"])
ma6Length = input.int(title="MA Length 6", defval=200, minval=1)
ma6Type = input.string(title="MA Type 6", defval="SMA", options=["SMA", "EMA"])

// Function to calculate the moving average based on type
get_moving_average(src, length, maType) =>
    maType == "EMA" ? ta.ema(src, length) : ta.sma(src, length)

// Calculate and plot the MA of close
closeMa1 = get_moving_average(close, ma1Length, ma1Type)
plot(closeMa1, color=ma1Color, force_overlay = true)

closeMa2 = get_moving_average(close, ma2Length, ma2Type)
plot(closeMa2, color=ma2Color, force_overlay = true)

closeMa3 = get_moving_average(close, ma3Length, ma3Type)
plot(closeMa3, color=ma3Color, force_overlay = true)

closeMa4 = get_moving_average(close, ma4Length, ma4Type)
plot(closeMa4, color=ma4Color, force_overlay = true)

closeMa5 = get_moving_average(close, ma5Length, ma5Type)
plot(closeMa5, color=ma5Color, force_overlay = true)

closeMa6 = get_moving_average(close, ma6Length, ma6Type)
plot(closeMa6, color=ma6Color, force_overlay = true)

// Plot the volume
plot(volume, style=plot.style_columns, color=(close > open ? bullishColor : bearishColor), title="Volume")

// Calculate and plot the SMA of volume
volMaLength = input.int(title="Volume SMA Length", defval=50, minval=1)
volumeSma = ta.sma(volume, volMaLength)
plot(volumeSma, color=volSmaColor, title="Volume SMA")