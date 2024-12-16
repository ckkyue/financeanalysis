// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © kelvinyue37

//@version=6
indicator(title = 'ADX & MFI', shorttitle = 'ADX MFI', overlay = false)

// Inputs
// Periods
adxPeriod = input.int(title = 'ADX Period', defval = 14, minval = 1, group = 'ADX & MFI')
mfiPeriod = input.int(title = 'MFI Period', defval = 14, minval = 1, group = 'ADX & MFI')
zScorePeriod = input.int(title = 'Z-Score Period', defval = 252, minval = 1, group = 'ADX & MFI')

// Calculate the +DM and -DM
plusDM = na(high[1]) ? 0 : (high - high[1] > low[1] - low and high - high[1] > 0 ? high - high[1] : 0)
minusDM = na(low[1]) ? 0 : (low[1] - low > high - high[1] and low[1] - low > 0 ? low[1] - low : 0)

// Calculate the +DI and -DI by EMA of +DM and -DM, divided by ATR
plusDI = ta.ema(plusDM, adxPeriod) / ta.atr(adxPeriod) * 100
minusDI = ta.ema(minusDM, adxPeriod) / ta.atr(adxPeriod) * 100

// Calculate the DX
dx = na(plusDI + minusDI) ? na : math.abs(plusDI - minusDI) / (plusDI + minusDI) * 100

// Calculate the ADX
adx = ta.ema(dx, adxPeriod)

// Plot the ADX
plot(adx, title = 'ADX', color = color.orange)

// Calculate the HLC3, Raw MF, and the change of HLC3
hlc3 = (high + low + close) / 3
rawMF = hlc3 * volume
hlc3Change = hlc3 - hlc3[1]

// Calculate the +MF and -MF
plusMF = hlc3[1] < hlc3 ? rawMF : 0
minusMF = hlc3[1] > hlc3 ? rawMF : 0

// Calculate the sum of +MF and -MF over a period
plusMFSum = math.sum(plusMF, mfiPeriod)
minusMFSum = math.sum(minusMF, mfiPeriod)

// Calculate the MF Ratio with division by zero check
mfRatio = minusMFSum != 0 ? plusMFSum / math.abs(minusMFSum) : 0

// Calculate the MFI
mfi = 100 - (100 / (1 + mfRatio))

// Plot the MFI
plot(mfi, title = 'MFI', color=color.blue)
hline(80, title = 'Overbought', color=color.red)
hline(50, color=color.black)
hline(20, title = 'Oversold', color=color.red)

// Calculate rolling z-scores
adxMean = bar_index < zScorePeriod ? ta.sma(adx, bar_index + 1) : ta.sma(adx, zScorePeriod)
adxStdDev = bar_index < zScorePeriod ? ta.stdev(adx, bar_index + 1) : ta.stdev(adx, zScorePeriod)
adxZScore = na(adxStdDev) ? na : (adx - adxMean) / adxStdDev

mfiMean = bar_index < zScorePeriod ? ta.sma(mfi, bar_index + 1) : ta.sma(mfi, zScorePeriod)
mfiStdDev = bar_index < zScorePeriod ? ta.stdev(mfi, bar_index + 1) : ta.stdev(mfi, zScorePeriod)
mfiZScore = na(mfiStdDev) ? na : (mfi - mfiMean) / mfiStdDev

// Display the most recent z-scores as labels on the plot
if bar_index == last_bar_index
    // Determine y-coordinates based on the condition
    adxY = adx < mfi ? 30 : 60
    mfiY = adx < mfi ? 60 : 30

    // Add "#" only if using fewer data points
    adxLabelText = bar_index < zScorePeriod ? "#" + str.tostring(adxZScore, "#.##") + "σ" : str.tostring(adxZScore, "#.##") + "σ"
    mfiLabelText = bar_index < zScorePeriod ? "#" + str.tostring(mfiZScore, "#.##") + "σ" : str.tostring(mfiZScore, "#.##") + "σ"

    // Create labels
    label.new(bar_index + 7, adxY, text = adxLabelText, color=color.orange, style=label.style_label_down, size=size.small, textcolor=color.white, yloc=yloc.price)
    label.new(bar_index + 7, mfiY, text = mfiLabelText, color=color.blue, style=label.style_label_down, size=size.small, textcolor=color.white, yloc=yloc.price)