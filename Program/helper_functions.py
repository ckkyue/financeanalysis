# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd
import os
import re
from requests_ratelimiter import LimiterSession
from scipy.stats import linregress
import time
import yfinance as yf

# Determines if a given time is within the Daylight Saving Time (DST) period in the USA.
def check_DST(start):
   # Get the current year
    year = start.year

    # Calculate the second Sunday in March
    march1 = dt.datetime(year, 3, 1)
    sun_march2 = march1 + dt.timedelta(days=(6 - march1.weekday()) % 7) + dt.timedelta(weeks=1)

    # Calculate the first Sunday in November
    nov1 = dt.datetime(year, 11, 1)
    sun_nov1 = nov1 + dt.timedelta(days=(6 - nov1.weekday()) % 7)

    # Return both dates as strings
    return sun_march2 <=  start <= sun_nov1

# Get the current date
def get_current_date(start, index_name):
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
    
# Generate a list of end dates
def generate_end_dates(years, current_date, interval="1m", index_name="^GSPC"):
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
        current = dt.datetime.strptime(current_date, "%Y-%m-%d")
        target_date = current - relativedelta(years=years)
        target_date = target_date.replace(day=1)

        # Get the price data of the index
        df = get_df(index_name, current_date)

        # Initialize the list of end dates
        end_dates = []
        current_date_int = target_date

        # Determine increment based on the unit
        increment = {"w": relativedelta(weeks=number), 
                     "m": relativedelta(months=number), 
                     "y": relativedelta(years=number)
                     }[unit]

        # Loop to generate end dates
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
            if pd.notna(first_trading_date):
                end_dates.append(first_trading_date.strftime("%Y-%m-%d"))
                
            current_date_int += increment

        return end_dates

    except (ValueError, KeyError) as e:
        print(f"Error: {e}")
        return None

# Get the price data of a stock
def get_df(stock, end_date, interval="1d", redownload=False, save=True):
    # Initial setup
    if interval in ["60m", "1h"]:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=729)).strftime("%Y-%m-%d")
    elif interval in ["2m", "5m", "15m", "30m", "90m"]:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=59)).strftime("%Y-%m-%d")
    elif interval in ["1m"]:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=7)).strftime("%Y-%m-%d")
    else:
        csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(years=40)).strftime("%Y-%m-%d")

    # Define the folder path
    folder_path = "Price data"

    # Check if there are pre-existing data
    current_files = [file for file in os.listdir(folder_path) if file.startswith(f"{stock}_")]

    # Get the list of dates
    dates = [file.split("_")[-1].replace(".csv", "") for file in current_files]

    # Get the maximum date from the list of dates
    max_date = max(dates) if dates else "N/A"

    # Remove the old files for dates prior to the maximum date
    if max_date != "N/A":
        for date in dates:
            if date < max_date:
                os.remove(os.path.join(folder_path, f"{stock}_{date}.csv"))
        # Define the filename
        if end_date >= max_date:
            filename = os.path.join(folder_path, f"{stock}_{end_date}.csv")
        else:
            filename = os.path.join(folder_path, f"{stock}_{max_date}.csv")
    else:
        filename = os.path.join(folder_path, f"{stock}_{end_date}.csv")
    
    # Save the price data to a .csv file if the most updated data do not exist
    if not os.path.isfile(filename) or redownload:
        df = yf.download(stock, start=csv_date, end=end_date, interval=interval, session=LimiterSession(per_second=5))
        if not df.empty:
            df.columns = df.columns.droplevel(1)
            if interval == "1d":
                df.index = df.index.date
                df["Date"] = pd.to_datetime(df.index)
                df.set_index("Date", inplace=True)
                
            else:
                df["Datetime"] = pd.to_datetime(df.index, utc=True)
                df.set_index("Datetime", inplace=True)

            # Remove the old file for the maximum date
            if max_date != "N/A":
                if max_date < end_date:
                    os.remove(os.path.join(folder_path, f"{stock}_{max_date}.csv"))
 
            if save:
                df.to_csv(filename)
                df = pd.read_csv(filename)

            else:
                return df
                    
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

# Get the information of a stock from yfinance
def get_stock_info(stock):
    try:
        # time.sleep(0.5)
        return yf.Ticker(stock, session=LimiterSession(per_second=5)).info
    
    except Exception as e:
        print((f"Error for get_stock_info {stock}: {e}\n"))

        return None

# Get the 5-min volume data
def get_volume5m_data(df, date, period=50):
    # Extract date and time components
    df["Date"] = df.index.date.astype(str)
    df["Time"] = df.index.time.astype(str)
    df["Datetime"] = df.index

    # Calculate the elapsed time of each day
    df["Elapsed Time"] = df["Datetime"] - df["Date"].map(df.groupby("Date")["Datetime"].min())

    # Extract the dataframe of a specific date
    df_date = df[df.index.get_level_values("Datetime").date == pd.to_datetime(date).date()]

    # Ensure df_date is not empty
    if df_date.empty:
        print(f"No data available for the date: {date}.")
        return None

    # Calculate the number of hours of the specific date
    df0_hours = df_date["Elapsed Time"].dt.total_seconds() / 3600

    # Calculate the SMA 50 and standard deviation of 5-min volume
    volume5m_sma_df = df.groupby("Elapsed Time")["Volume"].rolling(period, min_periods=1).mean()
    volume5m_sma_df0 = volume5m_sma_df[volume5m_sma_df.index.get_level_values("Datetime").date == pd.to_datetime(date).date()]
    volume5m_sma_df0 = volume5m_sma_df0.droplevel(1)
    volume5m_std_df = df.groupby("Elapsed Time")["Volume"].rolling(period, min_periods=1).std()
    volume5m_std_df0 = volume5m_std_df[volume5m_std_df.index.get_level_values("Datetime").date == pd.to_datetime(date).date()]

    # Calculate the number of hours for SMA values
    sma_hours = volume5m_sma_df0.index.total_seconds() / 3600

    return {
        "df_date": df_date,
        "df0_hours": df0_hours,
        "volume5m_sma_df0": volume5m_sma_df0,
        "volume5m_std_df0": volume5m_std_df0,
        "sma_hours": sma_hours,
    }

# Get the Excel filename
def get_excel_filename(end_date, index_name, index_dict, period_hk, period_us, RS, NASDAQ_all, result_folder):
        # Select period based on HK/US
        if index_name == "^HSI":
            period = period_hk
        else:
            period = period_us

        # Get the infix
        infix = get_infix(index_name, index_dict, NASDAQ_all)

        # Format the end date
        end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%y")

        # Define the folder path
        folder_path = os.path.join(result_folder, end_date_fmt)

        # Define the Excel filename
        excel_filename = os.path.join(folder_path, f"{infix}stock_{end_date_fmt}period{period}RS{RS}.xlsx")

        return excel_filename

# Merge dataframes of stocks
def merge_stocks(stocks, end_date):
    # Get the price data of the stocks
    dfs = [get_df(stock, end_date) for stock in stocks]

    # Rename the columns of the first DataFrame to include the stock name
    df_merged = dfs[0].rename(columns=lambda col: f"{col} ({stocks[0]})")

    # Join the remaining DataFrames with the appropriate suffix
    for i in range(1, len(dfs)):
        df_merged = df_merged.join(dfs[i].rename(columns=lambda col: f"{col} ({stocks[i]})"), how="inner")

    return df_merged

# Get the list of tickers of stock market
def stock_market(end_date, current_date, index_name, HKEX_all, NASDAQ_all):
    # HKEX
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
        # Read the .csv file containing historical components of S&P 500
        sp500_df = pd.read_csv("Program/sp_500_historical_components.csv")
        sp500_df["date"] = pd.to_datetime(sp500_df["date"])
        sp500_df.set_index("date", inplace=True)

        # Read Wikipedia to get the current components of S&P 500
        tickers_table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers = tickers_table["Symbol"].tolist()
        tickers = [str(ticker).replace(".", "-").replace("^", "-P").replace("/", "-") for ticker in tickers]
        tickers.sort()
        
        # Save the tickers to the .csv file
        sp500_df.loc[pd.to_datetime(current_date), "tickers"] = ",".join(tickers)
        sp500_df.to_csv("Program/sp_500_historical_components.csv")

        # Get the list of tickers
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

# Get the infix
def get_infix(index_name, index_dict, NASDAQ_all):
    if NASDAQ_all and index_name == "^GSPC":
        infix = "NASDAQ"
    else:
        infix = index_dict[index_name].replace(" ", "")
        
    return infix

# Get the currency
def get_currency(index_name):
    if index_name == "^HSI":
        currency = "HKD"
    elif index_name == "^GSPC" or "^IXIC":
        currency = "USD"

    return currency

# Find the RS rating and volume SMA 5 rank of a stock
def get_rs_volume(stock, rs_volume_df):
    if stock in rs_volume_df["Stock"].values:
        row = rs_volume_df.loc[rs_volume_df["Stock"] == stock]
        rs = row["RS"].iloc[0]
        volume_sma5_rank = row["Volume SMA 5 Rank"].iloc[0]

        return rs, volume_sma5_rank
    else:
        return None

# Slope function
def slope_reg(arr):
    y = np.array(arr)
    x = np.arange(len(y))
    slope = linregress(x, y)[0]
    
    return slope

# Randomize an array
def randomize_array(arr):
    # Get the length of the array
    length = len(arr)
    
    # Randomize the array by swapping two random elements 10 times
    for i in range(10):
        index = np.random.randint(0, length - 1)
        arr[index], arr[index + 1] = arr[index + 1], arr[index]

    return arr * np.random.uniform(low=0.8, high=1.2, size=arr.shape)