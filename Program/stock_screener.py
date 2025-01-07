# Imports
import ast
import datetime as dt
from functools import partial
from fundamentals import *
from helper_functions import get_current_date, generate_end_dates, get_currency, get_df, get_excel_filename, get_infix, get_rs_volume, get_stock_info, stock_market
import multiprocessing
import numpy as np
import pandas as pd
pd.options.mode.chained_assignment = None
from pandas import ExcelWriter as EW
import os
from sklearn.preprocessing import MinMaxScaler
from technicals import *
from tqdm import tqdm
import yfinance as yf

def stoploss_target(stock, entry, entry_date, period=5, max_stoploss=0.08, atr_buffer=0.5, rr=2):
    """
    Calculate the stop loss and target price for a given stock based on its entry price and date.

    Parameters:
    - stock (str): The stock ticker symbol.
    - entry (float): The entry price of the stock.
    - entry_date (str): The date when the stock was purchased in 'YYYY-MM-DD' format.
    - period (int): The number of days to look back for the minimum low price. Default to 5.
    - max_stoploss (float): The maximum stop loss percentage. Default to 0.08 (8%).
    - atr_buffer (float): The buffer to adjust the average true range (ATR) for the stop loss calculation. Default to 0.5.
    - rr (int): The risk-reward ratio for calculating the target price. Default to 2.

    Returns:
    - tuple: A tuple containing the stop loss price, stop loss percentage, target price, and target percentage.
    """

    # Retrieve historical price data for the specified stock starting from the entry date
    df = get_df(stock, entry_date)
    
    # Filter the DataFrame to include only data up to and including the entry date
    df = df[df.index <= entry_date]

    # Calculate the minimum low price over the specified lookback period
    low_min = df["Low"].rolling(window=period).min().iloc[-1]
    
    # Calculate the Average True Range (ATR) for the stock
    atr = ATR(df)["ATR"].iloc[-1]

    # Determine the stop loss price using the entry price and minimum low price
    stoploss = max((1 - max_stoploss) * entry, low_min - atr_buffer * atr)

    # Calculate the stop loss percentage relative to the entry price
    stoploss_pct = (1 - stoploss / entry) * 100

    # Calculate the target price based on the risk-reward ratio
    target = entry + (entry - stoploss) * rr

    # Calculate the target price percentage relative to the entry price
    target_pct = (target / entry - 1) * 100

    # Round the calculated values to two decimal places for prices and one decimal place for percentages
    stoploss = round(stoploss, 2)
    stoploss_pct = round(stoploss_pct, 1)
    target = round(target, 2)
    target_pct = round(target_pct, 1)
    
    return stoploss, stoploss_pct, target, target_pct
    
def EMA_replace(SMA_value, EMA_value):
    """
    Replace SMA value with EMA value if SMA is NaN.

    Parameters:
    - SMA_value (float): The Simple Moving Average value.
    - EMA_value (float): The Exponential Moving Average value.

    Returns:
    - float: The EMA value if SMA is NaN, otherwise the SMA value.
    """

    return EMA_value if np.isnan(SMA_value) else SMA_value

def check_conds_tech(index_name, df):
    """
    Check if the price data meets specified technical conditions based on moving averages.

    Parameters:
    - index_name (str): The name of the index.
    - df (DataFrame): The DataFrame containing price data with 'Close', 'Low', and 'High' columns.

    Returns:
    - conds_tech_data (dict): A dictionary containing the evaluation of technical conditions and relevant data.
    """

    # Current closing price
    current_close = df["Close"].iloc[-1]

    # Define moving average periods
    periods = [5, 20, 50, 200]

    # Calculate the moving averages and store them in the DataFrame
    for i in periods:
        df.loc[:, f"SMA {str(i)}"] = SMA(df, i)
        df.loc[:, f"EMA {str(i)}"] = EMA(df, i)

    # Retrieve the latest moving average values and their slopes
    SMA_5 = df["SMA 5"].iloc[-1]
    SMA_20 = df["SMA 20"].iloc[-1]
    SMA_50 = df["SMA 50"].iloc[-1]
    SMA_200 = df["SMA 200"].iloc[-1]
    SMA_20_slope = df["SMA 20"].diff().iloc[-1]
    SMA_50_slope = df["SMA 50"].diff().iloc[-1]
    SMA_200_slope = df["SMA 200"].diff().iloc[-1]
    EMA_5 = df["EMA 5"].iloc[-1]
    EMA_20 = df["EMA 20"].iloc[-1]
    EMA_50 = df["EMA 50"].iloc[-1]
    EMA_200 = df["EMA 200"].iloc[-1]
    EMA_20_slope = df["EMA 20"].diff().iloc[-1]
    EMA_50_slope = df["EMA 50"].diff().iloc[-1]
    EMA_200_slope = df["EMA 200"].diff().iloc[-1]

    # Calculate the 52-week low and high
    Low = round(min(df["Low"][-252:]), 2)
    High = round(max(df["High"][-252:]), 2)

    # Define technical conditions based on the index name
    if index_name == "^HSI":
        cond_t1 = current_close > EMA_replace(SMA_20, EMA_20) > EMA_replace(SMA_50, EMA_50)
        cond_t2 = current_close > EMA_replace(SMA_200, EMA_200)
        cond_t3 = EMA_replace(SMA_20_slope, EMA_20_slope) > 0
        conds_tech = cond_t1 and cond_t2 and cond_t3
        cond_t4 = None
        cond_t5 = None

    else:
        cond_t1 = current_close > EMA_replace(SMA_50, EMA_50) > EMA_replace(SMA_200, EMA_200)
        cond_t2 = EMA_replace(SMA_50_slope, EMA_50_slope) > 0
        cond_t3 = EMA_replace(SMA_200_slope, EMA_200_slope) > 0
        cond_t4 = current_close >= (1.25 * Low)
        cond_t5 = current_close >= (0.75 * High)
        conds_tech = cond_t1 and cond_t2 and cond_t3 and cond_t4 and cond_t5

    # Prepare the output data with the technical condition results
    conds_tech_data = {
        "conds_tech": conds_tech,
        "cond_t1": cond_t1,
        "cond_t2": cond_t2,
        "cond_t3": cond_t3,
        "cond_t4": cond_t4,
        "cond_t5": cond_t5,
        "current_close": current_close,
        "SMA 5": SMA_5,
        "EMA 5": EMA_5,
        "SMA 20": SMA_20,
        "SMA 20 slope": SMA_20_slope,
        "EMA 20": EMA_20,
        "EMA 20 slope": EMA_20_slope,
        "SMA 50": SMA_50,
        "SMA 50 slope": SMA_50_slope,
        "EMA 50": EMA_50,
        "EMA 50 slope": EMA_50_slope,
        "SMA 200": SMA_200,
        "SMA 200 slope": SMA_200_slope,
        "EMA 200": EMA_200,
        "EMA 200 slope": EMA_200_slope,
        "Low": Low,
        "High": High
    }
    
    return conds_tech_data
    
def check_conds_fund(Y_growth, Q_growth):
    """
    Check if the stock meets specified fundamental conditions.

    Parameters:
    - Y_growth (float): Yearly growth rate.
    - Q_growth (float): Quarterly growth rate.

    Returns:
    - conds_fund, cond_f2, cond_f3 (tuple): A tuple containing a boolean indicating overall condition fulfilment,
           and individual condition results for Y_growth, Q_growth.
    """

    # Check if the yearly growth rate is non-negative
    try:
        cond_f2 = Y_growth >= 0
    except Exception:
        cond_f2 = False

    # Check if the quarterly growth rate is non-negative
    try:
        cond_f3 = Q_growth >= 0
    except Exception:
        cond_f3 = False
    
    # Overall condition is true if all individual conditions are met
    conds_fund = cond_f2 and cond_f3

    return conds_fund, cond_f2, cond_f3

# Check the Minervini conditions for the top performing stocks
def process_stock(stock, index_name, end_date, current_date, stock_dfs, stock_infos, rs_volume_df, backtest=False):
    """
    Process the stock data to check if it meets the Minervini conditions for top-performing stocks.

    Parameters:
    - stock (str): The stock ticker symbol.
    - index_name (str): The name of the index.
    - end_date (str): The end date for the analysis in 'YYYY-MM-DD' format.
    - current_date (str): The current date for analysis in 'YYYY-MM-DD' format.
    - stock_dfs (dict): A dictionary containing DataFrames of stock price data.
    - stock_infos (dict): A dictionary containing stock information.
    - rs_volume_df (DataFrame): DataFrame for relative strength and volume.
    - backtest (bool): Flag to indicate if backtesting is being performed. Default is False.

    Returns:
    - result (dict) or None: A dictionary with relevant stock information if conditions are met, otherwise None.
    """

    # Get the currency of the index
    currency = get_currency(index_name)

    try:
        # Retrieve stock data and information
        df = stock_dfs[stock]
        stock_info = stock_infos[stock]

        # Preprocess stock data
        # Filter stock data based on the end date
        df = df[df.index < end_date]

        # Get relative strength rating and volume SMA 5 rank
        RS_rating, volume_sma5_rank = get_rs_volume(stock, rs_volume_df)

        # Check the technical conditions
        conds_tech_data = check_conds_tech(index_name, df)

        # Extract relevant technical data
        conds_tech = conds_tech_data["conds_tech"]
        current_close = conds_tech_data["current_close"]
        SMA_5 = conds_tech_data["SMA 5"]
        EMA_5 = conds_tech_data["EMA 5"]
        SMA_20 = conds_tech_data["SMA 20"]
        EMA_20 = conds_tech_data["EMA 20"]
        SMA_50 = conds_tech_data["SMA 50"]
        EMA_50 = conds_tech_data["EMA 50"]
        SMA_200 = conds_tech_data["SMA 200"]
        EMA_200 = conds_tech_data["EMA 200"]
        Low = conds_tech_data["Low"]
        High = conds_tech_data["High"]

        # Set conditions based on index name
        if index_name == "^HSI":
            cond_t1 = conds_tech_data["cond_t1"]
            cond_t2 = conds_tech_data["cond_t2"]
            cond_t3 = conds_tech_data["cond_t3"]
        else:
            cond_t1 = conds_tech_data["cond_t1"]
            cond_t2 = conds_tech_data["cond_t2"]
            cond_t3 = conds_tech_data["cond_t3"]
            cond_t4 = conds_tech_data["cond_t4"]
            cond_t5 = conds_tech_data["cond_t5"]

        # Check if the technical conditions are fulfilled
        if conds_tech:
            market_cap = get_market_cap(stock, stock_info, end_date, current_date, backtest=backtest)

            # Fundamental condition: market cap must be greater than 1 billion
            cond_f1 = market_cap != "N/A" and market_cap > 1

            # Check if both technical and fundamental conditions are met
            if conds_tech and cond_f1:
                # Get trailing and forward EPS
                tEPS = stock_info.get("trailingEps", "N/A")
                fEPS = stock_info.get("forwardEps", "N/A")

                # Estimate EPS growth for the next year
                EPS_nextY_growth = round((fEPS - tEPS) / np.abs(tEPS) * 100, 2) if tEPS != "N/A" else None
            
                # Get earnings growth and ROE based on index name
                if index_name == "^HSI":
                    earnings_thisQ_growth = stock_info["earningsQuarterlyGrowth"] * 100
                    ROE = stock_info["returnOnEquity"] * 100
                else:
                    EPS_past5Y_growth, EPS_thisY_growth, EPS_QoQ_growth, ROE = get_fundamentals(stock, end_date, current_date, backtest=backtest)

                # Check fundamental conditions
                if index_name == "^HSI":
                    conds_fund, cond_f2, cond_f3 = check_conds_fund(EPS_nextY_growth, earnings_thisQ_growth)
                else:
                    conds_fund, cond_f2, cond_f3 = check_conds_fund(EPS_thisY_growth, EPS_QoQ_growth)
                
                if conds_fund:
                    # Gather additional stock information
                    sector = stock_info.get("sector", "N/A")
                    industry = stock_info.get("industry", "N/A")

                    # Get quarterly growths for the stock
                    EPS_thisQ_growth, EPS_last1Q_growth, EPS_last2Q_growth = get_lastQ_growths(stock, index_name, end_date, current_date, backtest=backtest)

                    # Calculate stock volatility
                    data = get_volatility(df)
                    volatility_20 = data["Volatility 20"].iloc[-1]
                    volatility_60 = data["Volatility 60"].iloc[-1]
                    
                    # MVP/VCP condition calculations
                    data = MVP_VCP(df)
                    MVP = data["MVP"].iloc[-1]
                    M_past60 = data["M past 60"].iloc[-1]
                    MV_past60 = data["MV past 60"].iloc[-1]
                    MP_past60 = data["MP past 60"].iloc[-1]
                    MVP_past60 = data["MVP past 60"].iloc[-1]
                    MVP_rating = data["MVP Rating"].iloc[-1]
                    VCP = data["VCP"].iloc[-1]
                    pivot_breakout = data["Pivot breakout"].iloc[-1]
                    volume_shrink = data["Volume shrinking"].iloc[-1]

                    # Get the next earning date
                    try:
                        earning_dates = get_earning_dates(stock, current_date)
                        next_earning_date = min([earning_date for earning_date in earning_dates if earning_date > end_date])
                    except Exception as e:
                        print(f"Error getting next earning date {stock}: {e}\n")
                        next_earning_date = "N/A"

                    # Compile relevant stock information into a result dictionary
                    result = {
                        "Stock": stock,
                        "RS Rating": RS_rating,
                        "Volume SMA 5 Rank": volume_sma5_rank,
                        "Close": round(current_close, 2),
                        "Volatility 20 (%)": round(volatility_20 * 100, 2),
                        "Volatility 60 (%)": round(volatility_60 * 100, 2),
                        "SMA 5": EMA_replace(SMA_5, EMA_5),
                        "SMA 20": EMA_replace(SMA_20, EMA_20),
                        "SMA 50": EMA_replace(SMA_50, EMA_50),
                        "SMA 200": EMA_replace(SMA_200, EMA_200),
                        "SMA 5/20 Ratio": round(SMA_5 / SMA_20, 2),
                        "SMA 5/50 Ratio": round(SMA_5 / SMA_50, 2),
                        "MVP": MVP,
                        "M past 60": M_past60,
                        "MV past 60": MV_past60,
                        "MP past 60": MP_past60,
                        "MVP past 60": MVP_past60,
                        "MVP Rating": MVP_rating,
                        "VCP": VCP,
                        "Pivot Preakout": pivot_breakout,
                        "Volume Shrinking": volume_shrink,
                        "52 Week Low": Low,
                        "52 Week High": High,
                        f"Market Cap (B, {currency})": market_cap,
                        "EPS past 5Y (%)": EPS_past5Y_growth if index_name != "^HSI" else None,
                        "EPS this Y (%)": EPS_thisY_growth if index_name != "^HSI" else None,
                        "EPS Q/Q (%)": EPS_QoQ_growth if index_name != "^HSI" else None,
                        "ROE (%)": ROE,
                        "EPS this Q (%)": EPS_thisQ_growth if index_name != "^HSI" else None,
                        "EPS last 1Q (%)": EPS_last1Q_growth if index_name != "^HSI" else None,
                        "EPS last 2Q (%)": EPS_last2Q_growth if index_name != "^HSI" else None,
                        "Next Earning Date": next_earning_date,
                        "Sector": sector,
                        "Industry": industry,
                    }
                    if not backtest:
                        result.update({
                            "Trailing EPS": tEPS,
                            "Forward EPS": fEPS,
                            "Estimated EPS growth (%)": EPS_nextY_growth,
                        })

                    if index_name == "^HSI":
                        result.update({
                            "Earnings this Q (%)": earnings_thisQ_growth,
                        })

                    return result
                    
    except Exception as e:
        print(f"Error for {stock}: {e}\n")

        return None
    
def EM_rating(index_name, df, factors, cap_threshold=10):
    """
    Calculate the EM rating for stocks based on specified factors and market capitalization.

    Parameters:
    - index_name (str): The name of the index.
    - df (DataFrame): The DataFrame containing stock data.
    - factors (list): A list of factors for weighting the EM rating calculation.
    - cap_threshold (float): The market cap threshold for categorising stocks. Default is 10 billion.

    Returns:
    - DataFrame: The updated DataFrame with the calculated EM Rating.
    """

    # Define the target columns based on the index name
    if index_name == "^HSI":
        cols = ["MVP Rating", "Estimated EPS growth (%)", "Earnings this Q (%)"]
    else:
        cols = ["MVP Rating", "EPS this Y (%)", "EPS Q/Q (%)"]

    df_copy = df.copy()

    # Extract the number of stocks
    stocks_num = df_copy.shape[0]

    # Skip processing if the number of stocks is less than or equal to 1
    if stocks_num <= 1:
        return df

    # Initialise the MinMaxScaler
    scaler = MinMaxScaler()

    # Normalise the first column
    df_copy[cols[0]] = scaler.fit_transform(df_copy[cols[0]].values.reshape(-1, 1))

    # Apply log1p and MinMaxScaler to the last two columns
    for col in cols[1:]:
        min_value = df_copy[col].min()
        if min_value < 0:
            # Adjust the values before applying log1p to avoid negative values
            df_copy[col] = np.log1p(df_copy[col] - min_value)
        else:
            df_copy[col] = np.log1p(df_copy[col])
            
        # Normalise the updated column
        df_copy[col] = scaler.fit_transform(df_copy[col].values.reshape(-1, 1))

    # Calculate the weighted average for each row and multiply by 100 to get the EM Rating
    df["EM Rating"] = (df_copy[cols] * factors / np.sum(factors)).sum(axis=1) * 100

    # Identify the column corresponding to market capitalisation
    market_cap_col = [col for col in df.columns if re.match(r"Market Cap \(B, .*", col)]
    if market_cap_col:
        market_cap_col = market_cap_col[0]

        # Split the DataFrame based on cap_threshold
        if cap_threshold:
            df_high_cap = df[df[market_cap_col] >= cap_threshold]
            df_low_cap = df[df[market_cap_col] < cap_threshold]

            # Sort both DataFrames by EM Rating in descending order
            df_high_cap = df_high_cap.sort_values("EM Rating", ascending=False)
            df_low_cap = df_low_cap.sort_values("EM Rating", ascending=False)

            # Combine the two DataFrames
            df = pd.concat([df_high_cap, df_low_cap])
        else:
            # Sort the EM ratings in descending order if no cap_threshold is provided
            df = df.sort_values("EM Rating", ascending=False)

    return df

def select_stocks(end_dates, current_date, index_name, index_dict, 
                  period_hk, period_us, RS, HKEX_all, NASDAQ_all, factors, backtest):
    """
    Select stocks based on their performance and criteria for a given index.

    Parameters:
    - end_dates (list): List of end dates for analysis.
    - current_date (str): The current date for analysis in 'YYYY-MM-DD' format.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - period_hk (int): The period for HK stocks.
    - period_us (int): The period for US stocks.
    - RS (float): Relative strength threshold.
    - HKEX_all (list): List of all HKEX stocks.
    - NASDAQ_all (bool): If True, include all stocks of NASDAQ.
    - factors (list): A list of factors for weighting.
    - backtest (bool): Flag to indicate if backtesting is being performed.

    Returns:
    - None: Exports results to an Excel file.
    """

    # Select the appropriate period based on the index name
    if index_name == "^HSI":
        period = period_hk
        RS = RS - 10
    else:
        period = period_us

    # Get the infix for filenames
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Set the result folder based on backtest flag
    if backtest:
        result_folder = "Backtest"
    else:
        result_folder = "Result"

    # Remove end dates for which files already exist
    for end_date in end_dates.copy():
        filename = get_excel_filename(end_date, index_name, index_dict, period_hk, period_us, RS, NASDAQ_all, result_folder)
        if os.path.isfile(filename):
            end_dates.remove(end_date)

    # Get current stocks in the market
    stocks_current = stock_market(current_date, current_date, index_name, HKEX_all, NASDAQ_all)

    # Fetch price data for current stocks
    dfs = {}
    for stock in tqdm(stocks_current, desc="Fetching stock price data"):
        dfs[stock] = get_df(stock, current_date)

    # Initialise stock_infos as an empty dictionary
    stock_infos = {}

    # Process each end date
    for end_date in tqdm(end_dates, desc="Processing end dates"):
        # Get stocks for the current end date
        stocks = stock_market(end_date, current_date, index_name, HKEX_all, NASDAQ_all)

        # Fetch data for any new stocks
        for stock in tqdm(set(stocks) - set(dfs.keys()), desc=f"Fetching stock price data for {end_date}"):
            dfs[stock] = get_df(stock, current_date) 

        # Get index price data and filter by end date
        index_df = get_df(index_name, current_date)
        index_df = index_df[index_df.index < end_date]

        # Calculate the percent change of the index
        index_df["Percent Change"] = index_df["Close"].pct_change()

        # Calculate the total return of the index
        index_return = (index_df["Percent Change"] + 1).tail(period).cumprod().iloc[-1]
        index_shortName = index_dict[f"{index_name}"]
        print(f"Return for {index_shortName} between {index_df.index[-period].strftime('%Y-%m-%d')} and {end_date}: {index_return:.2f}")

        # Create relative strength and volume dataframes
        rs_df, volume_df, rs_volume_df = create_rs_volume_df(stocks, dfs, end_date, period, index_return, index_shortName, result_folder, infix, backtest)
        
        # Filter stocks based on criteria
        if index_name == "^HSI":
            rs_df = rs_df[rs_df["RS"] >= RS]
            volume_df = volume_df[(volume_df["Volume SMA 5 Rank"] <= 1000) | (volume_df["Volume SMA 20 Rank"] <= 1000)]
            rs_stocks = set(rs_df["Stock"])
            volume_stocks = set(volume_df["Stock"])
            stocks = list(rs_stocks.intersection(volume_stocks))
        else:
            rs_df = rs_df[rs_df["RS"] >= RS]
            stocks = rs_df["Stock"]

        # Create a pool of worker processes to fetch the stock price data
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            partial_get_df = partial(get_df, end_date=current_date)
            stock_dfs = {stock: df for stock, df in zip(stocks, list(tqdm(pool.imap(partial_get_df, stocks, 1), total=len(stocks), desc="Fetching stock price data")))}
        
        # Update stock_infos for stocks that are not already present
        stock_infos.update({stock: get_stock_info(stock) for stock in tqdm(set(stocks) - set(stock_infos.keys()), desc=f"Fetching stock info for {end_date}")})

        # Process each stock and compile results
        export_data = [process_stock(stock, index_name, end_date, current_date, stock_dfs, stock_infos, rs_volume_df, backtest=backtest) for stock in tqdm(stocks)]
        export_data = [row for row in export_data if row is not None]
        df = pd.DataFrame(export_data)
        df = EM_rating(index_name, df, factors)

        # Calculate means and standard deviations for volatility
        volatility_20_mean = df["Volatility 20 (%)"].mean()
        volatility_60_mean = df["Volatility 60 (%)"].mean()
        volatility_20_sd = df['Volatility 20 (%)'].std()
        volatility_60_sd = df['Volatility 60 (%)'].std()

        # Calculate z-scores for volatility
        volatility_20_zscore = (df["Volatility 20 (%)"] - volatility_20_mean) / volatility_20_sd
        volatility_60_zscore = (df["Volatility 60 (%)"] - volatility_60_mean) / volatility_60_sd

        # Insert z-scores into the DataFrame
        df.insert(df.columns.get_loc("Volatility 20 (%)") + 1, "Volatility 20 Z-Score", volatility_20_zscore)
        df.insert(df.columns.get_loc("Volatility 60 (%)") + 1, "Volatility 60 Z-Score", volatility_60_zscore)

        # Format end date for folder naming
        end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%y")

        # Create a folder for results if it does not exist
        folder = os.path.join(result_folder, f"{end_date_fmt}")
        if not os.path.exists(folder):
            os.makedirs(folder)

        # Export results to an Excel file
        filename = get_excel_filename(end_date, index_name, index_dict, period_hk, period_us, RS, NASDAQ_all, result_folder)
        writer = EW(filename)
        df.to_excel(writer, sheet_name="Sheet1", index=False)
        writer._save()

def create_stock_dict(end_dates, index_name, index_dict, NASDAQ_all, factors, RS=90, period=252, cap_threshold=1, backtest=False, recreate_dict=False):
    """
    Create a dictionary of selected stocks based on analysis criteria.

    Parameters:
    - end_dates (list): List of end dates for analysis.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): If True, include all stocks of NASDAQ.
    - factors (list): A list of factors for weighting.
    - RS (float): Relative strength threshold. Default is 90.
    - period (int): Analysis period in days. Default is 252.
    - cap_threshold (float): Minimum market capitalisation threshold. Default is 1 billion.
    - backtest (bool): Flag to indicate if backtesting is being performed.
    - recreate_dict (bool): If True, recreate the dictionary even if it already exists. Default to False.

    Returns:
    - None: Exports results to a text file.
    """

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Initialise an empty dictionary to store the selected stocks
    stock_dict = {}

    # Define the result folder based on backtest flag
    if backtest:
        result_folder = "Backtest"
    else:
        result_folder = "Result"

    # Define the market cap label based on cap_threshold
    cap_label = f"cap{cap_threshold}" if cap_threshold else ""

    # Load the stock dictionary if it exists
    stock_dict_folder = os.path.join(result_folder, "Stock dict")
    stock_dict_filename = os.path.join(stock_dict_folder, f"{infix}stock_dict{factors}{cap_label}.txt")
    if os.path.isfile(stock_dict_filename):
        with open(stock_dict_filename, "r") as file:
            stock_dict = ast.literal_eval(file.read())

    if not os.path.isfile(stock_dict_filename) or recreate_dict:
        # Iterate over all end dates except the last one
        for end_date in end_dates[:-1]:
            # Format the end date for file naming
            end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%y")

            # Define the filename for the screened stocks
            filename = os.path.join(result_folder, f"{end_date_fmt}/{infix}stock_{end_date_fmt}period{period}RS{RS}.xlsx")

            # Read the data of the screened stocks
            df = pd.read_excel(filename)

            # Calculate the EM rating
            df = EM_rating(index_name, df, factors)

            # Identify the column of market cap
            cap_col = [col for col in df.columns if re.match(r"Market Cap \(B, .*", col)]
            if cap_col:
                cap_col = cap_col[0]

                # Apply market cap threshold if required
                if cap_threshold:
                    df = df[df[cap_col] >= cap_threshold]
            else:
                raise ValueError("'Market Cap' column not found in the dataframe.")

            # Extract the number of stocks
            stocks_num = df.shape[0]

            # Store top stocks or None if no stocks found
            if stocks_num == 0:
                stock_dict[end_date] = None
            else:
                stocks = df["Stock"].tolist()
                stock_dict[end_date] = stocks

            # Sort stock_dict by date
            stock_dict = dict(sorted(stock_dict.items(), key=lambda x: dt.datetime.strptime(x[0], "%Y-%m-%d")))

        # Write the stock_dict to a file
        with open(stock_dict_filename, "w") as file:
            file.write(str(stock_dict))

# Main function
def main():
    # Start of the program
    start = dt.datetime.now()
    print(start, "\n")

    # Define the paths for the folders
    folders = ["Price data", "Result", "Result/Figure", "Backtest"]
    
    # Check if the folders exist, create them if they do not
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    # Variables
    HKEX_all = True
    NASDAQ_all = True
    period_hk = 60 # Period for HK stocks
    period_us = 252 # Period for US stocks 
    RS = 90
    factors = [0.05, 0.8, 0.15]
    backtest = False

    # Index
    index_name = "^GSPC"
    index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite"}

    # Get the current date
    current_date = get_current_date(start, index_name)

    # Create the end dates
    # end_dates = generate_end_dates(7, current_date, interval="1w")
    # end_dates.append(current_date)
    end_dates = [current_date]

    # Stock selection
    select_stocks(end_dates, current_date, index_name, index_dict, 
                  period_hk, period_us, RS, HKEX_all, NASDAQ_all, factors, backtest)

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()