// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © kelvinyue37

//@version=6
indicator(title = 'Momentum All-in-One', shorttitle = 'Earnings, ADX, MFI, MVP, VCP', overlay = true)

// Inputs
// Arrow Settings
i_ArrowOnGraph = input(true, title = 'Displays Arrows', inline = '1', group = 'Arrows')
i_ArrowQoq = input(false, title = 'Arrow QoQ', inline = '1', group = 'Arrows')
i_SalesOnGraph = input(false, title = 'Sales', inline = '1', group = 'Arrows')
i_ArrowSize = input.string('Small', title = 'Arrow Size', options = ['Tiny', 'Small', 'Normal', 'Large'], inline = '2', group = 'Arrows')
i_ArrowColor = input(color.black, title = 'Arrow Colors', inline = '3', group = 'Arrows')
i_PosArrowColor = input(color.blue, title = '+ve', inline = '3', group = 'Arrows')
i_NegArrowColor = input(color.red, title = '-ve', inline = '3', group = 'Arrows')

// Table Settings
i_TableSize = input.string('Normal', title = 'Table Size', options = ['Tiny', 'Small', 'Normal', 'Large'], group = 'Table Settings', inline = '4')
i_MarketSu = input.bool(true, title = 'MarketSurge Look', group = 'Table Settings', tooltip = 'Uncheck for customization')
i_PosTable = input.string(defval = position.bottom_left, title = 'Table Position', options = [position.top_left, position.top_center, position.top_right, position.middle_left, position.middle_center, position.middle_right, position.bottom_left, position.bottom_center, position.bottom_right], group = 'Table Settings', inline = '5', tooltip = 'Available in Weekly Table Only.')
i_FrameWidth = input.int(1, title = 'Frame Width', group = 'Table Settings', options = [0, 1, 2, 3, 4, 5], inline = '0.25')
i_FrameColor = input(color.black, title = 'Color', group = 'Table Settings', inline = '0.25')
i_TableBorder = input(true, title = 'Table Border', group = 'Table Settings', inline = '0.5')
i_BorderColor = input(color.black, title = '| Color', group = 'Table Settings', inline = '0.5')
i_ResultBackgroundColorOdd = input(color.silver, title = 'Odd Rows', group = 'Table Settings', inline = '6')
i_ResultBackgroundColorEven = input(color.white, title = 'Even Rows', group = 'Table Settings', inline = '6')

// Digit Settings
i_Estimates = input(true, title = 'Estimates', group = 'Digit Settings', tooltip = 'Available in Weekly Table Only.')
i_Compare = input(false, title = 'Show VS YoY', group = 'Digit Settings', inline = '2', tooltip = 'Available in Weekly Table Only.')
i_YoY = input(true, title = 'YoY', group = 'Digit Settings', inline = '2', tooltip = 'Available in Weekly Table Only.')
i_QoQ = input(false, title = 'QoQ', group = 'Digit Settings', inline = '2', tooltip = 'Available in Weekly Table Only.')
i_Surprises = input(false, title = '% Surprise', group = 'Digit Settings', inline = '3', tooltip = 'Available in Weekly Table Only.')
i_PosSurp = input(color.teal, title = '+ve', group = 'Digit Settings', inline = '3')
i_NegSurp = input(color.red, title = '-ve', group = 'Digit Settings', inline = '3')
i_GrossMargin = input(false, title = 'Gross Margin', group = 'Digit Settings', inline = '4')
i_ROE = input(false, title = 'Return On Equity', group = 'Digit Settings', inline = '4')
i_RowAndColumnTextColor = input(color.black, title = 'Row & Column Text Color', group = 'Digit Settings')
i_PosColor2 = input(color.blue, title = '% Positive', group = 'Digit Settings', inline = '8')
i_NegColor2 = input(color.red, title = '% Negative', group = 'Digit Settings', inline = '8')

// No input
datasize = 10

// Switch arrow Size
arrowSize = switch i_ArrowSize
    'Normal' => size.normal
    'Tiny' => size.tiny
    'Small' => size.small
    'Large' => size.large

// Switch table size
tableSize = switch i_TableSize
    'Normal' => size.normal
    'Tiny' => size.tiny
    'Small' => size.small
    'Large' => size.large

// New MarketSurge Look
if i_MarketSu
    i_FrameColor := color.black
    i_BorderColor := color.black
    i_ResultBackgroundColorOdd := color.rgb(231, 231, 231)
    i_ResultBackgroundColorEven := color.white
    i_ResultBackgroundColorEven

// Declare tables
// Weekly Table
var table epsTable = table.new(i_PosTable, 15, 15, frame_color = i_FrameColor, frame_width = i_FrameWidth, border_width = i_TableBorder ? 1 : 0, border_color = i_BorderColor)

// Calculations
// Current earnings per share (EPS)
EPS = request.earnings(syminfo.tickerid, earnings.actual, ignore_invalid_symbol = true, lookahead = barmerge.lookahead_on)
EPS_Standard = request.earnings(syminfo.tickerid, earnings.standardized, ignore_invalid_symbol = true, lookahead = barmerge.lookahead_on)
EPS_Estimate = request.earnings(syminfo.tickerid, earnings.estimate, ignore_invalid_symbol = true, lookahead = barmerge.lookahead_on)
SALES = request.financial(syminfo.tickerid, 'TOTAL_REVENUE', 'FQ', ignore_invalid_symbol = true)
SALES_Estimate = request.financial(syminfo.tickerid, 'SALES_ESTIMATES', 'FQ', ignore_invalid_symbol = true)
SALES_GROWTH = request.financial(syminfo.tickerid, 'REVENUE_ONE_YEAR_GROWTH', 'FQ', ignore_invalid_symbol = true)
grossMargin = i_GrossMargin ? request.financial(syminfo.tickerid, 'GROSS_MARGIN', 'FQ', ignore_invalid_symbol = true) : na
ROE = request.financial(syminfo.tickerid, 'RETURN_ON_EQUITY', 'FQ', ignore_invalid_symbol = true)

// Date
rev = request.financial(syminfo.tickerid, 'TOTAL_REVENUE', 'FQ', barmerge.gaps_on, ignore_invalid_symbol = true)

// Get EPS numbers from TradingView
// Estimates of next earning
futureEPS = earnings.future_eps
futureSales = earnings.future_revenue
futureTime = earnings.future_time

// EPS & Sales
barSince = ta.barssince(EPS != EPS[1] or EPS_Standard != EPS_Standard[1] or EPS_Estimate != EPS_Estimate[1])
EPSTime = barSince == 0

// Actual EPS
firstEPS = ta.valuewhen(bar_index == 0, EPS, 0)
actualEPS = ta.valuewhen(EPSTime, EPS, 0)
if na(actualEPS)
    actualEPS := firstEPS
    actualEPS
actualEPS1 = ta.valuewhen(EPSTime, EPS, 1)
if na(actualEPS1) and actualEPS != firstEPS
    actualEPS1 := firstEPS
    actualEPS1
actualEPS2 = ta.valuewhen(EPSTime, EPS, 2)
if na(actualEPS2) and actualEPS1 != firstEPS
    actualEPS2 := firstEPS
    actualEPS2
actualEPS3 = ta.valuewhen(EPSTime, EPS, 3)
if na(actualEPS3) and actualEPS2 != firstEPS
    actualEPS3 := firstEPS
    actualEPS3
actualEPS4 = ta.valuewhen(EPSTime, EPS, 4)
if na(actualEPS4) and actualEPS3 != firstEPS
    actualEPS4 := firstEPS
    actualEPS4
actualEPS5 = ta.valuewhen(EPSTime, EPS, 5)
if na(actualEPS5) and actualEPS4 != firstEPS
    actualEPS5 := firstEPS
    actualEPS5
actualEPS6 = ta.valuewhen(EPSTime, EPS, 6)
if na(actualEPS6) and actualEPS5 != firstEPS
    actualEPS6 := firstEPS
    actualEPS6
actualEPS7 = ta.valuewhen(EPSTime, EPS, 7)
if na(actualEPS7) and actualEPS6 != firstEPS
    actualEPS7 := firstEPS
    actualEPS7
actualEPS8 = ta.valuewhen(EPSTime, EPS, 8)
if na(actualEPS8) and actualEPS7 != firstEPS
    actualEPS8 := firstEPS
    actualEPS8
actualEPS9 = ta.valuewhen(EPSTime, EPS, 9)
if na(actualEPS9) and actualEPS8 != firstEPS
    actualEPS9 := firstEPS
    actualEPS9
actualEPS10 = ta.valuewhen(EPSTime, EPS, 10)
if na(actualEPS10) and actualEPS9 != firstEPS
    actualEPS10 := firstEPS
    actualEPS10
actualEPS11 = ta.valuewhen(EPSTime, EPS, 11)
if na(actualEPS11) and actualEPS10 != firstEPS
    actualEPS11 := firstEPS
    actualEPS11

// Standard EPS
standardEPS = ta.valuewhen(EPSTime, EPS_Standard, 0)
standardEPS1 = ta.valuewhen(EPSTime, EPS_Standard, 1)
standardEPS2 = ta.valuewhen(EPSTime, EPS_Standard, 2)
standardEPS3 = ta.valuewhen(EPSTime, EPS_Standard, 3)
standardEPS4 = ta.valuewhen(EPSTime, EPS_Standard, 4)
standardEPS5 = ta.valuewhen(EPSTime, EPS_Standard, 5)
standardEPS6 = ta.valuewhen(EPSTime, EPS_Standard, 6)
standardEPS7 = ta.valuewhen(EPSTime, EPS_Standard, 7)
standardEPS8 = ta.valuewhen(EPSTime, EPS_Standard, 8)
standardEPS9 = ta.valuewhen(EPSTime, EPS_Standard, 9)
standardEPS10 = ta.valuewhen(EPSTime, EPS_Standard, 10)
standardEPS11 = ta.valuewhen(EPSTime, EPS_Standard, 11)

// MarketSmith replace missing reported EPS by Standard EPS when available
if na(actualEPS)
    actualEPS := standardEPS
    actualEPS
if na(actualEPS1)
    actualEPS1 := standardEPS1
    actualEPS1
if na(actualEPS2)
    actualEPS2 := standardEPS2
    actualEPS2
if na(actualEPS3)
    actualEPS3 := standardEPS3
    actualEPS3
if na(actualEPS4)
    actualEPS4 := standardEPS4
    actualEPS4
if na(actualEPS5)
    actualEPS5 := standardEPS5
    actualEPS5
if na(actualEPS6)
    actualEPS6 := standardEPS6
    actualEPS6
if na(actualEPS7)
    actualEPS7 := standardEPS7
    actualEPS7
if na(actualEPS8)
    actualEPS8 := standardEPS8
    actualEPS8
if na(actualEPS9)
    actualEPS9 := standardEPS9
    actualEPS9
if na(actualEPS10)
    actualEPS10 := standardEPS10
    actualEPS10
if na(actualEPS11)
    actualEPS11 := standardEPS11
    actualEPS11

// Estimate EPS
estimateEPS = ta.valuewhen(EPSTime, EPS_Estimate, 0)
estimateEPS1 = ta.valuewhen(EPSTime, EPS_Estimate, 1)
estimateEPS2 = ta.valuewhen(EPSTime, EPS_Estimate, 2)
estimateEPS3 = ta.valuewhen(EPSTime, EPS_Estimate, 3)
estimateEPS4 = ta.valuewhen(EPSTime, EPS_Estimate, 4)
estimateEPS5 = ta.valuewhen(EPSTime, EPS_Estimate, 5)
estimateEPS6 = ta.valuewhen(EPSTime, EPS_Estimate, 6)
estimateEPS7 = ta.valuewhen(EPSTime, EPS_Estimate, 7)

// EPS Surprise
epsSurprise0 = (actualEPS - estimateEPS) / math.abs(estimateEPS) * 100
epsSurprise1 = (actualEPS1 - estimateEPS1) / math.abs(estimateEPS1) * 100
epsSurpise2 = (actualEPS2 - estimateEPS2) / math.abs(estimateEPS2) * 100
epsSurprise3 = (actualEPS3 - estimateEPS3) / math.abs(estimateEPS3) * 100
epsSurprise4 = (actualEPS4 - estimateEPS4) / math.abs(estimateEPS4) * 100
epsSurprise5 = (actualEPS5 - estimateEPS5) / math.abs(estimateEPS5) * 100
epsSurprise6 = (actualEPS6 - estimateEPS6) / math.abs(estimateEPS6) * 100
epsSurprise7 = (actualEPS7 - estimateEPS7) / math.abs(estimateEPS7) * 100

// Same with Sales
firstSale = ta.valuewhen(bar_index == 0, SALES, 0)
sales = ta.valuewhen(EPSTime, SALES, 0)
if na(sales)
    sales := firstSale
    sales
sales1 = ta.valuewhen(EPSTime, SALES, 1)
if na(sales1) and sales != firstSale
    sales1 := firstSale
    sales1
sales2 = ta.valuewhen(EPSTime, SALES, 2)
if na(sales2) and sales1 != firstSale
    sales2 := firstSale
    sales2
sales3 = ta.valuewhen(EPSTime, SALES, 3)
if na(sales3) and sales2 != firstSale
    sales3 := firstSale
    sales3
sales4 = ta.valuewhen(EPSTime, SALES, 4)
if na(sales4) and sales3 != firstSale
    sales4 := firstSale
    sales4
sales5 = ta.valuewhen(EPSTime, SALES, 5)
if na(sales5) and sales4 != firstSale
    sales5 := firstSale
    sales5
sales6 = ta.valuewhen(EPSTime, SALES, 6)
if na(sales6) and sales5 != firstSale
    sales6 := firstSale
    sales6
sales7 = ta.valuewhen(EPSTime, SALES, 7)
if na(sales7) and sales6 != firstSale
    sales7 := firstSale
    sales7
sales8 = ta.valuewhen(EPSTime, SALES, 8)
if na(sales8) and sales7 != firstSale
    sales8 := firstSale
    sales8
sales9 = ta.valuewhen(EPSTime, SALES, 9)
if na(sales9) and sales8 != firstSale
    sales9 := firstSale
    sales9
sales10 = ta.valuewhen(EPSTime, SALES, 10)
if na(sales10) and sales9 != firstSale
    sales10 := firstSale
    sales10
sales11 = ta.valuewhen(EPSTime, SALES, 11)
if na(sales11) and sales10 != firstSale
    sales11 := firstSale
    sales11

// Sales growth
firstSaleGrowth = ta.valuewhen(bar_index == 0, SALES_GROWTH, 0)
salesChange0 = ta.valuewhen(EPSTime, SALES_GROWTH, 0)
if na(salesChange0)
    salesChange0 := firstSaleGrowth
    salesChange0
salesChange1 = ta.valuewhen(EPSTime, SALES_GROWTH, 1)
if na(salesChange1) and salesChange0 != firstSaleGrowth
    salesChange1 := firstSaleGrowth
    salesChange1
salesChange2 = ta.valuewhen(EPSTime, SALES_GROWTH, 2)
if na(salesChange2) and salesChange1 != firstSaleGrowth
    salesChange2 := firstSaleGrowth
    salesChange2
salesChange3 = ta.valuewhen(EPSTime, SALES_GROWTH, 3)
if na(salesChange3) and salesChange2 != firstSaleGrowth
    salesChange3 := firstSaleGrowth
    salesChange3
salesChange4 = ta.valuewhen(EPSTime, SALES_GROWTH, 4)
if na(salesChange4) and salesChange3 != firstSaleGrowth
    salesChange4 := firstSaleGrowth
    salesChange4
salesChange5 = ta.valuewhen(EPSTime, SALES_GROWTH, 5)
if na(salesChange5) and salesChange4 != firstSaleGrowth
    salesChange5 := firstSaleGrowth
    salesChange5
salesChange6 = ta.valuewhen(EPSTime, SALES_GROWTH, 6)
if na(salesChange6) and salesChange5 != firstSaleGrowth
    salesChange6 := firstSaleGrowth
    salesChange6
salesChange7 = ta.valuewhen(EPSTime, SALES_GROWTH, 7)
if na(salesChange7) and salesChange6 != firstSaleGrowth
    salesChange7 := firstSaleGrowth
    salesChange7

// Sometimes the sales number is actualised but not the sales variation.
if salesChange0 == salesChange1 and not(na(sales4) or sales4 == 0)
    salesChange0 := (sales - sales4) / math.abs(sales4) * 100
    salesChange0

// Case where earning are very close, should check if the % variation is good
salesChangeF = (futureSales - sales3) / math.abs(sales3) * 100
if salesChange1 == salesChange0 and sales1 == sales
    salesChange1 := (sales1 - sales5) / math.abs(sales5) * 100
    salesChange1
if salesChange2 == salesChange1 and sales2 == sales1
    salesChange2 := (sales2 - sales6) / math.abs(sales6) * 100
    salesChange2
if salesChange3 == salesChange2 and sales3 == sales2
    salesChange3 := (sales3 - sales7) / math.abs(sales7) * 100
    salesChange3
if salesChange4 == salesChange3 and sales4 == sales3
    salesChange4 := (sales4 - sales8) / math.abs(sales8) * 100
    salesChange4
if salesChange5 == salesChange4 and sales5 == sales4
    salesChange5 := (sales5 - sales9) / math.abs(sales9) * 100
    salesChange5
if salesChange6 == salesChange5 and sales6 == sales5
    salesChange6 := (sales6 - sales10) / math.abs(sales10) * 100
    salesChange6
if salesChange7 == salesChange6 and sales7 == sales6
    salesChange7 := (sales7 - sales11) / math.abs(sales11) * 100
    salesChange7

// Sales estimaate
salesEstimate = ta.valuewhen(EPSTime, SALES_Estimate, 0)
salesEstimate1 = ta.valuewhen(EPSTime, SALES_Estimate, 1)
salesEstimate2 = ta.valuewhen(EPSTime, SALES_Estimate, 2)
salesEstimate3 = ta.valuewhen(EPSTime, SALES_Estimate, 3)
salesEstimate4 = ta.valuewhen(EPSTime, SALES_Estimate, 4)
salesEstimate5 = ta.valuewhen(EPSTime, SALES_Estimate, 5)
salesEstimate6 = ta.valuewhen(EPSTime, SALES_Estimate, 6)
salesEstimate7 = ta.valuewhen(EPSTime, SALES_Estimate, 7)

// Detect same sales for TradingView bug correction
bool sameSales = SALES == sales1 and SALES_GROWTH == salesChange1
bool recentEarn = ta.barssince(EPSTime) <= 6

// Function to define previous quarters gross margin & ROE
f_grossMargin(i) =>
    request.security(syminfo.tickerid, '3M', grossMargin[i])
f_roe(i) =>
    request.security(syminfo.tickerid, '3M', ROE[i])

// Same with gross margin
firstGrossMargin = ta.valuewhen(bar_index == 0, grossMargin, 0)
GM0 = ta.valuewhen(EPSTime, grossMargin, 0)
if na(GM0)
    GM0 := firstGrossMargin
    GM0
GM1 = ta.valuewhen(EPSTime, grossMargin, 1)
if na(GM1) and GM0 != firstGrossMargin
    GM1 := firstGrossMargin
    GM1
GM2 = ta.valuewhen(EPSTime, grossMargin, 2)
if na(GM2) and GM1 != firstGrossMargin
    GM2 := firstGrossMargin
    GM2
GM3 = ta.valuewhen(EPSTime, grossMargin, 3)
if na(GM3) and GM2 != firstGrossMargin
    GM3 := firstGrossMargin
    GM3
GM4 = ta.valuewhen(EPSTime, grossMargin, 4)
if na(GM4) and GM3 != firstGrossMargin
    GM4 := firstGrossMargin
    GM4
GM5 = ta.valuewhen(EPSTime, grossMargin, 5)
if na(GM5) and GM4 != firstGrossMargin
    GM5 := firstGrossMargin
    GM5
GM6 = ta.valuewhen(EPSTime, grossMargin, 6)
if na(GM6) and GM5 != firstGrossMargin
    GM6 := firstGrossMargin
    GM6
GM7 = ta.valuewhen(EPSTime, grossMargin, 7)
if na(GM7) and GM6 != firstGrossMargin
    GM7 := firstGrossMargin
    GM7

// Same with ROE
firstReturnOnEquity = ta.valuewhen(bar_index == 0, ROE, 0)
ROE0 = ta.valuewhen(EPSTime, ROE, 0)
if na(ROE0)
    ROE0 := firstReturnOnEquity
    ROE0
ROE1 = ta.valuewhen(EPSTime, ROE, 1)
if na(ROE1) and ROE0 != firstReturnOnEquity
    ROE1 := firstReturnOnEquity
    ROE1
ROE2 = ta.valuewhen(EPSTime, ROE, 2)
if na(ROE2) and ROE1 != firstReturnOnEquity
    ROE2 := firstReturnOnEquity
    ROE2
ROE3 = ta.valuewhen(EPSTime, ROE, 3)
if na(ROE3) and ROE2 != firstReturnOnEquity
    ROE3 := firstReturnOnEquity
    ROE3
ROE4 = ta.valuewhen(EPSTime, ROE, 4)
if na(ROE4) and ROE3 != firstReturnOnEquity
    ROE4 := firstReturnOnEquity
    ROE4
ROE5 = ta.valuewhen(EPSTime, ROE, 5)
if na(ROE5) and ROE4 != firstReturnOnEquity
    ROE5 := firstReturnOnEquity
    ROE5
ROE6 = ta.valuewhen(EPSTime, ROE, 6)
if na(ROE6) and ROE5 != firstReturnOnEquity
    ROE6 := firstReturnOnEquity
    ROE6
ROE7 = ta.valuewhen(EPSTime, ROE, 7)
if na(ROE7) and ROE6 != firstReturnOnEquity
    ROE7 := firstReturnOnEquity
    ROE7

// Calculation using IBD/MarketSmith principle : current quarter EPS vs the same quartar's EPS of previous year. (YoY)
epsChangeF = actualEPS3 < 0 ? na : (futureEPS - actualEPS3) / math.abs(actualEPS3) * 100
epsChange0 = actualEPS < 0 ? na : actualEPS4 < 0 ? na : (EPS - actualEPS4) / math.abs(actualEPS4) * 100
epsChange1 = actualEPS1 < 0 ? na : actualEPS5 < 0 ? na : (actualEPS1 - actualEPS5) / math.abs(actualEPS5) * 100
epsChange2 = actualEPS2 < 0 ? na : actualEPS6 < 0 ? na : (actualEPS2 - actualEPS6) / math.abs(actualEPS6) * 100
epsChange3 = actualEPS3 < 0 ? na : actualEPS7 < 0 ? na : (actualEPS3 - actualEPS7) / math.abs(actualEPS7) * 100
epsChange4 = actualEPS4 < 0 ? na : actualEPS8 < 0 ? na : (actualEPS4 - actualEPS8) / math.abs(actualEPS8) * 100
epsChange5 = actualEPS5 < 0 ? na : actualEPS9 < 0 ? na : (actualEPS5 - actualEPS9) / math.abs(actualEPS9) * 100
epsChange6 = actualEPS6 < 0 ? na : actualEPS10 < 0 ? na : (actualEPS6 - actualEPS10) / math.abs(actualEPS10) * 100
epsChange7 = actualEPS7 < 0 ? na : actualEPS11 < 0 ? na : (actualEPS7 - actualEPS11) / math.abs(actualEPS11) * 100

// We use another variable to check whether the calculation has been done with a previous negative EPS (To display "#")                                                                                 // added this condition because 0.98 vs -0.16 = #712/713% not 999% APA
epsChangeHashF = futureEPS < 0 ? na : actualEPS3 >= 0 ? na : (futureEPS - actualEPS3) / math.abs(actualEPS3) * 100
epsChangeHash0 = actualEPS < 0 ? na : actualEPS4 >= 0 ? na : (EPS - actualEPS4) / math.abs(actualEPS4) * 100
epsChangeHash1 = actualEPS1 < 0 ? na : actualEPS5 >= 0 ? na : (actualEPS1 - actualEPS5) / math.abs(actualEPS5) * 100
epsChangeHash2 = actualEPS2 < 0 ? na : actualEPS6 >= 0 ? na : (actualEPS2 - actualEPS6) / math.abs(actualEPS6) * 100
epsChangeHash3 = actualEPS3 < 0 ? na : actualEPS7 >= 0 ? na : (actualEPS3 - actualEPS7) / math.abs(actualEPS7) * 100
epsChangeHash4 = actualEPS4 < 0 ? na : actualEPS8 >= 0 ? na : (actualEPS4 - actualEPS8) / math.abs(actualEPS8) * 100
epsChangeHash5 = actualEPS5 < 0 ? na : actualEPS9 >= 0 ? na : (actualEPS5 - actualEPS9) / math.abs(actualEPS9) * 100
epsChangeHash6 = actualEPS6 < 0 ? na : actualEPS10 >= 0 ? na : (actualEPS6 - actualEPS10) / math.abs(actualEPS10) * 100
epsChangeHash7 = actualEPS7 < 0 ? na : actualEPS11 >= 0 ? na : (actualEPS7 - actualEPS11) / math.abs(actualEPS11) * 100

// EPS QoQ
epsChangeQoQF = (futureEPS - actualEPS) / math.abs(actualEPS) * 100
epsChangeQoQ0 = (actualEPS - actualEPS1) / math.abs(actualEPS1) * 100
epsChangeQoQ1 = (actualEPS1 - actualEPS2) / math.abs(actualEPS2) * 100
epsChangeQoQ2 = (actualEPS2 - actualEPS3) / math.abs(actualEPS3) * 100
epsChangeQoQ3 = (actualEPS3 - actualEPS4) / math.abs(actualEPS4) * 100
epsChangeQoQ4 = (actualEPS4 - actualEPS5) / math.abs(actualEPS5) * 100
epsChangeQoQ5 = (actualEPS5 - actualEPS6) / math.abs(actualEPS6) * 100
epsChangeQoQ6 = (actualEPS6 - actualEPS7) / math.abs(actualEPS7) * 100
epsChangeQoQ7 = (actualEPS7 - actualEPS8) / math.abs(actualEPS8) * 100

// Sales surprise
salesSurprise0 = (sales - salesEstimate) / math.abs(salesEstimate) * 100
salesSurprise1 = (sales1 - salesEstimate1) / math.abs(salesEstimate1) * 100
salesSurprise2 = (sales2 - salesEstimate2) / math.abs(salesEstimate2) * 100
salesSurprise3 = (sales3 - salesEstimate3) / math.abs(salesEstimate3) * 100
salesSurprise4 = (sales4 - salesEstimate4) / math.abs(salesEstimate4) * 100
salesSurprise5 = (sales5 - salesEstimate5) / math.abs(salesEstimate5) * 100
salesSurprise6 = (sales6 - salesEstimate6) / math.abs(salesEstimate6) * 100
salesSurprise7 = (sales7 - salesEstimate7) / math.abs(salesEstimate7) * 100

// Sales QoQ
salesChangeQoQF = (futureSales - sales) / math.abs(sales) * 100
salesChangeQoQ0 = (sales - sales1) / math.abs(sales1) * 100
salesChangeQoQ1 = (sales1 - sales2) / math.abs(sales2) * 100
salesChangeQoQ2 = (sales2 - sales3) / math.abs(sales3) * 100
salesChangeQoQ3 = (sales3 - sales4) / math.abs(sales4) * 100
salesChangeQoQ4 = (sales4 - sales5) / math.abs(sales5) * 100
salesChangeQoQ5 = (sales5 - sales6) / math.abs(sales6) * 100
salesChangeQoQ6 = (sales6 - sales7) / math.abs(sales7) * 100
salesChangeQoQ7 = (sales7 - sales8) / math.abs(sales8) * 100

// Adapt format of sales
futureS = futureSales / 1000000
sales0M = sales / 1000000
sales1M = sales1 / 1000000
sales2M = sales2 / 1000000
sales3M = sales3 / 1000000
sales4M = sales4 / 1000000
sales5M = sales5 / 1000000
sales6M = sales6 / 1000000
sales7M = sales7 / 1000000
sales8M = sales8 / 1000000
sales9M = sales9 / 1000000
sales10M = sales10 / 1000000
sales11M = sales11 / 1000000

// If sales > 1000M we want it to be displayed in B
if sales >= 10000000000
    futureS := futureSales / 1000000000
    sales0M := sales / 1000000000
    sales1M := sales1 / 1000000000
    sales2M := sales2 / 1000000000
    sales3M := sales3 / 1000000000
    sales4M := sales4 / 1000000000
    sales5M := sales5 / 1000000000
    sales6M := sales6 / 1000000000
    sales7M := sales7 / 1000000000
    sales8M := sales8 / 1000000000
    sales9M := sales9 / 1000000000
    sales10M := sales10 / 1000000000
    sales11M := sales11 / 1000000000
    sales11M

// Table functions
f_fillCell(_table, _column, _row, _value) =>
    _c_color = i_PosColor2
    _transp = 0
    _cellText = str.tostring(_value, '0.00')
    if _cellText == 'NaN'
        _cellText := 'N/A'
        _cellText
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = i_RowAndColumnTextColor, text_size = tableSize)

f_fillCell2(_table, _column, _row, _value) =>
    _c_color = i_PosColor2
    _transp = 0
    _cellText = str.tostring(_value, '0.0')
    if _cellText == 'NaN'
        _cellText := 'N/A'
        _cellText
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = i_RowAndColumnTextColor, text_size = tableSize)

// For sales comparison
f_fillCellSales(_table, _column, _row, _value, _value1) =>
    _c_color = i_PosColor2
    _transp = 0
    _cellText1 = str.tostring(_value, '0.0')
    _cellText2 = str.tostring(_value1, '0.0')
    if _cellText1 == 'NaN'
        _cellText1 := 'N/A'
        _cellText1
    if _cellText2 == 'NaN'
        _cellText2 := 'N/A'
        _cellText2
    _cellText = _cellText1 + ' vs ' + _cellText2
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = i_RowAndColumnTextColor, text_size = tableSize)

// For EPS comparison
f_fillCellEPS(_table, _column, _row, _value, _value1) =>
    _c_color = i_PosColor2
    _transp = 0
    _cellText1 = str.tostring(_value, '0.00')
    _cellText2 = str.tostring(_value1, '0.00')
    if _cellText1 == 'NaN'
        _cellText1 := 'N/A'
        _cellText1
    if _cellText2 == 'NaN'
        _cellText2 := 'N/A'
        _cellText2
    _cellText = _cellText1 + ' vs ' + _cellText2
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = i_RowAndColumnTextColor, text_size = tableSize)

f_fillCellComp(_table, _column, _row, _value) =>
    _c_color = _value >= 0 ? i_PosColor2 : i_NegColor2
    _transp = 0
    _cellText = _value > 999 ? '+999%' : _value < -999 ? '-999%' : _value > 0 ? '+' + str.tostring(_value, '0') + '%' : str.tostring(_value, '0') + '%'
    if _cellText == 'NaN%'
        _cellText := 'N/A'
        _cellText
    if _cellText == '+0%'
        _cellText := '0%'
        _cellText
    if _value == epsChangeHashF
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash0
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash1
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash2
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash3
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash4
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash5
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash6
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText
    if _value == epsChangeHash7
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
        _cellText

    // Color for even or odd row
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = _cellText == '0%' or _cellText == 'N/A' ? i_RowAndColumnTextColor : _c_color, text_size = tableSize)

// For EPS % surprise
f_fillCellCompSurp(_table, _column, _row, _value) =>
    _c_color = _value >= 0 ? i_PosSurp : i_NegSurp
    _transp = 0
    _cellText = _value > 999 ? '+999%' : _value < -999 ? '-999%' : _value > 0 ? '+' + str.tostring(_value, '0') + '%' : str.tostring(_value, '0') + '%'
    if _cellText == 'NaN%'
        _cellText := 'N/A'
        _cellText
    if _cellText == '+0%'
        _cellText := '0%'
        _cellText
    if _row == 11
        _cellText := '-'
        _cellText
    // Color for even or odd row
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = _cellText == '0%' or _cellText == 'N/A' ? i_RowAndColumnTextColor : _c_color, text_size = tableSize)

// For QoQ EPS % change
f_fillCellComp2(_table, _column, _row, _value) =>
    _c_color = _value >= 0 ? i_PosColor2 : i_NegColor2
    _transp = 0
    // Recent modification made that I need to put the IBD/MarketSmith limitation of +999% here
    _cellText = _value > 999 ? '+999%' : _value < -999 ? '-999%' : _value > 0 ? '+' + str.tostring(_value, '0') + '%' : str.tostring(_value, '0') + '%'
    if _cellText == 'NaN%'
        _cellText := 'N/A'
        _cellText
    // Color for even or odd row
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = _cellText == 'N/A' ? i_RowAndColumnTextColor : _c_color, text_size = tableSize)

// Function for date
f_array(arrayId, val) =>
    array.unshift(arrayId, val)
    array.pop(arrayId)

ftdate(_table, _column, _row, _value) =>
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? i_ResultBackgroundColorOdd : i_ResultBackgroundColorEven
    table.cell(table_id = _table, column = _column, row = _row, text = _value, bgcolor = myColor, text_color = i_RowAndColumnTextColor, text_size = tableSize)

// For date
var date = array.new_int(datasize)
if bool(rev)
    f_array(date, time)

// Function used to master the fill of cells
condRepeatSameValueAtLastLine = actualEPS == actualEPS1 and standardEPS == standardEPS1 and EPS_Estimate == EPS_Estimate[1]
if barstate.islast
    // EPS Display
    if i_Compare == true
        if i_Estimates
            f_fillCellEPS(epsTable, 1, 11, futureEPS, actualEPS3)
        f_fillCellEPS(epsTable, 1, 10, condRepeatSameValueAtLastLine ? na : EPS, condRepeatSameValueAtLastLine ? na : actualEPS4)
        f_fillCellEPS(epsTable, 1, 9, actualEPS1, actualEPS5)
        f_fillCellEPS(epsTable, 1, 8, actualEPS2, actualEPS6)
        f_fillCellEPS(epsTable, 1, 7, actualEPS3, actualEPS7)
        f_fillCellEPS(epsTable, 1, 6, actualEPS4, actualEPS8)
        f_fillCellEPS(epsTable, 1, 5, actualEPS5, actualEPS9)
        f_fillCellEPS(epsTable, 1, 4, actualEPS6, actualEPS10)
        f_fillCellEPS(epsTable, 1, 3, actualEPS7, actualEPS11)

    if i_Compare == false
        if i_Estimates
            f_fillCell(epsTable, 1, 11, futureEPS)
        f_fillCell(epsTable, 1, 10, condRepeatSameValueAtLastLine ? na : actualEPS)
        f_fillCell(epsTable, 1, 9, actualEPS1)
        f_fillCell(epsTable, 1, 8, actualEPS2)
        f_fillCell(epsTable, 1, 7, actualEPS3)
        f_fillCell(epsTable, 1, 6, actualEPS4)
        f_fillCell(epsTable, 1, 5, actualEPS5)
        f_fillCell(epsTable, 1, 4, actualEPS6)
        f_fillCell(epsTable, 1, 3, actualEPS7)

    // EPS % change YoY
    if i_YoY
        f_fillCellComp(epsTable, 2, 3, na(epsChange7) ? epsChangeHash7 : epsChange7)
        f_fillCellComp(epsTable, 2, 4, na(epsChange6) ? epsChangeHash6 : epsChange6)
        f_fillCellComp(epsTable, 2, 5, na(epsChange5) ? epsChangeHash5 : epsChange5)
        f_fillCellComp(epsTable, 2, 6, na(epsChange4) ? epsChangeHash4 : epsChange4)
        f_fillCellComp(epsTable, 2, 7, na(epsChange3) ? epsChangeHash3 : epsChange3)
        f_fillCellComp(epsTable, 2, 8, na(epsChange2) ? epsChangeHash2 : epsChange2)
        f_fillCellComp(epsTable, 2, 9, na(epsChange1) ? epsChangeHash1 : epsChange1)
        f_fillCellComp(epsTable, 2, 10, condRepeatSameValueAtLastLine ? na : na(epsChange0) ? epsChangeHash0 : epsChange0)
        if i_Estimates
            f_fillCellComp(epsTable, 2, 11, na(epsChangeF) ? epsChangeHashF : epsChangeF)

    // EPS % change QoQ
    if i_QoQ == true
        f_fillCellComp2(epsTable, 3, 3, epsChangeQoQ7)
        f_fillCellComp2(epsTable, 3, 4, epsChangeQoQ6)
        f_fillCellComp2(epsTable, 3, 5, epsChangeQoQ5)
        f_fillCellComp2(epsTable, 3, 6, epsChangeQoQ4)
        f_fillCellComp2(epsTable, 3, 7, epsChangeQoQ3)
        f_fillCellComp2(epsTable, 3, 8, epsChangeQoQ2)
        f_fillCellComp2(epsTable, 3, 9, epsChangeQoQ1)
        f_fillCellComp2(epsTable, 3, 10, epsChangeQoQ0)
        if i_Estimates
            f_fillCellComp2(epsTable, 3, 11, epsChangeQoQF)

    // EPS % surprises
    if i_Surprises
        f_fillCellCompSurp(epsTable, 4, 3, epsSurprise7)
        f_fillCellCompSurp(epsTable, 4, 4, epsSurprise6)
        f_fillCellCompSurp(epsTable, 4, 5, epsSurprise5)
        f_fillCellCompSurp(epsTable, 4, 6, epsSurprise4)
        f_fillCellCompSurp(epsTable, 4, 7, epsSurprise3)
        f_fillCellCompSurp(epsTable, 4, 8, epsSurpise2)
        f_fillCellCompSurp(epsTable, 4, 9, epsSurprise1)
        f_fillCellCompSurp(epsTable, 4, 10, epsSurprise0)
        if i_Estimates
            f_fillCellCompSurp(epsTable, 4, 11, 0)

    // Sales display
    if i_Compare == true
        if i_Estimates
            f_fillCellSales(epsTable, 5, 11, futureS, sales3M)
        f_fillCellSales(epsTable, 5, 10, condRepeatSameValueAtLastLine ? na : recentEarn and sameSales ? na : sales0M, condRepeatSameValueAtLastLine ? na : sales4M)
        f_fillCellSales(epsTable, 5, 9, sales1M, sales5M)
        f_fillCellSales(epsTable, 5, 8, sales2M, sales6M)
        f_fillCellSales(epsTable, 5, 7, sales3M, sales7M)
        f_fillCellSales(epsTable, 5, 6, sales4M, sales8M)
        f_fillCellSales(epsTable, 5, 5, sales5M, sales9M)
        f_fillCellSales(epsTable, 5, 4, sales6M, sales10M)
        f_fillCellSales(epsTable, 5, 3, sales7M, sales11M)

    if i_Compare == false
        if i_Estimates
            f_fillCell2(epsTable, 5, 11, futureS)
        f_fillCell2(epsTable, 5, 10, condRepeatSameValueAtLastLine ? na : recentEarn and sameSales ? na : sales0M)
        f_fillCell2(epsTable, 5, 9, sales1M)
        f_fillCell2(epsTable, 5, 8, sales2M)
        f_fillCell2(epsTable, 5, 7, sales3M)
        f_fillCell2(epsTable, 5, 6, sales4M)
        f_fillCell2(epsTable, 5, 5, sales5M)
        f_fillCell2(epsTable, 5, 4, sales6M)
        f_fillCell2(epsTable, 5, 3, sales7M)

    // Sales % change YoY
    if i_YoY
        f_fillCellComp(epsTable, 6, 3, salesChange7)
        f_fillCellComp(epsTable, 6, 4, salesChange6)
        f_fillCellComp(epsTable, 6, 5, salesChange5)
        f_fillCellComp(epsTable, 6, 6, salesChange4)
        f_fillCellComp(epsTable, 6, 7, salesChange3)
        f_fillCellComp(epsTable, 6, 8, salesChange2)
        f_fillCellComp(epsTable, 6, 9, salesChange1)
        f_fillCellComp(epsTable, 6, 10, condRepeatSameValueAtLastLine ? na : recentEarn and sameSales ? na : salesChange0)
        if i_Estimates
            f_fillCellComp(epsTable, 6, 11, salesChangeF)

    // Sales % change QoQ
    if i_QoQ == true
        f_fillCellComp(epsTable, 7, 3, salesChangeQoQ7)
        f_fillCellComp(epsTable, 7, 4, salesChangeQoQ6)
        f_fillCellComp(epsTable, 7, 5, salesChangeQoQ5)
        f_fillCellComp(epsTable, 7, 6, salesChangeQoQ4)
        f_fillCellComp(epsTable, 7, 7, salesChangeQoQ3)
        f_fillCellComp(epsTable, 7, 8, salesChangeQoQ2)
        f_fillCellComp(epsTable, 7, 9, salesChangeQoQ1)
        f_fillCellComp(epsTable, 7, 10, condRepeatSameValueAtLastLine ? na : recentEarn and sameSales ? na : salesChangeQoQ0)
        if i_Estimates
            f_fillCellComp(epsTable, 7, 11, salesChangeQoQF)

    // Sales % surprises
    if i_Surprises
        f_fillCellCompSurp(epsTable, 8, 3, salesSurprise7)
        f_fillCellCompSurp(epsTable, 8, 4, salesSurprise6)
        f_fillCellCompSurp(epsTable, 8, 5, salesSurprise5)
        f_fillCellCompSurp(epsTable, 8, 6, salesSurprise4)
        f_fillCellCompSurp(epsTable, 8, 7, salesSurprise3)
        f_fillCellCompSurp(epsTable, 8, 8, salesSurprise2)
        f_fillCellCompSurp(epsTable, 8, 9, salesSurprise1)
        f_fillCellCompSurp(epsTable, 8, 10, salesSurprise0)
        if i_Estimates
            f_fillCellCompSurp(epsTable, 8, 11, 0)

    // Gross margin
    if i_GrossMargin == true
        f_fillCellComp(epsTable, 9, 3, GM7)
        f_fillCellComp(epsTable, 9, 4, GM6)
        f_fillCellComp(epsTable, 9, 5, GM5)
        f_fillCellComp(epsTable, 9, 6, GM4)
        f_fillCellComp(epsTable, 9, 7, GM3)
        f_fillCellComp(epsTable, 9, 8, GM2)
        f_fillCellComp(epsTable, 9, 9, GM1)
        f_fillCellComp(epsTable, 9, 10, GM0)

    // ROE
    if i_ROE == true
        f_fillCellComp(epsTable, 10, 3, ROE7)
        f_fillCellComp(epsTable, 10, 4, ROE6)
        f_fillCellComp(epsTable, 10, 5, ROE5)
        f_fillCellComp(epsTable, 10, 6, ROE4)
        f_fillCellComp(epsTable, 10, 7, ROE3)
        f_fillCellComp(epsTable, 10, 8, ROE2)
        f_fillCellComp(epsTable, 10, 9, ROE1)
        f_fillCellComp(epsTable, 10, 10, ROE0)

    // For Date MMM-yy
    for i = 0 to datasize - 3 by 1
        if barstate.islast
            ftdate(epsTable, 0, datasize - i, str.format('{0, date, MMM-yy}', array.get(date, i)))
    if i_Estimates
        ftdate(epsTable, 0, 11, str.format('{0, date, MMM-yy}', futureTime) + ' est')

    // Headings of table
    table.cell(epsTable, 0, 0, text = 'Quarterly', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    table.cell(epsTable, 1, 0, text = 'EPS ($)', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_YoY
        table.cell(epsTable, 2, 0, text = '% Chg', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_QoQ
        table.cell(epsTable, 3, 0, text = 'QoQ', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_Surprises
        table.cell(epsTable, 4, 0, text = '% Surp', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    table.cell(epsTable, 5, 0, text = 'Sales ($M)', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_YoY
        table.cell(epsTable, 6, 0, text = '% Chg', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_QoQ
        table.cell(epsTable, 7, 0, text = 'QoQ', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_Surprises
        table.cell(epsTable, 8, 0, text = '% Surp', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_GrossMargin
        table.cell(epsTable, 9, 0, text = 'GM', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
        if i_Estimates
            table.cell(epsTable, 9, 11, text = '-', bgcolor = i_ResultBackgroundColorEven, text_color = i_RowAndColumnTextColor, text_size = tableSize)
    if i_ROE
        table.cell(epsTable, 10, 0, text = 'ROE', bgcolor = i_MarketSu ? color.white : i_ResultBackgroundColorOdd, text_color = i_RowAndColumnTextColor, text_size = tableSize)
        if i_Estimates
            table.cell(epsTable, 10, 11, text = '-', bgcolor = i_ResultBackgroundColorEven, text_color = i_RowAndColumnTextColor, text_size = tableSize)

// Display arrow on the graph with EPS % change
selectEPS = ta.valuewhen(EPSTime, epsChangeHash0, 0) > ta.valuewhen(EPSTime, epsChange0, 0)
EPSvalue = i_ArrowQoq ? epsChangeQoQ0 : selectEPS ? ta.valuewhen(EPSTime, epsChangeHash0, 0) : ta.valuewhen(EPSTime, epsChange0, 0)
salesValue = i_ArrowQoq ? salesChangeQoQ0 : ta.valuewhen(EPSTime, salesChange0, 0)
textLabel = i_SalesOnGraph ? 'EPS & Sales' : 'EPS'
EPSDisplayText = EPSvalue > 999 ? '\n+999%' : EPSvalue > 0 ? '\n+' + str.tostring(EPSvalue, '0') + '%' : '\n' + str.tostring(EPSvalue, '0') + '%'
EPSDisplayText := EPSDisplayText == '\nNaN%' ? '\nN/A' : EPSDisplayText
EPSDisplayText := EPSDisplayText == '\n+0%' ? '\n0%' : EPSDisplayText
salesDisplayText = (EPSTime or EPSTime[1]) and sameSales and barstate.islast ? 'NaN%' : salesValue > 999 ? '+999%' : salesValue > 0 ? '+' + str.tostring(salesValue, '0') + '%' : str.tostring(salesValue, '0') + '%'
salesDisplayText := salesDisplayText == 'NaN%' ? 'N/A' : salesDisplayText
salesDisplayText := salesDisplayText == '+0%' ? '0%' : salesDisplayText

// Plot sales or not, depending on the result
if EPSTime and i_ArrowOnGraph
    arrowLabel = label.new(bar_index, bar_index, xloc = xloc.bar_index, yloc = yloc.belowbar, text = textLabel, style = label.style_triangleup, color = i_ArrowColor, textcolor = i_ArrowColor, size = arrowSize)
    // EPS or EPS & Sales
    mainLabel = label.new(bar_index, bar_index, xloc = xloc.bar_index, yloc = yloc.belowbar, text = textLabel, style = label.style_triangleup, color = color.new(color.aqua, 100), textcolor = i_ArrowColor, size = arrowSize)
    // EPS % change
    if not i_SalesOnGraph
        epsChangeLabel = label.new(bar_index, low, xloc = xloc.bar_index, yloc = yloc.belowbar, text = EPSDisplayText, style = label.style_triangleup, color = color.new(color.aqua, 100), textcolor = EPSDisplayText == '\nN/A' or EPSDisplayText == '\n0%' ? i_ArrowColor : EPSvalue > -1 ? i_PosArrowColor : i_NegArrowColor, size = arrowSize)
        epsChangeLabel
    if i_SalesOnGraph
        saleschangeLabel = label.new(bar_index, low, xloc = xloc.bar_index, yloc = yloc.belowbar, text = EPSDisplayText + ' | ' + salesDisplayText, style = label.style_triangleup, color = color.new(color.aqua, 100), textcolor = EPSDisplayText == '\nN/A' or EPSDisplayText == '\n0%' ? i_ArrowColor : EPSvalue > -1 ? i_PosArrowColor : i_NegArrowColor, size = arrowSize)
        saleschangeLabel