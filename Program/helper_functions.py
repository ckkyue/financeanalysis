# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd
import os
import re
from requests_ratelimiter import LimiterSession
from scipy.stats import linregress
import yfinance as yf

def check_DST(start):
    """
    Determines if a given time is within the Daylight Saving Time (DST) period in the USA.

    Parameters:
    - start (datetime): The datetime object to check.

    Returns:
    - bool: True if the date is within DST, False otherwise.
    """

   # Get the current year
    year = start.year

    # Calculate the second Sunday in March
    march1 = dt.datetime(year, 3, 1)
    march_sun2 = march1 + dt.timedelta(days=(6 - march1.weekday()) % 7) + dt.timedelta(weeks=1)

    # Calculate the first Sunday in November
    nov1 = dt.datetime(year, 11, 1)
    nov_sun1 = nov1 + dt.timedelta(days=(6 - nov1.weekday()) % 7)

    return march_sun2 <= start <= nov_sun1

def get_current_date(start, index_name):
    """
    Get the current date based on the provided datetime and stock index name.

    Parameters:
    - start (datetime): The datetime object to evaluate.
    - index_name (str): The name of the stock index.

    Returns:
    - str: The formatted date in 'YYYY-MM-DD' format.
    """

    # Always revert to the previous day for Sunday
    if start.weekday() == 6:
        return (start - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Handle Saturday
    if start.weekday() == 5:
        return start.strftime("%Y-%m-%d")

    # Adjust based on time and DST
    dst_offset = 0 if check_DST(start) else 1
    hour_cutoff = 16 if index_name == "^HSI" else 4 + dst_offset

    if index_name == "^HSI":
        if start.hour >= hour_cutoff:
            return (start + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            return start.strftime("%Y-%m-%d")
    else:
        if start.hour >= hour_cutoff:
            return start.strftime("%Y-%m-%d")
        else:
            return (start - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    
def generate_end_dates(years, current_date, interval="1m", index_name="^GSPC"):
    """
    Generate a list of end dates based on a specified interval and a starting date.

    Parameters:
    - years (int): The number of years to look back from the current date.
    - current_date (str): The current date in "YYYY-MM-DD" format.
    - interval (str): The duration for generating end dates in the format '<number><unit>'.
                      Units can be 'w' (weeks), 'm' (months), or 'y' (years). Default is '1m'.
    - index_name (str): The name of the index for which to fetch price data. Default is '^GSPC'.

    Returns:
    - list: A list of end dates as strings in "YYYY-MM-DD" format, or None if an error occurs.
    """

    # Validate the interval format
    match = re.match(r"(\d+)([a-zA-Z])", interval)
    if not match:
        raise ValueError("Input must match the format '<number><unit>'.")
    
    number = int(match.group(1))
    unit = match.group(2)

    if number < 0:
        raise ValueError("Number must be a non-negative integer.")
        
    if unit not in ["w", "m", "y"]:
        raise ValueError("Unit must be one of 'w' (weeks), 'm' (months), or 'y' (years).")

    try:
        # Parse the current date
        current = dt.datetime.strptime(current_date, "%Y-%m-%d")

        # Calculate the target date by subtracting the specified number of years
        target_date = current - relativedelta(years=years)

        # Set the target date to the first day of the month
        target_date = target_date.replace(day=1)

        # Retrieve the price data for the specified index
        df = get_df(index_name, current_date)

        # Initialise the list to hold end dates
        end_dates = []
        current_date_int = target_date

        # Determine the increment based on the specified unit
        increment = {"w": relativedelta(weeks=number), 
                     "m": relativedelta(months=number), 
                     "y": relativedelta(years=number)
                     }[unit]

        # Loop to generate end dates until the current date
        while current_date_int <= current:
            if unit == "w":
                week_start = current_date_int
                week_end = week_start + relativedelta(weeks=1, days=-1)
                first_trading_date = df.loc[(df.index >= week_start) & (df.index <= week_end)].index.min()
            elif unit == "m":
                month_start = current_date_int
                month_end = month_start + relativedelta(months=1, days=-1)
                first_trading_date = df.loc[(df.index >= month_start) & (df.index <= month_end)].index.min()
            elif unit == "y":
                year_start = current_date_int
                year_end = year_start + relativedelta(years=1, days=-1)
                first_trading_date = df.loc[(df.index >= year_start) & (df.index <= year_end)].index.min()

            # If a trading date is found, add it to the end dates list
            if pd.notna(first_trading_date):
                end_dates.append(first_trading_date.strftime("%Y-%m-%d"))

            # Increment the current date for the next iteration
            current_date_int += increment

        return end_dates

    except (ValueError, KeyError) as e:
        print(f"Error: {e}.")
        return None

def get_df(stock, end_date, interval="1d", redownload=False, save=True):
    """
    Retrieve price data for a specified stock and save it to CSV.

    Parameters:
    - stock (str): The stock ticker symbol.
    - end_date (str): The end date for retrieving data in "YYYY-MM-DD" format.
    - interval (str): Time interval for the data (e.g., "1d", "60m"). Default is "1d".
    - redownload (bool): If True, forces a redownload of the data. Default to False.
    - save (bool): If True, saves the data to a CSV file. Default to True.

    Returns:
    - DataFrame: A pandas DataFrame containing the stock price data, or None if an error occurs.
    """

    # Determine the starting date based on the interval
    if interval in ["60m", "1h"]:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=729)).strftime("%Y-%m-%d")
    elif interval in ["2m", "5m", "15m", "30m", "90m"]:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=59)).strftime("%Y-%m-%d")
    elif interval in ["1m"]:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=7)).strftime("%Y-%m-%d")
    else:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(years=40)).strftime("%Y-%m-%d")

    # Define the folder path for saving price data
    folder_path = "Price data"

    # Check for existing data files for the stock
    current_files = [file for file in os.listdir(folder_path) if file.startswith(f"{stock}_")]

    # Extract dates from the existing files
    dates = [file.split("_")[-1].replace(".csv", "") for file in current_files]

    # Determine the maximum date from existing files
    max_date = max(dates) if dates else "N/A"

    # Remove the old files for dates prior to the maximum date
    if max_date != "N/A":
        for date in dates:
            if date < max_date:
                os.remove(os.path.join(folder_path, f"{stock}_{date}.csv"))
        # Define the filename based on the comparison of end_date and max_date
        if end_date >= max_date:
            filename = os.path.join(folder_path, f"{stock}_{end_date}.csv")
        else:
            filename = os.path.join(folder_path, f"{stock}_{max_date}.csv")
    else:
        filename = os.path.join(folder_path, f"{stock}_{end_date}.csv")
    
    # Download price data if it does not exist or if redownload is requested
    if not os.path.isfile(filename) or redownload:
        df = yf.download(stock, start=csv_date, end=end_date, interval=interval, session=LimiterSession(per_second=5))
        if not df.empty:
            # Adjust DataFrame for daily data
            df.columns = df.columns.droplevel(1)
            if interval == "1d":
                df.index = df.index.date
                df["Date"] = pd.to_datetime(df.index)
                df.set_index("Date", inplace=True)
                
            else:
                df["Datetime"] = pd.to_datetime(df.index, utc=True)
                df.set_index("Datetime", inplace=True)

            # Remove the old file for the maximum date if applicable
            if max_date != "N/A":
                if max_date < end_date:
                    os.remove(os.path.join(folder_path, f"{stock}_{max_date}.csv"))
            
             # Save the DataFrame to a CSV file if specified
            if save:
                df.to_csv(filename)
                df = pd.read_csv(filename)

            else:
                return df
        
        # Read the most updated data from the CSV file           
        else:
            try:
                print(f"The price data of {stock} cannot be updated.")
            except Exception as e:
                print(f"Error for {stock}: {e}.")
                
            return None

    # Read the most updated data
    else:
        df = pd.read_csv(filename)

    if interval == "1d":
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        
    else:
        df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
        df.set_index("Datetime", inplace=True)
        
    return df

def get_stock_info(stock):
    """
    Retrieve stock information from yfinance.

    Parameters:
    - stock (str): The stock ticker symbol.

    Returns:
    - dict: A dictionary containing stock information, or None if an error occurs.
    """

    try:
        # time.sleep(0.5)
        return yf.Ticker(stock, session=LimiterSession(per_second=5)).info
    
    except Exception as e:
        print((f"Error for get_stock_info {stock}: {e}\n"))
        return None

def get_volume5m_data(df, date, sma_period=50):
    """
    Retrieve 5-minute volume data, including the simple moving average (SMA) and standard deviation.

    Parameters:
    - df (DataFrame): The DataFrame containing volume data with a datetime index.
    - date (str): The specific date for which to retrieve the volume data in "YYYY-MM-DD" format.
    - sma_period (int): The number of periods for calculating the SMA and standard deviation. Default to 50.

    Returns:
    - dict: A dictionary containing:
        - df_date: Data for the specific date.
        - df0_hours: Elapsed time in hours for the specific date.
        - volume5m_sma_df0: SMA of volume for the specific date.
        - volume5m_std_df0: Standard deviation of volume for the specific date.
        - sma_hours: Corresponding elapsed hours for SMA values.
    """

    # Extract date and time components from the DataFrame index
    df["Date"] = df.index.date.astype(str)
    df["Time"] = df.index.time.astype(str)
    df["Datetime"] = df.index

    # Calculate the elapsed time for each entry within its day
    df["Elapsed Time"] = df["Datetime"] - df["Date"].map(df.groupby("Date")["Datetime"].min())

    # Filter the DataFrame for the specific date
    df_date = df[df.index.get_level_values("Datetime").date == pd.to_datetime(date).date()]

    # Ensure there is data available for the specified date
    if df_date.empty:
        print(f"No data available for the date: {date}.")
        return None

    # Calculate the elapsed hours for the specific date
    df0_hours = df_date["Elapsed Time"].dt.total_seconds() / 3600

    # Calculate the SMA and standard deviation of the 5-minute volume
    volume5m_sma_df = df.groupby("Elapsed Time")["Volume"].rolling(sma_period, min_periods=1).mean()
    volume5m_sma_df0 = volume5m_sma_df[volume5m_sma_df.index.get_level_values("Datetime").date == pd.to_datetime(date).date()]
    volume5m_sma_df0 = volume5m_sma_df0.droplevel(1)
    volume5m_std_df = df.groupby("Elapsed Time")["Volume"].rolling(sma_period, min_periods=1).std()
    volume5m_std_df0 = volume5m_std_df[volume5m_std_df.index.get_level_values("Datetime").date == pd.to_datetime(date).date()]

    # Calculate the elapsed hours for the SMA values
    sma_hours = volume5m_sma_df0.index.total_seconds() / 3600

    return {
        "df_date": df_date,
        "df0_hours": df0_hours,
        "volume5m_sma_df0": volume5m_sma_df0,
        "volume5m_std_df0": volume5m_std_df0,
        "sma_hours": sma_hours,
    }

def get_excel_filename(end_date, index_name, index_dict, period_hk, period_us, RS, NASDAQ_all, result_folder):
    """
    Generate the filename for an Excel file based on the provided parameters.

    Parameters:
    - end_date (str): The end date in "YYYY-MM-DD" format.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - period_hk (str): The period for Hong Kong stocks.
    - period_us (str): The period for US stocks.
    - RS (str): The relative strength value.
    - NASDAQ_all (bool): If True, include all stocks in NASDAQ.
    - result_folder (str): The folder where the result will be saved.

    Returns:
    - str: The complete Excel filename including the path.
    """

    # Select the period based on whether the index is HK or US
    if index_name == "^HSI":
        period = period_hk
    else:
        period = period_us

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Format the end date to "DD-MM-YY"
    end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%y")

    # Define the folder path for results
    folder_path = os.path.join(result_folder, end_date_fmt)

    # Construct the Excel filename
    excel_filename = os.path.join(folder_path, f"{infix}stock_{end_date_fmt}period{period}RS{RS}.xlsx")

    return excel_filename

def merge_stocks(stocks, end_date):
    """
    Merge the price data of multiple stocks into a single DataFrame.

    Parameters:
    - stocks (list): A list of stock ticker symbols.
    - end_date (str): The end date in "YYYY-MM-DD" format.

    Returns:
    - DataFrame: A merged DataFrame containing the price data of all stocks.
    """

    # Retrieve the price data for each stock
    dfs = [get_df(stock, end_date) for stock in stocks]

    # Rename the columns of the first DataFrame to include the stock name
    df_merged = dfs[0].rename(columns=lambda col: f"{col} ({stocks[0]})")

    # Join the remaining DataFrames, renaming columns to include respective stock names
    for i in range(1, len(dfs)):
        df_merged = df_merged.join(dfs[i].rename(columns=lambda col: f"{col} ({stocks[i]})"), how="inner")

    return df_merged

def stock_market(end_date, current_date, index_name, HKEX_all, NASDAQ_all):
    """
    Retrieve a list of stock tickers from the specified stock market.

    Parameters:
    - end_date (str): The end date in "YYYY-MM-DD" format.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - HKEX_all (bool): Flag to indicate if all HKEX tickers should be retrieved.
    - NASDAQ_all (bool): Flag to indicate if all NASDAQ tickers should be retrieved.

    Returns:
    - list: A sorted list of stock tickers.
    """

    # HKEX (Hong Kong Stock Exchange)
    if index_name == "^HSI":
        if HKEX_all:
            hkex_df = pd.read_excel("Program/ListOfSecurities.xlsx", skiprows=2)
            hkex_df = hkex_df[hkex_df["Category"] == "Equity"]
            tickers = hkex_df["Stock Code"].tolist()
            tickers = [str(int(ticker)).zfill(4) + '.HK' for ticker in tickers]
        else:
            hsi_df = pd.read_csv("Program/constituents-hsi.csv")
            tickers = hsi_df["Symbol"].tolist()

    # S&P 500
    elif not NASDAQ_all and index_name == "^GSPC":
        # Read the CSV file containing historical components of the S&P 500
        sp500_df = pd.read_csv("Program/sp_500_historical_components.csv")
        sp500_df["date"] = pd.to_datetime(sp500_df["date"])
        sp500_df.set_index("date", inplace=True)

        # Read Wikipedia to get the current components of the S&P 500
        tickers_table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers = tickers_table["Symbol"].tolist()
        tickers = [str(ticker).replace(".", "-").replace("^", "-P").replace("/", "-") for ticker in tickers]
        tickers.sort()
        
        # Save the tickers to the CSV file
        sp500_df.loc[pd.to_datetime(current_date), "tickers"] = ",".join(tickers)
        sp500_df.to_csv("Program/sp_500_historical_components.csv")

        # Get the list of tickers for the specified end date
        tickers = sp500_df[sp500_df.index <= end_date]["tickers"].iloc[-1].split(",")
        tickers = [str(ticker).replace(".", "-").replace("^", "-P").replace("/", "-") for ticker in tickers]
        tickers.sort()

    # NASDAQ Composite
    elif index_name == "^IXIC":
        from yahoo_fin import stock_info as si
        tickers = si.tickers_nasdaq()
        tickers = [str(ticker).replace(".", "-").replace("^", "-P").replace("/", "-") for ticker in tickers]
        tickers.sort()

    # NASDAQ
    elif NASDAQ_all and index_name == "^GSPC":
        tickers_table = pd.read_csv("Program/nasdaq.csv")
        tickers = tickers_table["Symbol"].tolist()
        tickers = [str(ticker).replace(".", "-").replace("^", "-P").replace("/", "-") for ticker in tickers]
        tickers.sort()
        
    return tickers

def get_infix(index_name, index_dict, NASDAQ_all):
    """
    Retrieve the infix for a given index name.

    Parameters:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Flag to indicate if all NASDAQ tickers should be retrieved.

    Returns:
    - str: The infix corresponding to the index name.
    """

    if NASDAQ_all and index_name == "^GSPC":
        infix = "NASDAQ"
    else:
        infix = index_dict[index_name].replace(" ", "")
        
    return infix

def get_currency(index_name):
    """
    Get the currency associated with a given index name.

    Parameters:
    - index_name (str): The name of the stock index.

    Returns:
    - str: The currency code (e.g., "HKD", "USD").
    """
    
    if index_name == "^HSI":
        currency = "HKD"
    elif index_name == "^GSPC" or "^IXIC":
        currency = "USD"

    return currency

def get_rs_volume(stock, rs_volume_df):
    """
    Find the relative strength (RS) rating and volume SMA 5 rank of a stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - rs_volume_df (DataFrame): A DataFrame containing stock data, including RS and volume SMA 5 rank.

    Returns:
    - tuple: A tuple containing the RS rating and volume SMA 5 rank, or None if the stock is not found.
    """

    if stock in rs_volume_df["Stock"].values:
        row = rs_volume_df.loc[rs_volume_df["Stock"] == stock]
        rs = row["RS"].iloc[0]
        volume_sma5_rank = row["Volume SMA 5 Rank"].iloc[0]

        return rs, volume_sma5_rank
    else:
        return None

def slope_reg(arr):
    """
    Calculate the slope of a linear regression line for a given array.

    Parameters:
    - arr (array-like): The input array for which to calculate the slope.

    Returns:
    - float: The slope of the regression line.
    """

    y = np.array(arr)
    x = np.arange(len(y))
    slope = linregress(x, y)[0]
    
    return slope

def randomise_array(arr):
    """
    Randomise the order of elements in an array by swapping random elements.

    Parameters:
    - arr (array-like): The input array to randomise.

    Returns:
    - array: The randomised array, scaled by a uniform random factor.
    """

    # Get the length of the array
    length = len(arr)
    
    # Randomise the array by swapping two random elements 10 times
    for i in range(10):
        index = np.random.randint(0, length - 1)
        arr[index], arr[index + 1] = arr[index + 1], arr[index]

    # Scale the array by a uniform random factor between 0.8 and 1.2
    return arr * np.random.uniform(low=0.8, high=1.2, size=arr.shape)