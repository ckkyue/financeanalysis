// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © kelvinyue37

//@version=6
indicator(title='Momentum All-in-One', shorttitle='Momentum All-in-One', overlay=false)

// Input parameters
// Moving Averages settings
ma1Length = input.int(title='MA 1 Length', defval=5, minval=1, group='Moving Averages')
ma1Type = input.string(title='MA 1 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')
ma2Length = input.int(title='MA 2 Length', defval=10, minval=1, group='Moving Averages')
ma2Type = input.string(title='MA 2 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')
ma3Length = input.int(title='MA 3 Length', defval=20, minval=1, group='Moving Averages')
ma3Type = input.string(title='MA 3 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')
ma4Length = input.int(title='MA 4 Length', defval=50, minval=1, group='Moving Averages')
ma4Type = input.string(title='MA 4 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')
ma5Length = input.int(title='MA 5 Length', defval=100, minval=1, group='Moving Averages')
ma5Type = input.string(title='MA 5 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')
ma6Length = input.int(title='MA 6 Length', defval=200, minval=1, group='Moving Averages')
ma6Type = input.string(title='MA 6 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')
ma7Length = input.int(title='MA 7 Length', defval=15, minval=1, group='Moving Averages')
ma7Type = input.string(title='MA 7 Type', defval='SMA', options=['SMA', 'EMA', 'VWMA'], group='Moving Averages')

// Colors for moving averages
ma1Color = color.orange
ma2Color = color.aqua
ma3Color = color.fuchsia
ma4Color = color.blue
ma5Color = color.lime
ma6Color = color.yellow
ma7Color = color.rgb(255, 69, 0)

// Function to calculate the moving average
getMovingAverage(src, length, maType) =>
    if maType == "SMA"
        ta.sma(src, length)
    else if maType == "EMA"
        ta.ema(src, length)
    else if maType == "VWMA"
        ta.vwma(src, length)
    
// Calculate and plot moving averages
closeMa1 = getMovingAverage(close, ma1Length, ma1Type)
plot(closeMa1, color=ma1Color, title='MA 1', force_overlay =true)

closeMa2 = getMovingAverage(close, ma2Length, ma2Type)
plot(closeMa2, color=ma2Color, title='MA 2', force_overlay = true)

closeMa3 = getMovingAverage(close, ma3Length, ma3Type)
plot(closeMa3, color=ma3Color, title='MA 3', force_overlay = true)

closeMa4 = getMovingAverage(close, ma4Length, ma4Type)
plot(closeMa4, color=ma4Color, title='MA 4', force_overlay = true)

closeMa5 = getMovingAverage(close, ma5Length, ma5Type)
plot(closeMa5, color=ma5Color, title='MA 5', force_overlay = true)

closeMa6 = getMovingAverage(close, ma6Length, ma6Type)
plot(closeMa6, color=ma6Color, title='MA 6', force_overlay = true)

closeMa7 = getMovingAverage(close, ma7Length, ma7Type)
plot(closeMa7, color=ma7Color, title='MA 7', force_overlay = true)

// MVP and VCP settings
mvpPeriod = input.int(title="MVP Period", defval=15, minval=1, group='MVP & VCP')
vcpPeriod = input.int(title="VCP Period", defval=10, minval=1, group='MVP & VCP')
contractionLimit = input.float(title="Contraction", defval=0.05, minval=0.01, group='MVP & VCP')

// Calculate M condition
greater = close > close[1] ? 1 : 0
smaller = close < close[1] ? 1 : 0
mSum = math.sum(greater, mvpPeriod)
revMSum = math.sum(smaller, mvpPeriod)
isM = mSum >= (mvpPeriod * 0.8)
isRevM = revMSum >= (mvpPeriod * 0.8)

// Calculate V condition
isV = volume >= volume[mvpPeriod] * 1.2

// Calculate P condition
isP = close >= close[mvpPeriod] * 1.2
isRevP = close < close[mvpPeriod] * 1.2

// Initialize MVP label
var string mvpLabel = na

// Define MVP labels based on conditions
if isM and not isV and not isP
    mvpLabel := "M"
else if isM and isV and not isP
    mvpLabel := "MV"
else if isM and isP and not isV
    mvpLabel := "MP"
else if isM and isV and isP
    mvpLabel := "MVP"
else 
    mvpLabel := na

// Plot MVP conditions
plotshape(mvpLabel == "M", title='M', style=shape.triangleup, location=location.abovebar, color=color.gray, size=size.tiny, force_overlay = true)
plotshape(mvpLabel == "MV", title='MV', style=shape.triangleup, location=location.abovebar, color=color.blue, size=size.tiny, force_overlay = true)
plotshape(mvpLabel == "MP", title='MP', style=shape.triangleup, location=location.abovebar, color=color.yellow, size=size.tiny, force_overlay = true)
plotshape(mvpLabel == "MVP", title='MVP', style=shape.triangleup, location=location.abovebar, color=color.green, size=size.tiny, force_overlay = true)

// Calculate VCP condition
highestClose = ta.highest(close, vcpPeriod)
lowestClose = ta.lowest(close, vcpPeriod)
isVCP = na(highestClose) or na(lowestClose) or highestClose == 0 ? false : (1 - lowestClose / highestClose) <= contractionLimit

// Plot VCP condition
plotchar(isVCP, title="VCP", char=">", location=location.abovebar, color=color.orange, size=size.tiny, force_overlay = true)

// FTD & DD settings
ftdThreshold = input.float(title='FTD Threshold (%)', defval=1.5, minval=0.1, group='FTD & DD') / 100
ddThreshold = input.float(title='DD Threshold (%)', defval=0.2, minval=0.1, group='FTD & DD') / 100
volumePeriod = input.int(title='Volume Period', defval=50, minval=1, group='FTD & DD')
ftdDdPeriod = input.int(title='FTD/DD Period', defval=20, minval=1, group='FTD & DD')

// Calculate volume moving average
volumeMA = ta.sma(volume, volumePeriod)

// Exhaustion detection settings
exhaustionPricePeriod = input.int(title='Exhaustion Price Period', defval=20, minval=1, group='Exhaustion')
exhaustionSdThreshold = input.float(title='Exhaustion SD Threshold', defval=1.0, minval=0.1, group='Exhaustion')

// Calculate percent change
percentChange = ta.change(close) / close[1]

// Calculate rolling mean and standard deviation of percent change
percentChangeMean = ta.sma(percentChange, exhaustionPricePeriod)
percentChangeStd = ta.stdev(percentChange, exhaustionPricePeriod)

// Calculate percent change z-score
percentChangeZScore = percentChangeStd != 0 ? (percentChange - percentChangeMean) / percentChangeStd : 0

// Calculate exhaustion volume moving average
exhaustionVolumeMA = ta.sma(volume, volumePeriod)

// Detect exhaustion days
isExhaustion = volume > exhaustionVolumeMA and percentChangeZScore > exhaustionSdThreshold

// Plot exhaustion as inverted dark green triangle
plotshape(isExhaustion, title='Exhaustion', style=shape.triangledown, location=location.abovebar, color=color.rgb(0, 100, 0), size=size.small, force_overlay=true)

// Calculate FTD (Follow-Through Day)
isFTD = close > close[1] * (1 + ftdThreshold) and volume > volume[1] and volume > volumeMA

// Calculate DD (Distribution Day)
isDD = close < close[1] * (1 - ddThreshold) and volume > volume[1] and volume > volumeMA

// Calculate rolling sums for multiple FTDs and DDs
ftdSum = math.sum(isFTD ? 1 : 0, ftdDdPeriod)
ddSum = math.sum(isDD ? 1 : 0, ftdDdPeriod)

// Check for multiple FTDs and DDs
multipleFTDs = ftdSum >= 4 and isFTD
multipleDDs = ddSum >= 4 and isDD

// Plot FTD and DD
plotshape(isFTD and not multipleFTDs, title='FTD', style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small, force_overlay=true)
plotshape(isDD and not multipleDDs, title='DD', style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small, force_overlay=true)

// Plot shapes for multiple FTDs and DDs
plotshape(multipleFTDs, title='Multiple FTDs', style=shape.diamond, location=location.belowbar, color=color.green, size=size.small, force_overlay=true)
plotshape(multipleDDs, title='Multiple DDs', style=shape.diamond, location=location.abovebar, color=color.red, size=size.small, force_overlay=true)

// MMFI & MFI settings
mfiPeriod = input.int(title='MFI Period', defval=14, minval=1, group='MMFI & MFI')
zScorePeriod = input.int(title='Z-Score Period', defval=252, minval=1, group='MMFI & MFI')

// Get MMFI data - only if timeframe is daily or above
mmfiClose = timeframe.isdaily or timeframe.isweekly or timeframe.ismonthly ? request.security("MMFI", timeframe.period, close) : na

// Plot MMFI - only if data is available
showMMFI = not na(mmfiClose)
plot(showMMFI ? mmfiClose : na, title='MMFI', color=color.orange)

// Calculate raw MF, and change of HLC3
rawMF = hlc3 * volume
hlc3Change = hlc3 - hlc3[1]

// Calculate +MF and -MF
plusMF = hlc3[1] < hlc3 ? rawMF : 0
minusMF = hlc3[1] > hlc3 ? rawMF : 0

// Calculate sum of +MF and -MF over a period
plusMFSum = math.sum(plusMF, mfiPeriod)
minusMFSum = math.sum(minusMF, mfiPeriod)

// Calculate MF Ratio with division by zero check
mfRatio = minusMFSum != 0 ? plusMFSum / math.abs(minusMFSum) : 0

// Calculate MFI
mfi = 100 - (100 / (1 + mfRatio))

// Plot the MFI
plot(mfi, title='MFI', color=color.blue)
hline(80, title='Overbought', color=color.red)
hline(50, color=color.black)
hline(20, title='Oversold', color=color.red)

// Calculate rolling z-scores
mmfiMean = showMMFI ? (bar_index < zScorePeriod ? ta.sma(mmfiClose, bar_index + 1) : ta.sma(mmfiClose, zScorePeriod)) : na
mmfiStdDev = showMMFI ? (bar_index < zScorePeriod ? ta.stdev(mmfiClose, bar_index + 1) : ta.stdev(mmfiClose, zScorePeriod)) : na
mmfiZScore = na(mmfiStdDev) ? na : (mmfiClose - mmfiMean) / mmfiStdDev

mfiMean = bar_index < zScorePeriod ? ta.sma(mfi, bar_index + 1) : ta.sma(mfi, zScorePeriod)
mfiStdDev = bar_index < zScorePeriod ? ta.stdev(mfi, bar_index + 1) : ta.stdev(mfi, zScorePeriod)
mfiZScore = na(mfiStdDev) ? na : (mfi - mfiMean) / mfiStdDev

// Display the most recent z-scores as labels on the plot
if bar_index == last_bar_index
    // Determine y-coordinates based on the condition
    mmfiY = showMMFI ? (mmfiClose < mfi ? 25 : 55) : na
    mfiY = showMMFI ? (mmfiClose < mfi ? 55 : 25) : 55

    // Add "#" only if using fewer data points
    mmfiLabelText = showMMFI ? (bar_index < zScorePeriod ? "#" + "MMFI: " + str.tostring(mmfiZScore, "#.##") + "σ" : "MMFI: " + str.tostring(mmfiZScore, "#.##") + "σ") : na
    mfiLabelText = bar_index < zScorePeriod ? "#" + "MFI: " + str.tostring(mfiZScore, "#.##") + "σ" : "MFI: " + str.tostring(mfiZScore, "#.##") + "σ"

    // Create labels
    if showMMFI
        label.new(bar_index + 8, mmfiY, text=mmfiLabelText, color=color.orange, style=label.style_label_down, size=size.small, textcolor=color.white, yloc=yloc.price)
    label.new(bar_index + 8, mfiY, text=mfiLabelText, color=color.blue, style=label.style_label_down, size=size.small, textcolor=color.white, yloc=yloc.price)