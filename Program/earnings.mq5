// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © kelvinyue37

//@version=6
indicator(title = 'Earnings', shorttitle = 'Earnings', overlay = true)

// Input parameters
// Quantities to be displayed on the graph
graphArrows = input(true, title = 'Arrows', inline = '1', group = 'Graph')
graphQoQ = input(false, title = 'QoQ', inline = '1', group = 'Graph')
graphSales = input(false, title = 'Sales', inline = '1', group = 'Graph')

// Graph settings
inputGraphArrowSize = input.string('Small', title = 'Arrow Size', options = ['Tiny', 'Small', 'Normal', 'Large'], inline = '2', group = 'Graph')
graphArrowColor = input(color.black, title = 'Arrow Colour', inline = '3', group = 'Graph')
graphPosColor = input(color.blue, title = '+ve', inline = '3', group = 'Graph')
graphNegColor = input(color.red, title = '-ve', inline = '3', group = 'Graph')

// Display the table
displayTable = input.bool(true, title = 'Display Table', group = 'Table', inline = '1')

// Quantities to be displayed on the table
tableEst = input(true, title = 'Estimates', group = 'Table', inline = '2')
tableComp = input(false, title = 'Compare with YoY', group = 'Table', inline = '2')
tableYoY = input(true, title = 'YoY', group = 'Table', inline = '3')
tableQoQ = input(false, title = 'QoQ', group = 'Table', inline = '3')
tableSurp = input(false, title = 'Surprise (%)', group = 'Table', inline = '4')
posSurpColor = input(color.blue, title = '+ve', group = 'Table', inline = '4')
negSurpColor = input(color.red, title = '-ve', group = 'Table', inline = '4')
tableGM = input(false, title = 'Gross Margin (GM)', group = 'Table', inline = '5')
tableROE = input(false, title = 'Return On Equity (ROE)', group = 'Table', inline = '5')
tableTextColor = input(color.black, title = 'Text Colour', group = 'Table', inline = '6')
tablePosColor = input(color.blue, title = '+ve', group = 'Table', inline = '6')
tableNegColor = input(color.red, title = '-ve', group = 'Table', inline = '6')

// Table settings
inputTableSize = input.string('Normal', title = 'Size', options = ['Tiny', 'Small', 'Normal', 'Large'], group = 'Table', inline = '7')
inputTablePos = input.string(defval = 'Bottom Left', title = 'Position', options = ['Top Left', 'Top Centre', 'Top Right', 'Middle Left', 'Middle Centre', 'Middle Right', 'Bottom Left', 'Bottom Centre', 'Bottom Right'], group = 'Table', inline = '7')
frameWidth = input.int(1, title = 'Frame Width', group = 'Table', options = [0, 1, 2, 3, 4, 5], inline = '9')
frameColor = input(color.black, title = 'Frame Colour', group = 'Table', inline = '9')
tableBorder = input(true, title = 'Border', group = 'Table', inline = '10')
borderColor = input(color.black, title = ' | Colour', group = 'Table', inline = '10')
bgColorOdd = input(color.rgb(231, 231, 231), title = 'Odd Rows', group = 'Table', inline = '11')
bgColorEven = input(color.white, title = 'Even Rows', group = 'Table', inline = '11')

// Define the size of the data
datasize = 10

// Convert input to graph arrow size
graphArrowSize = switch inputGraphArrowSize
    'Normal' => size.normal
    'Tiny' => size.tiny
    'Small' => size.small
    'Large' => size.large

// Convert input to table size
tableSize = switch inputTableSize
    'Normal' => size.normal
    'Tiny' => size.tiny
    'Small' => size.small
    'Large' => size.large

// Convert input to table position
tablePos = switch inputTablePos
    'Top Left' => position.top_left
    'Top Centre' => position.top_center
    'Top Right' => position.top_right
    'Middle Left' => position.middle_left
    'Middle Centre' => position.middle_center
    'Middle Right' => position.middle_right
    'Bottom Left' => position.bottom_left
    'Bottom Centre' => position.bottom_center
    'Bottom Right' => position.bottom_right

// Declare table
var table epsTable = table.new(tablePos, 15, 15, frame_color = frameColor, frame_width = frameWidth, border_width = tableBorder ? 1 : 0, border_color = borderColor)

// Request current earnings per share (EPS) data
repEPS = request.earnings(syminfo.tickerid, earnings.actual, ignore_invalid_symbol = true, lookahead = barmerge.lookahead_on)
repEPSStandard = request.earnings(syminfo.tickerid, earnings.standardized, ignore_invalid_symbol = true, lookahead = barmerge.lookahead_on)
repEPSEst = request.earnings(syminfo.tickerid, earnings.estimate, ignore_invalid_symbol = true, lookahead = barmerge.lookahead_on)

// Request revenue data
repSales = request.financial(syminfo.tickerid, 'TOTAL_REVENUE', 'FQ', ignore_invalid_symbol = true)
repSalesEst = request.financial(syminfo.tickerid, 'SALES_ESTIMATES', 'FQ', ignore_invalid_symbol = true)
repSalesGrowth = request.financial(syminfo.tickerid, 'REVENUE_ONE_YEAR_GROWTH', 'FQ', ignore_invalid_symbol = true)

// Request GM data
repGM = tableGM ? request.financial(syminfo.tickerid, 'GROSS_MARGIN', 'FQ', ignore_invalid_symbol = true) : na

// Request ROE data
repROE = tableROE ? request.financial(syminfo.tickerid, 'RETURN_ON_EQUITY', 'FQ', ignore_invalid_symbol = true) : na

// Get future earnings estimates from TradingView
timeF = earnings.future_time
epsF = earnings.future_eps
salesF = earnings.future_revenue

// Determine if a new EPS or related value has been reported
epsTime = (ta.barssince(repEPS != repEPS[1] or repEPSStandard != repEPSStandard[1] or repEPSEst != repEPSEst[1])) == 0

// Retrieve the first EPS value at the start of the data series
eps0 = ta.valuewhen(bar_index == 0, repEPS, 0)

// Calculate EPS based on the reporting time
actualEPS0 = ta.valuewhen(epsTime, repEPS, 0)
if na(actualEPS0)
    actualEPS0 := eps0
eps1 = ta.valuewhen(epsTime, repEPS, 1)
if na(eps1) and actualEPS0 != eps0
    eps1 := eps0
eps2 = ta.valuewhen(epsTime, repEPS, 2)
if na(eps2) and eps1 != eps0
    eps2 := eps0
eps3 = ta.valuewhen(epsTime, repEPS, 3)
if na(eps3) and eps2 != eps0
    eps3 := eps0
eps4 = ta.valuewhen(epsTime, repEPS, 4)
if na(eps4) and eps3 != eps0
    eps4 := eps0
eps5 = ta.valuewhen(epsTime, repEPS, 5)
if na(eps5) and eps4 != eps0
    eps5 := eps0
eps6 = ta.valuewhen(epsTime, repEPS, 6)
if na(eps6) and eps5 != eps0
    eps6 := eps0
eps7 = ta.valuewhen(epsTime, repEPS, 7)
if na(eps7) and eps6 != eps0
    eps7 := eps0
eps8 = ta.valuewhen(epsTime, repEPS, 8)
if na(eps8) and eps7 != eps0
    eps8 := eps0
eps9 = ta.valuewhen(epsTime, repEPS, 9)
if na(eps9) and eps8 != eps0
    eps9 := eps0
eps10 = ta.valuewhen(epsTime, repEPS, 10)
if na(eps10) and eps9 != eps0
    eps10 := eps0
eps11 = ta.valuewhen(epsTime, repEPS, 11)
if na(eps11) and eps10 != eps0
    eps11 := eps0

// Fill missing EPS with standardised EPS
standardEPS0 = ta.valuewhen(epsTime, repEPSStandard, 0)
standardEPS1 = ta.valuewhen(epsTime, repEPSStandard, 1)
if na(actualEPS0)
    actualEPS0 := standardEPS0
if na(eps1)
    eps1 := standardEPS1
if na(eps2)
    eps2 := ta.valuewhen(epsTime, repEPSStandard, 2)
if na(eps3)
    eps3 := ta.valuewhen(epsTime, repEPSStandard, 3)
if na(eps4)
    eps4 := ta.valuewhen(epsTime, repEPSStandard, 4)
if na(eps5)
    eps5 := ta.valuewhen(epsTime, repEPSStandard, 5)
if na(eps6)
    eps6 := ta.valuewhen(epsTime, repEPSStandard, 6)
if na(eps7)
    eps7 := ta.valuewhen(epsTime, repEPSStandard, 7)
if na(eps8)
    eps8 := ta.valuewhen(epsTime, repEPSStandard, 8)
if na(eps9)
    eps9 := ta.valuewhen(epsTime, repEPSStandard, 9)
if na(eps10)
    eps10 := ta.valuewhen(epsTime, repEPSStandard, 10)
if na(eps11)
    eps11 := ta.valuewhen(epsTime, repEPSStandard, 11)

// Retrieve EPS estimates
estEPS = ta.valuewhen(epsTime, repEPSEst, 0)
estEPS1 = ta.valuewhen(epsTime, repEPSEst, 1)
estEPS2 = ta.valuewhen(epsTime, repEPSEst, 2)
estEPS3 = ta.valuewhen(epsTime, repEPSEst, 3)
estEPS4 = ta.valuewhen(epsTime, repEPSEst, 4)
estEPS5 = ta.valuewhen(epsTime, repEPSEst, 5)
estEPS6 = ta.valuewhen(epsTime, repEPSEst, 6)
estEPS7 = ta.valuewhen(epsTime, repEPSEst, 7)

// Calculate EPS surprises
epsSurp0 = (actualEPS0 - estEPS) / math.abs(estEPS) * 100
epsSurp1 = (eps1 - estEPS1) / math.abs(estEPS1) * 100
epsSurp2 = (eps2 - estEPS2) / math.abs(estEPS2) * 100
epsSurp3 = (eps3 - estEPS3) / math.abs(estEPS3) * 100
epsSurp4 = (eps4 - estEPS4) / math.abs(estEPS4) * 100
epsSurp5 = (eps5 - estEPS5) / math.abs(estEPS5) * 100
epsSurp6 = (eps6 - estEPS6) / math.abs(estEPS6) * 100
epsSurp7 = (eps7 - estEPS7) / math.abs(estEPS7) * 100

// Retrieve the first sales value at the start of the data series
sales0 = ta.valuewhen(bar_index == 0, repSales, 0)

// Calculate sales based on the reporting time
actualSales0 = ta.valuewhen(epsTime, repSales, 0)
if na(actualSales0)
    actualSales0 := sales0
sales1 = ta.valuewhen(epsTime, repSales, 1)
if na(sales1) and actualSales0 != sales0
    sales1 := sales0
sales2 = ta.valuewhen(epsTime, repSales, 2)
if na(sales2) and sales1 != sales0
    sales2 := sales0
sales3 = ta.valuewhen(epsTime, repSales, 3)
if na(sales3) and sales2 != sales0
    sales3 := sales0
sales4 = ta.valuewhen(epsTime, repSales, 4)
if na(sales4) and sales3 != sales0
    sales4 := sales0
sales5 = ta.valuewhen(epsTime, repSales, 5)
if na(sales5) and sales4 != sales0
    sales5 := sales0
sales6 = ta.valuewhen(epsTime, repSales, 6)
if na(sales6) and sales5 != sales0
    sales6 := sales0
sales7 = ta.valuewhen(epsTime, repSales, 7)
if na(sales7) and sales6 != sales0
    sales7 := sales0
sales8 = ta.valuewhen(epsTime, repSales, 8)
if na(sales8) and sales7 != sales0
    sales8 := sales0
sales9 = ta.valuewhen(epsTime, repSales, 9)
if na(sales9) and sales8 != sales0
    sales9 := sales0
sales10 = ta.valuewhen(epsTime, repSales, 10)
if na(sales10) and sales9 != sales0
    sales10 := sales0
sales11 = ta.valuewhen(epsTime, repSales, 11)
if na(sales11) and sales10 != sales0
    sales11 := sales0

// Retrieve the first sales growth value at the start of the data series
salesGrowth0 = ta.valuewhen(bar_index == 0, repSalesGrowth, 0)

// Calculate sales growth based on the reporting time
actualSalesGrowth0 = ta.valuewhen(epsTime, repSalesGrowth, 0)
if na(actualSalesGrowth0)
    actualSalesGrowth0 := salesGrowth0
salesGrowth1 = ta.valuewhen(epsTime, repSalesGrowth, 1)
if na(salesGrowth1) and actualSalesGrowth0 != salesGrowth0
    salesGrowth1 := salesGrowth0
salesGrowth2 = ta.valuewhen(epsTime, repSalesGrowth, 2)
if na(salesGrowth2) and salesGrowth1 != salesGrowth0
    salesGrowth2 := salesGrowth0
salesGrowth3 = ta.valuewhen(epsTime, repSalesGrowth, 3)
if na(salesGrowth3) and salesGrowth2 != salesGrowth0
    salesGrowth3 := salesGrowth0
salesGrowth4 = ta.valuewhen(epsTime, repSalesGrowth, 4)
if na(salesGrowth4) and salesGrowth3 != salesGrowth0
    salesGrowth4 := salesGrowth0
salesGrowth5 = ta.valuewhen(epsTime, repSalesGrowth, 5)
if na(salesGrowth5) and salesGrowth4 != salesGrowth0
    salesGrowth5 := salesGrowth0
salesGrowth6 = ta.valuewhen(epsTime, repSalesGrowth, 6)
if na(salesGrowth6) and salesGrowth5 != salesGrowth0
    salesGrowth6 := salesGrowth0
salesGrowth7 = ta.valuewhen(epsTime, repSalesGrowth, 7)
if na(salesGrowth7) and salesGrowth6 != salesGrowth0
    salesGrowth7 := salesGrowth0

// Check if the sales change has been actualised
if actualSalesGrowth0 == salesGrowth1 and not(na(sales4) or sales4 == 0)
    actualSalesGrowth0 := (sales0 - sales4) / math.abs(sales4) * 100

// Calculate future sales change
salesGrowthF = (salesF - sales3) / math.abs(sales3) * 100

// Assess subsequent sales changes
if salesGrowth1 == actualSalesGrowth0 and sales1 == sales0
    salesGrowth1 := (sales1 - sales5) / math.abs(sales5) * 100
if salesGrowth2 == salesGrowth1 and sales2 == sales1
    salesGrowth2 := (sales2 - sales6) / math.abs(sales6) * 100
if salesGrowth3 == salesGrowth2 and sales3 == sales2
    salesGrowth3 := (sales3 - sales7) / math.abs(sales7) * 100
if salesGrowth4 == salesGrowth3 and sales4 == sales3
    salesGrowth4 := (sales4 - sales8) / math.abs(sales8) * 100
if salesGrowth5 == salesGrowth4 and sales5 == sales4
    salesGrowth5 := (sales5 - sales9) / math.abs(sales9) * 100
if salesGrowth6 == salesGrowth5 and sales6 == sales5
    salesGrowth6 := (sales6 - sales10) / math.abs(sales10) * 100
if salesGrowth7 == salesGrowth6 and sales7 == sales6
    salesGrowth7 := (sales7 - sales11) / math.abs(sales11) * 100

// Retrieve sales estimates based on the reporting time
salesEst0 = ta.valuewhen(epsTime, repSalesEst, 0)
salesEst1 = ta.valuewhen(epsTime, repSalesEst, 1)
salesEst2 = ta.valuewhen(epsTime, repSalesEst, 2)
salesEst3 = ta.valuewhen(epsTime, repSalesEst, 3)
salesEst4 = ta.valuewhen(epsTime, repSalesEst, 4)
salesEst5 = ta.valuewhen(epsTime, repSalesEst, 5)
salesEst6 = ta.valuewhen(epsTime, repSalesEst, 6)
salesEst7 = ta.valuewhen(epsTime, repSalesEst, 7)

// Detect same sales for TradingView bug correction
bool sameSales = repSales == sales1 and repSalesGrowth == salesGrowth1
bool recentEarn = ta.barssince(epsTime) <= 6

// Retrieve the first GM value at the start of the data series
gm0 = ta.valuewhen(bar_index == 0, repGM, 0)

// Calculate GM based on the reporting time
actualGM0 = ta.valuewhen(epsTime, repGM, 0)
if na(actualGM0)
    actualGM0 := gm0
gm1 = ta.valuewhen(epsTime, repGM, 1)
if na(gm1) and actualGM0 != gm0
    gm1 := gm0
gm2 = ta.valuewhen(epsTime, repGM, 2)
if na(gm2) and gm1 != gm0
    gm2 := gm0
gm3 = ta.valuewhen(epsTime, repGM, 3)
if na(gm3) and gm2 != gm0
    gm3 := gm0
gm4 = ta.valuewhen(epsTime, repGM, 4)
if na(gm4) and gm3 != gm0
    gm4 := gm0
gm5 = ta.valuewhen(epsTime, repGM, 5)
if na(gm5) and gm4 != gm0
    gm5 := gm0
gm6 = ta.valuewhen(epsTime, repGM, 6)
if na(gm6) and gm5 != gm0
    gm6 := gm0
gm7 = ta.valuewhen(epsTime, repGM, 7)
if na(gm7) and gm6 != gm0
    gm7 := gm0

// Retrieve the first ROE value at the start of the data series
roe0 = ta.valuewhen(bar_index == 0, repROE, 0)

// Calculate ROE based on the reporting time
actualROE0 = ta.valuewhen(epsTime, repROE, 0)
if na(actualROE0)
    actualROE0 := roe0
roe1 = ta.valuewhen(epsTime, repROE, 1)
if na(roe1) and actualROE0 != roe0
    roe1 := roe0
roe2 = ta.valuewhen(epsTime, repROE, 2)
if na(roe2) and roe1 != roe0
    roe2 := roe0
roe3 = ta.valuewhen(epsTime, repROE, 3)
if na(roe3) and roe2 != roe0
    roe3 := roe0
roe4 = ta.valuewhen(epsTime, repROE, 4)
if na(roe4) and roe3 != roe0
    roe4 := roe0
roe5 = ta.valuewhen(epsTime, repROE, 5)
if na(roe5) and roe4 != roe0
    roe5 := roe0
roe6 = ta.valuewhen(epsTime, repROE, 6)
if na(roe6) and roe5 != roe0
    roe6 := roe0
roe7 = ta.valuewhen(epsTime, repROE, 7)
if na(roe7) and roe6 != roe0
    roe7 := roe0

// Calculate EPS YoY change on the same quarter
epsChangeF = eps3 < 0 ? na : (epsF - eps3) / math.abs(eps3) * 100
epsChange0 = actualEPS0 < 0 ? na : eps4 < 0 ? na : (repEPS - eps4) / math.abs(eps4) * 100
epsChange1 = eps1 < 0 ? na : eps5 < 0 ? na : (eps1 - eps5) / math.abs(eps5) * 100
epsChange2 = eps2 < 0 ? na : eps6 < 0 ? na : (eps2 - eps6) / math.abs(eps6) * 100
epsChange3 = eps3 < 0 ? na : eps7 < 0 ? na : (eps3 - eps7) / math.abs(eps7) * 100
epsChange4 = eps4 < 0 ? na : eps8 < 0 ? na : (eps4 - eps8) / math.abs(eps8) * 100
epsChange5 = eps5 < 0 ? na : eps9 < 0 ? na : (eps5 - eps9) / math.abs(eps9) * 100
epsChange6 = eps6 < 0 ? na : eps10 < 0 ? na : (eps6 - eps10) / math.abs(eps10) * 100
epsChange7 = eps7 < 0 ? na : eps11 < 0 ? na : (eps7 - eps11) / math.abs(eps11) * 100

// Check whether the calculation has been done with a previous negative EPS
epsChangeHashF = epsF < 0 ? na : eps3 >= 0 ? na : (epsF - eps3) / math.abs(eps3) * 100
epsChangeHash0 = actualEPS0 < 0 ? na : eps4 >= 0 ? na : (repEPS - eps4) / math.abs(eps4) * 100
epsChangeHash1 = eps1 < 0 ? na : eps5 >= 0 ? na : (eps1 - eps5) / math.abs(eps5) * 100
epsChangeHash2 = eps2 < 0 ? na : eps6 >= 0 ? na : (eps2 - eps6) / math.abs(eps6) * 100
epsChangeHash3 = eps3 < 0 ? na : eps7 >= 0 ? na : (eps3 - eps7) / math.abs(eps7) * 100
epsChangeHash4 = eps4 < 0 ? na : eps8 >= 0 ? na : (eps4 - eps8) / math.abs(eps8) * 100
epsChangeHash5 = eps5 < 0 ? na : eps9 >= 0 ? na : (eps5 - eps9) / math.abs(eps9) * 100
epsChangeHash6 = eps6 < 0 ? na : eps10 >= 0 ? na : (eps6 - eps10) / math.abs(eps10) * 100
epsChangeHash7 = eps7 < 0 ? na : eps11 >= 0 ? na : (eps7 - eps11) / math.abs(eps11) * 100

// Calculate EPS QoQ change
epsChangeQoQF = (epsF - actualEPS0) / math.abs(actualEPS0) * 100
epsChangeQoQ0 = (actualEPS0 - eps1) / math.abs(eps1) * 100
epsChangeQoQ1 = (eps1 - eps2) / math.abs(eps2) * 100
epsChangeQoQ2 = (eps2 - eps3) / math.abs(eps3) * 100
epsChangeQoQ3 = (eps3 - eps4) / math.abs(eps4) * 100
epsChangeQoQ4 = (eps4 - eps5) / math.abs(eps5) * 100
epsChangeQoQ5 = (eps5 - eps6) / math.abs(eps6) * 100
epsChangeQoQ6 = (eps6 - eps7) / math.abs(eps7) * 100
epsChangeQoQ7 = (eps7 - eps8) / math.abs(eps8) * 100

// Calculate sales surprises
salesSurp0 = (sales0 - salesEst0) / math.abs(salesEst0) * 100
salesSurp1 = (sales1 - salesEst1) / math.abs(salesEst1) * 100
salesSurp2 = (sales2 - salesEst2) / math.abs(salesEst2) * 100
salesSurp3 = (sales3 - salesEst3) / math.abs(salesEst3) * 100
salesSurp4 = (sales4 - salesEst4) / math.abs(salesEst4) * 100
salesSurp5 = (sales5 - salesEst5) / math.abs(salesEst5) * 100
salesSurp6 = (sales6 - salesEst6) / math.abs(salesEst6) * 100
salesSurp7 = (sales7 - salesEst7) / math.abs(salesEst7) * 100

// Calculate sales QoQ change
salesGrowthQoQF = (salesF - sales0) / math.abs(sales0) * 100
salesGrowthQoQ0 = (sales0 - sales1) / math.abs(sales1) * 100
salesGrowthQoQ1 = (sales1 - sales2) / math.abs(sales2) * 100
salesGrowthQoQ2 = (sales2 - sales3) / math.abs(sales3) * 100
salesGrowthQoQ3 = (sales3 - sales4) / math.abs(sales4) * 100
salesGrowthQoQ4 = (sales4 - sales5) / math.abs(sales5) * 100
salesGrowthQoQ5 = (sales5 - sales6) / math.abs(sales6) * 100
salesGrowthQoQ6 = (sales6 - sales7) / math.abs(sales7) * 100
salesGrowthQoQ7 = (sales7 - sales8) / math.abs(sales8) * 100

// Format the sales values in millions or billions
fmtSales(sales) =>
    sales >= 1000000000 ? sales / 1000000000 : sales / 1000000

futureS = fmtSales(salesF)
salesFmt0 = fmtSales(sales0)
salesFmt1 = fmtSales(sales1)
salesFmt2 = fmtSales(sales2)
salesFmt3 = fmtSales(sales3)
salesFmt4 = fmtSales(sales4)
salesFmt5 = fmtSales(sales5)
salesFmt6 = fmtSales(sales6)
salesFmt7 = fmtSales(sales7)
salesFmt8 = fmtSales(sales8)
salesFmt9 = fmtSales(sales9)
salesFmt10 = fmtSales(sales10)
salesFmt11 = fmtSales(sales11)

// Function to fill a table cell with a formatted value
fillCell(_table, _column, _row, _value, _decimalFormat) =>
    // Convert the value to a string with the specified decimal format
    _cellText = str.tostring(_value, _decimalFormat)
    
    // Handle NaN values by displaying 'N/A'
    if _cellText == 'NaN'
        _cellText := 'N/A'
    
    // Determine the background color based on the row index (odd/even)
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? bgColorOdd : bgColorEven
    
    // Fill the specified cell in the table with the formatted text and color
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = tableTextColor, text_size = tableSize)

// Function to fill a table cell with EPS or sales comparison values
fillCellComp(_table, _column, _row, _value1, _value2, _decimalFormat) =>
    // Set default color for positive values
    _c_color = tablePosColor
    
    // Convert both values to strings with the specified decimal format
    _cellText1 = str.tostring(_value1, _decimalFormat)
    _cellText2 = str.tostring(_value2, _decimalFormat)
    
    // Handle NaN values by displaying 'N/A'
    if _cellText1 == 'NaN'
        _cellText1 := 'N/A'
    if _cellText2 == 'NaN'
        _cellText2 := 'N/A'
    
    // Create a comparison string
    _cellText = _cellText1 + ' vs ' + _cellText2
    
    // Determine the background color based on the row index (odd/even)
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? bgColorOdd : bgColorEven
    
    // Fill the specified cell in the table with the comparison text and color
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = tableTextColor, text_size = tableSize)

// Function to fill a table cell with change values
fillCellChg(_table, _column, _row, _value, _isSurp) =>
    // Determine color based on whether it's a surprise and the value
    _c_color = _isSurp ? (_value >= 0 ? posSurpColor : negSurpColor) : (_value >= 0 ? tablePosColor : tableNegColor)
    
    // Initialise the text for the cell based on the value
    _cellText = _value > 999 ? '+999%' : _value < -999 ? '-999%' : _value > 0 ? '+' + str.tostring(_value, '0') + '%' : str.tostring(_value, '0') + '%'
    
    // Handle specific cases for NaN and zero values
    if _cellText == 'NaN%'
        _cellText := 'N/A'
    if _cellText == '+0%'
        _cellText := '0%'
    
    // Handle special cases for specific EPS change values
    if _value == epsChangeHashF or _value == epsChangeHash0 or _value == epsChangeHash1 or _value == epsChangeHash2 or _value == epsChangeHash3 or _value == epsChangeHash4 or _value == epsChangeHash5 or _value == epsChangeHash6 or _value == epsChangeHash7
        _cellText := _value > 999 ? '#+999%' : _value < -999 ? '#-999%' : _value > 0 ? '#' + '+' + str.tostring(_value, '0') + '%' : '#' + str.tostring(_value, '0') + '%'
    
    // Determine the background color for even or odd rows
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? bgColorOdd : bgColorEven
    
    // Fill the specified cell in the table with the change text and color
    table.cell(_table, _column, _row, _cellText, bgcolor = myColor, text_color = _cellText == '0%' or _cellText == 'N/A' ? tableTextColor : _c_color, text_size = tableSize)

// Request total revenue for the current ticker and financial period
rev = request.financial(syminfo.tickerid, 'TOTAL_REVENUE', 'FQ', barmerge.gaps_on, ignore_invalid_symbol = true)

// Function to manage an array by adding a value to the front and removing the last element
updateArray(arrayId, val) =>
    array.unshift(arrayId, val) // Add the new value at the beginning of the array
    array.pop(arrayId) // Remove the last element of the array

// Function to fill a table cell with a date value
fillCellDate(_table, _column, _row, _value) =>
    // Determine the background color based on the row index (odd/even)
    myColor = _row == 10 or _row == 8 or _row == 6 or _row == 4 ? bgColorOdd : bgColorEven
    
    // Fill the specified cell in the table with the date value and color
    table.cell(table_id = _table, column = _column, row = _row, text = _value, bgcolor = myColor, text_color = tableTextColor, text_size = tableSize)

// Initialise an array for storing date values
var dateArray = array.new_int(datasize)

// If revenue data is available, update the date array with the current time
if bool(rev)
    updateArray(dateArray, time)

// Condition to determine if the last EPS values are unchanged
isEPSRep = actualEPS0 == eps1 and standardEPS0 == standardEPS1 and repEPSEst == repEPSEst[1]

// Check if the current bar is the last one and if the display table is enabled
if barstate.islast and displayTable
    // Display EPS
    if tableComp
        if tableEst
            fillCellComp(epsTable, 1, 11, epsF, eps3, '0.00')

        fillCellComp(epsTable, 1, 10, isEPSRep ? na : repEPS, isEPSRep ? na : eps4, '0.00')
        fillCellComp(epsTable, 1, 9, eps1, eps5, '0.00')
        fillCellComp(epsTable, 1, 8, eps2, eps6, '0.00')
        fillCellComp(epsTable, 1, 7, eps3, eps7, '0.00')
        fillCellComp(epsTable, 1, 6, eps4, eps8, '0.00')
        fillCellComp(epsTable, 1, 5, eps5, eps9, '0.00')
        fillCellComp(epsTable, 1, 4, eps6, eps10, '0.00')
        fillCellComp(epsTable, 1, 3, eps7, eps11, '0.00')

    else
        if tableEst
            fillCell(epsTable, 1, 11, epsF, '0.00')

        fillCell(epsTable, 1, 10, isEPSRep ? na : actualEPS0, '0.00')
        fillCell(epsTable, 1, 9, eps1, '0.00')
        fillCell(epsTable, 1, 8, eps2, '0.00')
        fillCell(epsTable, 1, 7, eps3, '0.00')
        fillCell(epsTable, 1, 6, eps4, '0.00')
        fillCell(epsTable, 1, 5, eps5, '0.00')
        fillCell(epsTable, 1, 4, eps6, '0.00')
        fillCell(epsTable, 1, 3, eps7, '0.00')

    // Display EPS YoY Change
    if tableYoY
        fillCellChg(epsTable, 2, 3, na(epsChange7) ? epsChangeHash7 : epsChange7, false)
        fillCellChg(epsTable, 2, 4, na(epsChange6) ? epsChangeHash6 : epsChange6, false)
        fillCellChg(epsTable, 2, 5, na(epsChange5) ? epsChangeHash5 : epsChange5, false)
        fillCellChg(epsTable, 2, 6, na(epsChange4) ? epsChangeHash4 : epsChange4, false)
        fillCellChg(epsTable, 2, 7, na(epsChange3) ? epsChangeHash3 : epsChange3, false)
        fillCellChg(epsTable, 2, 8, na(epsChange2) ? epsChangeHash2 : epsChange2, false)
        fillCellChg(epsTable, 2, 9, na(epsChange1) ? epsChangeHash1 : epsChange1, false)
        fillCellChg(epsTable, 2, 10, isEPSRep ? na : na(epsChange0) ? epsChangeHash0 : epsChange0, false)
        if tableEst
            fillCellChg(epsTable, 2, 11, na(epsChangeF) ? epsChangeHashF : epsChangeF, false)

    // Display EPS QoQ Change
    if tableQoQ
        fillCellChg(epsTable, 3, 3, epsChangeQoQ7, false)
        fillCellChg(epsTable, 3, 4, epsChangeQoQ6, false)
        fillCellChg(epsTable, 3, 5, epsChangeQoQ5, false)
        fillCellChg(epsTable, 3, 6, epsChangeQoQ4, false)
        fillCellChg(epsTable, 3, 7, epsChangeQoQ3, false)
        fillCellChg(epsTable, 3, 8, epsChangeQoQ2, false)
        fillCellChg(epsTable, 3, 9, epsChangeQoQ1, false)
        fillCellChg(epsTable, 3, 10, epsChangeQoQ0, false)
        if tableEst
            fillCellChg(epsTable, 3, 11, epsChangeQoQF, false)

    // Display EPS surprises
    if tableSurp
        fillCellChg(epsTable, 4, 3, epsSurp7, true)
        fillCellChg(epsTable, 4, 4, epsSurp6, true)
        fillCellChg(epsTable, 4, 5, epsSurp5, true)
        fillCellChg(epsTable, 4, 6, epsSurp4, true)
        fillCellChg(epsTable, 4, 7, epsSurp3, true)
        fillCellChg(epsTable, 4, 8, epsSurp2, true)
        fillCellChg(epsTable, 4, 9, epsSurp1, true)
        fillCellChg(epsTable, 4, 10, epsSurp0, true)
        if tableEst
            fillCellChg(epsTable, 4, 11, 0, true)


    // Display sales
    if tableComp
        if tableEst
            fillCellComp(epsTable, 5, 11, futureS, salesFmt3, '0.0')
        fillCellComp(epsTable, 5, 10, isEPSRep ? na : recentEarn and sameSales ? na : salesFmt0, isEPSRep ? na : salesFmt4, '0.0')
        fillCellComp(epsTable, 5, 9, salesFmt1, salesFmt5, '0.0')
        fillCellComp(epsTable, 5, 8, salesFmt2, salesFmt6, '0.0')
        fillCellComp(epsTable, 5, 7, salesFmt3, salesFmt7, '0.0')
        fillCellComp(epsTable, 5, 6, salesFmt4, salesFmt8, '0.0')
        fillCellComp(epsTable, 5, 5, salesFmt5, salesFmt9, '0.0')
        fillCellComp(epsTable, 5, 4, salesFmt6, salesFmt10, '0.0')
        fillCellComp(epsTable, 5, 3, salesFmt7, salesFmt11, '0.0')

    else
        if tableEst
            fillCell(epsTable, 5, 11, futureS, '0.0')
        fillCell(epsTable, 5, 10, isEPSRep ? na : recentEarn and sameSales ? na : salesFmt0, '0.0')
        fillCell(epsTable, 5, 9, salesFmt1, '0.0')
        fillCell(epsTable, 5, 8, salesFmt2, '0.0')
        fillCell(epsTable, 5, 7, salesFmt3, '0.0')
        fillCell(epsTable, 5, 6, salesFmt4, '0.0')
        fillCell(epsTable, 5, 5, salesFmt5, '0.0')
        fillCell(epsTable, 5, 4, salesFmt6, '0.0')
        fillCell(epsTable, 5, 3, salesFmt7, '0.0')

    // Display sales YoY change
    if tableYoY
        fillCellChg(epsTable, 6, 3, salesGrowth7, false)
        fillCellChg(epsTable, 6, 4, salesGrowth6, false)
        fillCellChg(epsTable, 6, 5, salesGrowth5, false)
        fillCellChg(epsTable, 6, 6, salesGrowth4, false)
        fillCellChg(epsTable, 6, 7, salesGrowth3, false)
        fillCellChg(epsTable, 6, 8, salesGrowth2, false)
        fillCellChg(epsTable, 6, 9, salesGrowth1, false)
        fillCellChg(epsTable, 6, 10, isEPSRep ? na : recentEarn and sameSales ? na : actualSalesGrowth0, false)
        if tableEst
            fillCellChg(epsTable, 6, 11, salesGrowthF, false)

    // Display sales QoQ Change
    if tableQoQ
        fillCellChg(epsTable, 7, 3, salesGrowthQoQ7, false)
        fillCellChg(epsTable, 7, 4, salesGrowthQoQ6, false)
        fillCellChg(epsTable, 7, 5, salesGrowthQoQ5, false)
        fillCellChg(epsTable, 7, 6, salesGrowthQoQ4, false)
        fillCellChg(epsTable, 7, 7, salesGrowthQoQ3, false)
        fillCellChg(epsTable, 7, 8, salesGrowthQoQ2, false)
        fillCellChg(epsTable, 7, 9, salesGrowthQoQ1, false)
        fillCellChg(epsTable, 7, 10, isEPSRep ? na : recentEarn and sameSales ? na : salesGrowthQoQ0, false)
        if tableEst
            fillCellChg(epsTable, 7, 11, salesGrowthQoQF, false)

    // Display sales surprises
    if tableSurp
        fillCellChg(epsTable, 8, 3, salesSurp7, true)
        fillCellChg(epsTable, 8, 4, salesSurp6, true)
        fillCellChg(epsTable, 8, 5, salesSurp5, true)
        fillCellChg(epsTable, 8, 6, salesSurp4, true)
        fillCellChg(epsTable, 8, 7, salesSurp3, true)
        fillCellChg(epsTable, 8, 8, salesSurp2, true)
        fillCellChg(epsTable, 8, 9, salesSurp1, true)
        fillCellChg(epsTable, 8, 10, salesSurp0, true)
        if tableEst
            fillCellChg(epsTable, 8, 11, 0, true)

    // Display GM values
    if tableGM
        fillCellChg(epsTable, 9, 3, gm7, false)
        fillCellChg(epsTable, 9, 4, gm6, false)
        fillCellChg(epsTable, 9, 5, gm5, false)
        fillCellChg(epsTable, 9, 6, gm4, false)
        fillCellChg(epsTable, 9, 7, gm3, false)
        fillCellChg(epsTable, 9, 8, gm2, false)
        fillCellChg(epsTable, 9, 9, gm1, false)
        fillCellChg(epsTable, 9, 10, gm0, false)

    // Display ROE values
    if tableROE
        fillCellChg(epsTable, 10, 3, roe7, false)
        fillCellChg(epsTable, 10, 4, roe6, false)
        fillCellChg(epsTable, 10, 5, roe5, false)
        fillCellChg(epsTable, 10, 6, roe4, false)
        fillCellChg(epsTable, 10, 7, roe3, false)
        fillCellChg(epsTable, 10, 8, roe2, false)
        fillCellChg(epsTable, 10, 9, roe1, false)
        fillCellChg(epsTable, 10, 10, roe0, false)

    // Fill table cells with formatted date values (MMM-yy)
    for i = 0 to datasize - 3 by 1
        // Check if the current bar is the last one
        if barstate.islast
            // Fill the date cell in the table using the formatted date from the dateArray
            fillCellDate(epsTable, 0, datasize - i, str.format('{0, date, MMM-yy}', array.get(dateArray, i)))

    // If estimating values are to be shown, fill the estimation date cell
    if tableEst
        fillCellDate(epsTable, 0, 11, str.format('{0, date, MMM-yy}', timeF) + ' est.')

    // Set headings for the EPS table
    table.cell(epsTable, 0, 0, text = 'Quarter', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)
    table.cell(epsTable, 1, 0, text = 'EPS ($)', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)

    // Conditional headings based on table display options
    if tableYoY
        table.cell(epsTable, 2, 0, text = 'YoY', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)
        table.cell(epsTable, 6, 0, text = 'YoY', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)

    if tableQoQ
        table.cell(epsTable, 3, 0, text = 'QoQ', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)
        table.cell(epsTable, 6, 0, text = 'YoY', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)

    if tableSurp
        table.cell(epsTable, 4, 0, text = 'Surp', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)
        table.cell(epsTable, 8, 0, text = 'Surp', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)

    table.cell(epsTable, 5, 0, text = 'Sales (M)', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)

    if tableGM
        table.cell(epsTable, 9, 0, text = 'GM', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)
        
        // If estimating values are to be shown
        if tableEst
            table.cell(epsTable, 9, 11, text = '-', bgcolor = bgColorEven, text_color = tableTextColor, text_size = tableSize)

    if tableROE
        table.cell(epsTable, 10, 0, text = 'ROE', bgcolor = displayTable ? color.white : bgColorOdd, text_color = tableTextColor, text_size = tableSize)

        // If estimating values are to be shown
        if tableEst
            table.cell(epsTable, 10, 11, text = '-', bgcolor = bgColorEven, text_color = tableTextColor, text_size = tableSize)

// Determine the EPS % change for display on the graph
// Check if the hash EPS change is greater than the previous EPS change
epsHashGreater = ta.valuewhen(epsTime, epsChangeHash0, 0) > ta.valuewhen(epsTime, epsChange0, 0)

// If graphQoQ is true, use the QoQ EPS change; otherwise, use selectEPS or the regular EPS change
graphEPSValue = graphQoQ ? epsChangeQoQ0 : epsHashGreater ? ta.valuewhen(epsTime, epsChangeHash0, 0) : ta.valuewhen(epsTime, epsChange0, 0)

// If graphQoQ is true, use the QoQ sales growth; otherwise, use the actual sales growth
graphSalesValue = graphQoQ ? salesGrowthQoQ0 : ta.valuewhen(epsTime, actualSalesGrowth0, 0)

// Set the graph label based on whether sales data should be included
graphLabel = graphSales ? 'EPS & Sales' : 'EPS'

// Format the EPS display text on the graph based on its value
graphEPSText = graphEPSValue > 999 ? '\n+999%' : graphEPSValue > 0 ? '\n+' + str.tostring(graphEPSValue, '0') + '%' : '\n' + str.tostring(graphEPSValue, '0') + '%'
graphEPSText := graphEPSText == '\nNaN%' ? '\nN/A' : graphEPSText == '\n+0%' ? '\n0%' : graphEPSText

// Format the sales display text on the graph based on its value
graphSalesText = (epsTime or epsTime[1]) and sameSales and barstate.islast ? 'NaN%' : graphSalesValue > 999 ? '+999%' : graphSalesValue > 0 ? '+' + str.tostring(graphSalesValue, '0') + '%' : str.tostring(graphSalesValue, '0') + '%'
graphSalesText := graphSalesText == 'NaN%' ? 'N/A' : graphSalesText == '+0%' ? '0%' : graphSalesText

// Plot arrows and labels on the graph based on conditions
if epsTime and graphArrows
    // Create a label for EPS and optionally sales
    graphArrowLabel = label.new(bar_index, bar_index, xloc = xloc.bar_index, yloc = yloc.belowbar, text = graphLabel, style = label.style_triangleup, color = graphArrowColor, textcolor = graphArrowColor, size = graphArrowSize)

    // If sales data is included, create a sales growth label
    if graphSales
        salesGrowthLabel = label.new(bar_index, low, xloc = xloc.bar_index, yloc = yloc.belowbar, text = graphEPSText + ' | ' + graphSalesText, style = label.style_triangleup, color = color.new(color.aqua, 100), textcolor = graphEPSText == '\nN/A' or graphEPSText == '\n0%' ? graphArrowColor : graphEPSValue > -1 ? graphPosColor : graphNegColor, size = graphArrowSize)
    
    // If sales data is not included, create an EPS change label
    else
        epsChangeLabel = label.new(bar_index, low, xloc = xloc.bar_index, yloc = yloc.belowbar, text = graphEPSText, style = label.style_triangleup, color = color.new(color.aqua, 100), textcolor = graphEPSText == '\nN/A' or graphEPSText == '\n0%' ? graphArrowColor : graphEPSValue > -1 ? graphPosColor : graphNegColor, size = graphArrowSize)