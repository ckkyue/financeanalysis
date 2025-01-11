# Import
import datetime as dt
from helper_functions import get_current_date, get_df, get_excel_filename, stock_market
import openpyxl
from openpyxl.styles import Font, PatternFill
from pandas import ExcelWriter as EW
from plot import *
import scipy.stats as stats
from technicals import *

# # Display the whole dataframe
# pd.set_option("display.max_rows", None)
# pd.set_option("display.max_columns", None)

def screen_excel(excel_filename, sector_excel_classification):
    """
    Screen stocks from an Excel file and apply formatting based on specified criteria.

    Parameters:
    - excel_filename (str): The path to the Excel file containing stock data.
    - sector_excel_classification (DataFrame): A DataFrame containing sector classifications.

    This function highlights cells based on the following criteria:
    - Volatility Z-Scores: Text colour changes based on thresholds.
    - Sector classification: Cells are highlighted based on sector performance.
    - MVP designation: Text colour changes to green for "MVP" entries.
    - VCP status: Cells are highlighted for entries marked as True.
    """

    # Get the classified sectors
    sectors_excel_leading = sector_excel_classification["Leading"]
    sectors_excel_improving = sector_excel_classification["Improving"]
    sectors_excel_weakening = sector_excel_classification["Weakening"]
    sectors_excel_lagging = sector_excel_classification["Lagging"]

    # Load the workbook and select the active sheet
    workbook = openpyxl.load_workbook(excel_filename)
    sheet = workbook.active

    # Define fill colours for highlighting
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    orange_fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
    red_font = Font(color="FF0000")
    green_font = Font(color="008000")

    # Find the index of relevant columns
    stock_col_index = None
    volatility20_col_index = None
    volatility60_col_index = None
    mvp_col_index = None
    vcp_col_index = None
    sector_col_index = None
    
    for cell in sheet[1]: # Assuming the first row contains headers
        if cell.value == "Stock":
            stock_col_index = cell.column
        elif cell.value == "Volatility 20 Z-Score":
            volatility20_col_index = cell.column
        elif cell.value == "Volatility 60 Z-Score":
            volatility60_col_index = cell.column
        elif cell.value == "MVP":
            mvp_col_index = cell.column
        elif cell.value == "VCP":
            vcp_col_index = cell.column
        elif cell.value == "Sector":
            sector_col_index = cell.column

    # Highlight the cells of each row based on the criteria
    if sector_col_index is not None:
        for row in sheet.iter_rows(min_row=2): # Start from the second row
            volatility20_cell = row[volatility20_col_index - 1]
            volatility60_cell = row[volatility60_col_index - 1]
            sector_cell = row[sector_col_index - 1]
            mvp_cell = row[mvp_col_index - 1]
            vcp_cell = row[vcp_col_index - 1]
            
            # Change text colour to red if Volatility 20 Z-Score exceeds 2
            if volatility20_cell.value > 2:
                volatility20_cell.font = red_font
            elif volatility20_cell.value < - 1:
                volatility20_cell.font = green_font

            # Change text colour to red if Volatility 60 Z-Score exceeds 2
            if volatility60_cell.value > 2:
                volatility60_cell.font = red_font
            elif volatility60_cell.value < - 1:
                volatility60_cell.font = green_font

            # Highlight the sector cell based on performance classification
            if sector_cell.value in sectors_excel_leading + sectors_excel_improving:
                sector_cell.fill = yellow_fill
            elif sector_cell.value in sectors_excel_lagging + sectors_excel_weakening:
                sector_cell.fill = red_fill

            # Change text colour to green if marked as MVP
            if mvp_cell.value == "MVP":
                mvp_cell.font = green_font

            # Highlight the cell if VCP is True
            if vcp_cell.value == True:
                vcp_cell.fill = orange_fill

    # Save the changes to the Excel file
    workbook.save(excel_filename)
    print(f"Changes made to the Excel file {excel_filename}.")

def retracement_excel(excel_filename, end_date, col_min="Low", col_max="High", period=5, buffer=15):
    """
    Updates the Excel file with the calculated SMA 5 slopes, retracement values,
    and their respective z-scores.

    Parameters:
    - excel_filename (str): The path to the Excel file containing stock data.
    - end_date (str): The end date for stock data retrieval in "YYYY-MM-DD" format.
    - col_min (str): The name of the column for minimum values. Default to "Low".
    - col_max (str): The name of the column for maximum values. Default to "High".
    - period (int): The period for local extrema calculations. Default to 5.
    - buffer (int): The buffer for retracement calculations. Default to 15.

    This function updates the Excel file with the calculated SMA 5 slopes, retracement values,
    and their respective z-scores.
    """

    # Read the screened stocks from the Excel file
    df = pd.read_excel(excel_filename)

    # Initialise lists to store retracement values and SMA 5 slopes
    retracements = []
    SMA_5_slopes = []

    # Get the list of stocks
    stocks = df["Stock"].tolist()

    # Iterate over all stocks
    for stock in stocks:
        data = get_df(stock, end_date) # Retrieve stock data
        data = get_local_extrema(data, col_min=col_min, col_max=col_max, period=period)
        data["Percent Change"] = data["Close"].pct_change()
        data["Percent Change SMA 5"] = SMA(data, 5, col="Percent Change") # Calculate SMA for percent change
        SMA_5_slope = data["Percent Change SMA 5"].iloc[-1] # Get the last SMA value
        SMA_5_slopes.append(SMA_5_slope)

        # Calculate retracement values
        local_min1, local_max, retracement = calculate_retracement(data, col_min=col_min, col_max=col_max, buffer=buffer)
        retracements.append(retracement)

    # Convert lists to numpy arrays
    SMA_5_slopes = np.array(SMA_5_slopes)
    SMA_5_slopes_zscore = stats.zscore(SMA_5_slopes)

    # Calculate z-scores for SMA 5 slopes and retracements
    retracements = np.array(retracements)
    retracements_zscore = stats.zscore(retracements)

    # Overwrite or insert the calculated values into the DataFrame
    if "SMA 5 Slope (%)" in df.columns:
        df["SMA 5 Slope (%)"] = np.round(SMA_5_slopes * 100, 2)
    else:
        df.insert(df.columns.get_loc("Close") + 1, "SMA 5 Slope (%)", np.round(SMA_5_slopes * 100, 2))

    if "SMA 5 Slope Z-Score" in df.columns:
        df["SMA 5 Slope Z-Score"] = np.round(SMA_5_slopes * 100, 2)
    else:
        df.insert(df.columns.get_loc("SMA 5 Slope (%)") + 1, "SMA 5 Slope Z-Score", SMA_5_slopes_zscore)
    
    if "Retracement (%)" in df.columns:
        df["Retracement (%)"] = np.round(retracements * 100, 2)
    else:
        df.insert(df.columns.get_loc("SMA 5 Slope (%)") + 1, "Retracement (%)", np.round(retracements * 100, 2))

    if "Retracement Z-Score" in df.columns:
        df["Retracement Z-Score"] = retracements_zscore
    else:
        df.insert(df.columns.get_loc("Retracement (%)") + 1, "Retracement Z-Score", retracements_zscore)

    # Save the changes to the Excel file
    writer = EW(excel_filename)
    df.to_excel(writer, sheet_name="Sheet1", index=False)
    writer._save()
    print(f"Changes made to the Excel file {excel_filename}.")

# Main function
def main():
    # Start of the program
    start = dt.datetime.now()

   # Variables
    HKEX_all = False
    NASDAQ_all = True
    period_hk = 60 # Period for HK stocks
    period_us = 252 # Period for US stocks
    RS = 90

    # Index
    index_name = "^GSPC"
    index_names = ["^HSI", "^GSPC", "^IXIC", "^DJI", "IWM", "FFTY", "QQQE", "GC=F"]
    index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite", "^DJI": "Dow Jones Industrial Average", 
                  "IWM": "iShares Russell 2000 ETF", "FFTY": "Innovator IBD 50 ETF", "QQQE": "NASDAQ-100 Equal Weighted ETF", 
                  "KWEB": "KraneShares CSI China Internet ETF", "GC=F": "Gold"}
     
    # Sectors
    sectors = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLV", 
            "XLI", "XLB", "XLRE", "XLK", "XLU"]
    sector_dict = {"XLC": "Communication Services", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", 
                "XLE": "Energy", "XLF": "Financials", "XLV": "Health Care", 
                "XLI": "Industrials", "XLB": "Materials", "XLRE": "Real Estate", 
                "XLK": "Technology", "XLU": "Utilities"}
    sector_excel_dict = {"XLC": "Communication Services", "XLY": "Consumer Cyclical", "XLP": "Consumer Defensive", 
                "XLE": "Energy", "XLF": "Financial Services", "XLV": "Healthcare", 
                "XLI": "Industrials", "XLB": "Basic Materials", "XLRE": "Real Estate", 
                "XLK": "Technology", "XLU": "Utilities"}
    
    # Define the result folder
    result_folder = "Result"

    # Get the current date
    current_date = get_current_date(start, index_name)
    
    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    plot_all = True
    if plot_all:
        # Iterate over all indices and sectors
        for ticker in index_names + sectors:
            # Get the price data of the tickers
            df = get_df(ticker, current_date)

            # Visualize the closing price history of the ticker
            plot_close(ticker, df, MVP_VCP=False, save=True)

    sector_rotation = True
    if sector_rotation:
        # Calculate the JdK RS-Ratio and Momentum
        index_df = get_JdK(index_names + sectors, index_df, current_date)

        # Initialize two empty dictionaries to store the classified sectors
        sector_classification = {
            "Leading": [],
            "Weakening": [],
            "Improving": [],
            "Lagging": []
        }

        sector_excel_classification = {
            "Leading": [],
            "Weakening": [],
            "Improving": [],
            "Lagging": []
        }

        # Iterate over all sectors
        for sector in sectors:
            rs_ratio = index_df[f"{sector} JdK RS-Ratio"].iloc[-1]
            rs_momentum = index_df[f"{sector} JdK RS-Momentum"].iloc[-1]

            if rs_ratio >= 100:
                if rs_momentum >= 100:
                    sector_classification["Leading"].append(sector_dict[sector])
                    sector_excel_classification["Leading"].append(sector_excel_dict[sector])
                else:
                    sector_classification["Weakening"].append(sector_dict[sector])
                    sector_excel_classification["Weakening"].append(sector_excel_dict[sector])
            else:
                if rs_momentum > 100:
                    sector_classification["Improving"].append(sector_dict[sector])
                    sector_excel_classification["Improving"].append(sector_excel_dict[sector])
                else:
                    sector_classification["Lagging"].append(sector_dict[sector])
                    sector_excel_classification["Lagging"].append(sector_excel_dict[sector])

        # Print the classified sectors
        for category, sectors_list in sector_classification.items():
            print(f"{category} sectors: {', '.join(sectors_list)}")

        # Plot the relative rotation graph
        plot_rrg(sectors, sector_dict, index_df, "sector", save=True)

    plot_all_jdk = True
    if plot_all_jdk:
        # Iterate over all sectors
        for sector in sectors:
            # Plot the JdK RS-Ratio and Momentum of the sector
            plot_JdK(sector, sector_dict, index_df, save=True)

    sector_selected = True
    if sector_selected:
        # Plot the sectors of the selected stocks
        plot_sector_selected(current_date, "^GSPC", index_dict, NASDAQ_all=NASDAQ_all, save=True)
    
    hkex_retracement = False
    if hkex_retracement:
        # Get the Excel filename
        excel_filename = get_excel_filename(current_date, "^HSI", index_dict, period_hk, period_us, RS, NASDAQ_all, result_folder)

        retracement_excel(excel_filename, current_date)

    screen_us = True
    if screen_us:
        # Get the Excel filename
        excel_filename = get_excel_filename(current_date, "^GSPC", index_dict, period_hk, period_us, RS, NASDAQ_all, result_folder)

        # Screen the stocks from Excel file
        screen_excel(excel_filename, sector_excel_classification)

    screen_hk = False
    if screen_hk:
        # Get the Excel filename
        excel_filename = get_excel_filename(get_current_date(start, "^HSI"), "^HSI", index_dict, period_hk, period_us, RS - 10, NASDAQ_all, result_folder)

        # Screen the stocks from Excel file
        screen_excel(excel_filename, sector_excel_classification)

    plot_marketbreadth = True
    if plot_marketbreadth:
        # Get the list of tickers of stock market
        index_df = get_df(index_name, current_date)
        tickers = stock_market(current_date, current_date, index_name, HKEX_all, False)

        # Calculate the market breadth indicators
        index_df = market_breadth(current_date, index_df, tickers)

        # Save the data of the index to a .csv file
        index_filename = f"Price data/{index_name}_{current_date}.csv"
        index_df.to_csv(index_filename)

        # Visualize the closing price history and other technical indicators
        plot_market_breadth(index_name, index_df, tickers, save=True)
        plot_close(index_name, index_df, MVP_VCP=False)
        plot_MFI_RSI(index_name, index_df, save=True)
    
    plot_vix = True
    if plot_vix:
        # Get the price data of CBOE Volatility Index (VIX)
        vix_df = get_df("^VIX", current_date)

        # Get the current high of VIX
        vix_current_high = round(vix_df["High"].iloc[-1], 2)

        # Calculate SMA 5
        vix_df["SMA 5"] = SMA(vix_df, 5)
        vix_sma5 = vix_df["SMA 5"].iloc[-1]

        # Define the exit indicator based on VIX value
        if vix_current_high < 26 and vix_sma5 <= 0:
            vix_colour = "Green"
        elif 26 < vix_current_high < 30 or vix_sma5 > 0:
            vix_colour = "Yellow"
        elif vix_current_high > 30:
            vix_colour = "Red"

        # Plot the closing price history of VIX
        plot_close("^VIX", vix_df, save=True)

        # Print the exit indicator
        print(f"Current VIX: {vix_current_high} ({vix_colour})")

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()