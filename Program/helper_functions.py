# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
import io
from contextlib import redirect_stdout, redirect_stderr
from curl_cffi import requests
session = requests.Session(impersonate="chrome")
import numpy as np
import pandas as pd
import os
import re
from requests_ratelimiter import LimiterSession
from scipy.stats import linregress
import time
from tqdm import tqdm
import tvDatafeed as tv
from tvDatafeed import Interval
import yfinance as yf
import requests

def check_DST(start):
    """
    Determine if a given time is within the Daylight Saving Time (DST) period in the USA.

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

def modify_current_date(start, index_name):
    """
    Modify the current date based on the provided datetime and stock index name.

    Parameters:
    - start (datetime): The datetime object to evaluate.
    - index_name (str): The name of the stock index.

    Returns:
    - str: The formatted date in 'YYYY-MM-DD' format.
    """

    weekday = start.weekday()
    if weekday == 6:  # Sunday
        return (start - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    if weekday == 5:  # Saturday
        return start.strftime("%Y-%m-%d")

    if index_name == "^HSI":
        # HSI cutoff: after 16:10, use next day
        if start.hour > 16 or (start.hour == 16 and start.minute >= 10):
            return (start + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        return start.strftime("%Y-%m-%d")

    # US indices
    dst_offset = 0 if check_DST(start) else 1
    hour_cutoff = 4 + dst_offset
    if start.hour >= hour_cutoff:
        return start.strftime("%Y-%m-%d")
    return (start - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    
def _get_range(unit, base_date, shift_increment):
    """
    Calculate the start and end date range for a given interval unit and shift.

    Parameters:
    - unit (str): The interval unit ("w" for weeks, "m" for months, "y" for years).
    - base_date (datetime): The base date to start from.
    - shift_increment (relativedelta): The shift to apply to the range.

    Returns:
    - tuple: (start, end) where both are datetime objects representing the start and end of the range.
    """
    if unit == "w":
        start = base_date + shift_increment
        end = start + relativedelta(weeks=1, days=-1)
    elif unit == "m":
        start = base_date + shift_increment
        end = start + relativedelta(months=1, days=-1)
    elif unit == "y":
        start = base_date + shift_increment
        end = start + relativedelta(years=1, days=-1)
    else:
        start = end = base_date
    return start, end

def generate_end_dates(start_date=None, end_date=None, years=None, interval="1m", shift="0d", index_name="^GSPC"):
    """
    Generate a list of end dates based on a specified interval and a starting date, with an optional shift.

    Parameters:
    - start_date (str or datetime, optional): The start date in "YYYY-MM-DD" format or as a datetime object. Default is None.
    - end_date (str or datetime, optional): The end date in "YYYY-MM-DD" format or as a datetime object. Default is None.
    - years (int, optional): The number of years for which to generate end dates. Default is None.
    - interval (str): The duration for generating end dates in the format "<number><unit>".
                      Units can be "w" (weeks), "m" (months), or "y" (years). Default is "1m".
    - shift (str): The duration to shift the end dates in the format "<number><unit>". Default is "0d".
    - index_name (str): The name of the index for which to fetch price data. Default is "^GSPC".

    Returns:
    - list: A list of end dates as strings in "YYYY-MM-DD" format, or None if an error occurs.
    """

    # Convert start_date and end_date to datetime objects if they are strings
    if start_date and isinstance(start_date, str):
        start_date = dt.datetime.strptime(start_date, "%Y-%m-%d")
    if end_date and isinstance(end_date, str):
        end_date = dt.datetime.strptime(end_date, "%Y-%m-%d")

    # Validate the interval format
    match = re.match(r"(\d+)([a-zA-Z])", interval)
    if not match:
        raise ValueError("Interval must match the format '<number><unit>'.")
    
    number = int(match.group(1))
    unit = match.group(2)

    if number < 0:
        raise ValueError("Number must be a non-negative integer.")
        
    if unit not in ["w", "m", "y"]:
        raise ValueError("Unit must be one of 'w' (weeks), 'm' (months), or 'y' (years).")

    # Validate the shift format
    shift_match = re.match(r"(\d+)([a-zA-Z])", shift)
    if not shift_match:
        raise ValueError("Shift must match the format '<number><unit>'.")
    
    shift_number = int(shift_match.group(1))
    shift_unit = shift_match.group(2)

    if shift_number < 0:
        raise ValueError("Shift number must be a non-negative integer.")
        
    if shift_unit not in ["d", "w", "m", "y"]:
        raise ValueError("Shift unit must be one of 'd' (days), 'w' (weeks), 'm' (months), or 'y' (years).")

    try:
        # Parse the start date and end date
        if start_date and end_date:
            current_date_int = start_date
        elif start_date and years:
            end_date = start_date + relativedelta(years=years)
            end_date = end_date.replace(day=1) + relativedelta(months=1, days=-1)
            current_date_int = start_date
        elif end_date and years:
            start_date = end_date - relativedelta(years=years)
            start_date = start_date.replace(day=1)
            current_date_int = start_date
        else:
            raise ValueError("At least two of start_date, end_date, and years must be specified.")
        
        # Retrieve the price data for the specified index
        end_date_fmt = end_date.strftime("%Y-%m-%d")
        df = get_df(index_name, end_date_fmt)
        
        # Initialise the list to hold end dates
        end_dates = []

        # Use dicts for increment and shift
        increment_map = {
            "w": relativedelta(weeks=number),
            "m": relativedelta(months=number),
            "y": relativedelta(years=number)
        }
        shift_map = {
            "d": relativedelta(days=shift_number),
            "w": relativedelta(weeks=shift_number),
            "m": relativedelta(months=shift_number),
            "y": relativedelta(years=shift_number)
        }
        increment = increment_map[unit]
        shift_increment = shift_map[shift_unit]

        # Loop to generate end dates until the current date
        while current_date_int <= end_date:
            range_start, range_end = _get_range(unit, current_date_int, shift_increment)
            trading_dates = df.loc[(df.index >= range_start) & (df.index <= range_end)].index
            if not trading_dates.empty:
                end_dates.append(trading_dates.min().strftime("%Y-%m-%d"))
            current_date_int += increment

        return end_dates

    except (ValueError, KeyError) as e:
        print(f"Error: {e}.")
        return None

def get_df(stock, end_date, interval="1d", max_period=False, adj=False, redownload=False, max_retry=5, min_interval=0.2, save=True, method="yfinance"):
    """
    Retrieve price data for a specified stock and save it to CSV.

    Parameters:
    - stock (str): Stock ticker symbol.
    - end_date (str): End date for data in "YYYY-MM-DD" format.
    - interval (str, optional): Data interval (e.g., "1d", "60m"). Defaults to "1d".
    - max_period (bool, optional): If True, fetch maximum available data. Defaults to False.
    - adj (bool, optional): If True, adjust OHLC prices based on Adj Close. Defaults to False.
    - redownload (bool, optional): If True, force redownload. Defaults to False.
    - max_retry (int, optional): Number of retry attempts for download. Defaults to 5.
    - min_interval (float, optional): Minimum seconds between calls. Default is 0.2.
    - save (bool, optional): If True, save data to CSV. Defaults to True.
    - method (str, optional): Data source method ("yfinance" or "tradingview"). Defaults to "yfinance".

    Returns:
    - pd.DataFrame: Stock price data, or None if data cannot be retrieved or invalid period.
    """

    # Common setup - define folder path and file naming logic
    folder_path = "Price data"
    
    # Determine file suffix based on method and parameters
    if method == "tradingview":
        filename = os.path.join(folder_path, f"{stock}_{end_date}.csv")
        file_suffix = ""
    else:
        max_suffix = "_max" if max_period else ""
        interval_suffix = f"_{interval}" if interval != "1d" else ""
        file_suffix = f"{max_suffix}{interval_suffix}"
        filename = os.path.join(folder_path, f"{stock}_{end_date}{file_suffix}.csv")

    # Common file management logic
    current_files = [
        file for file in os.listdir(folder_path)
        if file.startswith(f"{stock}_") and file.endswith(f"{file_suffix}.csv")
    ]
    dates = [file.replace(".csv", "").split("_")[1] for file in current_files]
    max_date = max(dates, default=None)

    # Remove outdated files and update filename if newer exists
    if max_date:
        for date in dates:
            if date < max_date:
                old_file = os.path.join(folder_path, f"{stock}_{date}{file_suffix}.csv")
                if os.path.exists(old_file):
                    os.remove(old_file)
        if max_date > end_date:
            filename = os.path.join(folder_path, f"{stock}_{max_date}{file_suffix}.csv")

    # Check if download is needed
    need_download = (redownload or not os.path.isfile(filename))

    # Download data if needed
    if need_download:
        if method == "tradingview":
            try:
                tv_client = tv.TvDatafeed()
                df = tv_client.get_hist(symbol=stock, exchange="INDEX", interval=Interval.in_daily, n_bars=10000)
                
                if df is None or df.empty:
                    print(f"Failed to retrieve TradingView data for {stock}.")
                    return None
                
                # Process TradingView data
                df.columns = [col.capitalize() for col in df.columns]
                df.index = pd.to_datetime(df.index)
                df.index.name = "Datetime"
                df.index = df.index.normalize()
                
                if "Volume" in df.columns:
                    df = df.drop(columns=["Volume"])
                
            except Exception as e:
                print(f"Error downloading {stock} from TradingView: {e}")
                return None

        else:  # yfinance method
            delay = 5
            interval_periods = {
                "1m": relativedelta(days=7),
                "2m": relativedelta(days=59),
                "5m": relativedelta(days=59),
                "15m": relativedelta(days=59),
                "30m": relativedelta(days=59),
                "90m": relativedelta(days=59),
                "60m": relativedelta(days=729),
                "1h": relativedelta(days=729),
            }
            
            csv_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - interval_periods.get(interval, relativedelta(years=40))).strftime("%Y-%m-%d")
            
            df = None
            fatal_error = False

            for attempt in range(1, max_retry + 1):
                # Rate limit
                last_call = getattr(get_df, "_yf_last_call", None)
                now = time.time()
                if last_call is not None:
                    elapsed = now - last_call
                    if elapsed < min_interval:
                        time.sleep(min_interval - elapsed)
                get_df._yf_last_call = time.time()

                stdout_buffer = io.StringIO()
                stderr_buffer = io.StringIO()
                try:
                    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                        params = {
                            "session": session,
                            "auto_adjust": False
                        }
                        if max_period:
                            df = yf.download(stock, **params)
                        else:
                            df = yf.download(stock, start=csv_date, end=end_date, interval=interval, **params)

                    captured_output = stdout_buffer.getvalue() + stderr_buffer.getvalue()
                    errors = ["YFInvalidPeriodError", "YFPricesMissingError", "YFTzMissingError"]
                    for error in errors:
                        if error in captured_output:
                            print(f"{error} for {stock}. Aborting further attempts.")
                            fatal_error = True
                            break

                    if fatal_error:
                        break # exit retry loop immediately
                    
                    if not df.empty:
                        break
                    print(f"Empty DataFrame for {stock} on attempt {attempt}.")
                    if attempt < max_retry:
                        time.sleep(delay)

                except Exception as e:
                    error_message = str(e).lower()
                    print(f"Error downloading {stock} on attempt {attempt}: {e}")
                    if "rate" in error_message or "limit" in error_message or "429" in error_message:
                        delay = 30
                    if attempt < max_retry:
                        print(f"Retrying in {delay} seconds...")
                        time.sleep(delay)

            if df is None or df.empty:
                print(f"Failed to update price data for {stock}.")
                if max_date:
                    fallback_file = os.path.join(folder_path, f"{stock}_{max_date}{file_suffix}.csv")
                    if os.path.exists(fallback_file):
                        return pd.read_csv(fallback_file)
                return None

            # Process yfinance data
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.index = pd.to_datetime(df.index.date if interval == "1d" else df.index, utc=interval != "1d")
            df.index.name = "Date" if interval == "1d" else "Datetime"

            # Remove old file if newer data was downloaded
            if max_date and max_date < end_date:
                old_file = os.path.join(folder_path, f"{stock}_{max_date}{file_suffix}.csv")
                if os.path.exists(old_file):
                    os.remove(old_file)

        # Save to CSV (common for both methods)
        if save:
            df.to_csv(filename)

    else:
        # Load existing file (common for both methods)
        try:
            df = pd.read_csv(filename)
        except pd.errors.EmptyDataError:
            print(f"WARNING: No data in {filename}. Returning None.")
            return None
        if method == "tradingview":
            df.set_index(pd.to_datetime(df["Datetime"]), inplace=True)
            df.index.name = "Datetime"
            df.drop(columns=["Datetime"], inplace=True)
        else:
            df.set_index(pd.to_datetime(df["Date" if interval == "1d" else "Datetime"], utc=interval != "1d"), inplace=True)
            df.index.name = "Date" if interval == "1d" else "Datetime"
            df.drop(columns=["Date" if interval == "1d" else "Datetime"], inplace=True)

    # Apply adjustments if requested (only for yfinance data)
    if adj and method == "yfinance":
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = df["Adj Close"] / df["Close"] * df[col]
        df.drop(columns=["Adj Close"], inplace=True)

    return df

def get_stock_info(stock, max_retry=5, min_interval=0.2):
    """
    Retrieve stock information from yfinance, enforcing a minimum interval between calls.

    Parameters:
    - stock (str): The stock ticker symbol.
    - max_retry (int): Maximum number of retry attempts. Default is 5.
    - min_interval (float, optional): Minimum seconds between calls. Default is 0.2.

    Returns:
    - dict: A dictionary containing stock information, or None if an error occurs.
    """

    delay = 5 # Default delay in seconds

    for attempt in range(max_retry):
        # Rate limit
        last_call = getattr(get_stock_info, "_yf_last_call", None)
        now = time.time()
        if last_call is not None:
            elapsed = now - last_call
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        get_stock_info._yf_last_call = time.time()

        try:
            stock_info = yf.Ticker(stock, session=session).info

            # Validate returned data - empty dicts can be returned on rate limiting
            if stock_info and len(stock_info) > 1:
                return stock_info
            else:
                print(f"Empty or incomplete data received for {stock} on attempt {attempt + 1}")

        except Exception as e:
            error_message = str(e).lower()
            print(f"Error for get_stock_info {stock} on attempt {attempt + 1}: {e}")

            # Check for specific rate limiting keywords
            if "rate" in error_message or "limit" in error_message or "429" in error_message:
                delay = 30

        # Wait before next retry with current delay
        if attempt < max_retry - 1:
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)

    print(f"Failed to retrieve information for {stock} after {max_retry} attempts.")
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

    # Ensure DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index)

    # Filter for the specific date
    date_dt = pd.to_datetime(date).date()
    df_date = df[df.index.date == date_dt]
    if df_date.empty:
        print(f"No data available for the date: {date}.")
        return None

    # Calculate elapsed time in hours from the day's start
    min_time = df_date.index.min()
    df_date = df_date.copy()
    df_date["Elapsed Time"] = (df_date.index - min_time)
    df0_hours = df_date["Elapsed Time"].dt.total_seconds() / 3600

    # Calculate rolling SMA and STD for the date
    volume5m_sma_df0 = df_date["Volume"].rolling(sma_period, min_periods=1).mean()
    volume5m_std_df0 = df_date["Volume"].rolling(sma_period, min_periods=1).std()
    sma_hours = (df_date.index - min_time).total_seconds() / 3600

    return {
        "df_date": df_date,
        "df0_hours": df0_hours,
        "volume5m_sma_df0": volume5m_sma_df0,
        "volume5m_std_df0": volume5m_std_df0,
        "sma_hours": sma_hours,
    }

def get_excel_filename(end_date, index_name, index_dict, period, RS, all_stocks, result_folder="Result"):
    """
    Generate the filename for an Excel file based on the provided parameters.

    Parameters:
    - end_date (str): The ending date in "YYYY-MM-DD" format.
    - index_name (str): The stock index symbol under analysis.
    - index_dict (dict): A dictionary mapping index symbols to their full names.
    - period (str): The period label to be included in the file name.
    - RS (float): The relative strength threshold to filter stocks.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - result_folder (str): The directory where the resulting Excel file will be saved. Default is "Result".

    Returns:
    - str: The complete Excel filename including the path.
    """

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)

    # Format the end date to "MM-DD-YY"
    end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%m-%d-%y")

    # Define the folder path for results
    folder_path = os.path.join(result_folder, end_date_fmt)

    # Construct the Excel filename
    excel_filename = os.path.join(folder_path, f"{infix}stock_{end_date_fmt}period{period}RS{RS}.xlsx")

    return excel_filename

def merge_stocks(stocks, dfs):
    """
    Merge the price data of multiple stocks into a single DataFrame.

    Parameters:
    - stocks (list): A list of stock ticker symbols.
    - dfs (list): A list of DataFrames containing price data for different stocks.
    - end_date (str): The end date in "YYYY-MM-DD" format.

    Returns:
    - DataFrame: A merged DataFrame containing the price data of all stocks.
    """

    # Rename the columns of the first DataFrame to include the stock name
    df_merged = dfs[0].rename(columns=lambda col: f"{col} ({stocks[0]})")

    # Join the remaining DataFrames using an outer join to include rows with NaN values    
    for i in range(1, len(dfs)):
        df_merged = df_merged.join(dfs[i].rename(columns=lambda col: f"{col} ({stocks[i]})"), how="outer")

    # Sort the index
    df_merged.sort_index(inplace=True)
    
    return df_merged

def sp500_bloomberg_to_csv():
    # Define the filename to save the output CSV
    bloomberg_file = "Program/sp_500_historical_components_bloomberg.csv"

    # Check if the file already exists
    if not os.path.exists(bloomberg_file):
        # Define the input Excel file path
        excel_file = "Program/sp_500_historical_components_bloomberg.xlsx"

        # Read the Excel file
        excel_data = pd.read_excel(excel_file, sheet_name=None) # Read all sheets into a dictionary

        # Initialize the DataFrame with date and tickers columns
        sp500_bloomberg_df = pd.DataFrame(columns=["date", "tickers"])

        # Process the Bloomberg S&P 500 components data
        for sheet_name, df in excel_data.items():
            if sheet_name.startswith("SPX"):
                try:
                    # Validate sheet name format
                    parts = sheet_name.split("_")
                    if len(parts) != 3:
                        raise ValueError("Sheet name must be in format 'SPX_YYYY_MM'.")

                    _, year, month = parts
                    # Ensure year and month are numeric
                    if not (year.isdigit() and month.isdigit()):
                        raise ValueError("Year and month must be numeric.")

                    # Map quarter-ending months to actual end dates (Jan, Apr, Jul, Oct)
                    month_map = {"01": "01-31", "04": "04-30", "07": "07-31", "10": "10-31"}
                    if month not in month_map:
                        raise ValueError(f"Month {month} not in expected quarters (01, 04, 07, 10).")

                    # Create the date string
                    date_str = f"{year}-{month_map[month]}"

                    # Get the first column of the DataFrame, which contains the tickers
                    tickers = df.iloc[:, 0].dropna().astype(str).tolist()

                    # Skip if no tickers are found
                    if not tickers:
                        print(f"Warning: No tickers found in sheet {sheet_name}.")
                        continue

                    # Clean up the ticker symbols
                    tickers = [ticker.split(" ")[0] for ticker in tickers]
                    tickers = [_normalize_ticker(ticker) for ticker in tickers]

                    # Add to the DataFrame
                    sp500_bloomberg_df = sp500_bloomberg_df.append({"date": date_str, "tickers": ",".join(tickers)}, ignore_index=True)

                except Exception as e:
                    print(f"Error processing sheet {sheet_name}: {e}")

        # Save the DataFrame to a CSV file
        sp500_bloomberg_df.to_csv(bloomberg_file, index=False)

def _get_hkex_tickers(base_path, all_stocks):
    """Retrieve HKEX tickers based on all_stocks flag."""
    if all_stocks:
        hkex_df = pd.read_excel(os.path.join(base_path, "ListOfSecurities.xlsx"), skiprows=2)
        tickers = hkex_df.loc[hkex_df["Category"] == "Equity", "Stock Code"].apply(lambda x: f"{int(x):04d}.HK").tolist()
    else:
        hsi_df = pd.read_csv(os.path.join(base_path, "constituents-hsi.csv"))
        tickers = hsi_df["Symbol"].tolist()
    return sorted(tickers)

def _get_sp500_tickers(base_path, end_date, current_date, bloomberg):
    """Retrieve S&P 500 tickers from historical data or Wikipedia."""
    sp500_bloomberg_file = os.path.join(base_path, "sp_500_historical_components_bloomberg.csv")
    sp500_hist_file = os.path.join(base_path, "sp_500_historical_components.csv")

    # Determine which data source to use
    if end_date < "2008-01-01" or bloomberg:
        if not os.path.exists(sp500_bloomberg_file):
            sp500_bloomberg_to_csv()
        sp500_file = sp500_bloomberg_file
    else:
        sp500_file = sp500_hist_file

    # Load historical data
    sp500_df = pd.read_csv(sp500_file)
    sp500_df["date"] = pd.to_datetime(sp500_df["date"])
    sp500_df.set_index("date", inplace=True)

    # Update with current data from Wikipedia if end_date is current_date
    if end_date == current_date:
        _update_sp500_from_wikipedia(sp500_df, current_date, sp500_hist_file)

    # Extract tickers for the end_date
    tickers = sp500_df[sp500_df.index <= end_date]["tickers"].iloc[-1].split(",")
    return sorted([_normalize_ticker(ticker) for ticker in tickers])

def _update_sp500_from_wikipedia(sp500_df, current_date, sp500_hist_file):
    """Update S&P 500 tickers from Wikipedia for the current date."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        response = requests.get(url, headers=headers)
        
        tickers_table = pd.read_html(response.content)[1]
        if "Symbol" not in tickers_table.columns:
            tickers_table = pd.read_html(response.content)[0]
        
        tickers = [_normalize_ticker(ticker) for ticker in tickers_table["Symbol"]]
        tickers.sort()

        # Update DataFrame and save
        sp500_df.loc[pd.to_datetime(current_date), "tickers"] = ",".join(tickers)
        sp500_df.to_csv(sp500_hist_file)
    except Exception as e:
        print(f"Warning: Could not update S&P 500 tickers from Wikipedia: {e}. Using existing data.")

def _get_nasdaq_composite_tickers():
    """Retrieve NASDAQ Composite tickers using yahoo_fin."""
    from yahoo_fin import stock_info as si
    tickers = [_normalize_ticker(ticker) for ticker in si.tickers_nasdaq()]
    return sorted(tickers)

def _get_nasdaq_all_tickers(base_path):
    """Retrieve all NASDAQ tickers from CSV file."""
    nasdaq_file = os.path.join(base_path, "nasdaq.csv")
    tickers_table = pd.read_csv(nasdaq_file)
    tickers = [_normalize_ticker(ticker) for ticker in tickers_table["Symbol"]]
    return sorted(tickers)

def _normalize_ticker(ticker):
    """Normalize ticker symbols by replacing special characters."""
    return str(ticker).replace(".", "-").replace("^", "-P").replace("/", "-")

def stock_market(end_date, current_date, index_name, all_stocks, bloomberg=False):
    """
    Retrieve a list of stock tickers from the specified stock market.

    Parameters:
    - end_date (str): The end date in "YYYY-MM-DD" format.
    - current_date (str): The current date in "YYYY-MM-DD" format.
    - index_name (str): Name of the index being analysed.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - bloomberg (bool): Flag indicating whether to use Bloomberg data. Default is False.

    Returns:
    - list: A sorted list of stock tickers.
    """

    base_path = "Constituents data"

    # HKEX (Hong Kong Stock Exchange)
    if index_name == "^HSI":
        return _get_hkex_tickers(base_path, all_stocks)

    # S&P 500
    elif not all_stocks and index_name == "^GSPC":
        return _get_sp500_tickers(base_path, end_date, current_date, bloomberg)

    # NASDAQ Composite
    elif index_name == "^IXIC":
        return _get_nasdaq_composite_tickers()

    # NASDAQ (all stocks)
    elif all_stocks and index_name == "^GSPC":
        return _get_nasdaq_all_tickers(base_path)

    return []

def get_infix(index_name, index_dict, all_stocks):
    """
    Retrieve the infix for a given index name.

    Parameters:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.

    Returns:
    - str: The infix corresponding to the index name.
    """

    if all_stocks and index_name == "^HSI":
        infix = "HKEX"
    elif all_stocks and index_name == "^GSPC":
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

def get_rs(stock, df):
    """
    Find the relative strength (RS) rating of a stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - df (DataFrame): A DataFrame containing RS ratings.

    Returns:
    - rs (float) or None: The RS rating, or None if the stock is not found.
    """

    if stock in df["Stock"].values:
        row = df.loc[df["Stock"] == stock]
        rs = row["RS"].iloc[0]
        return rs
    else:
        return None

def get_volume_sma_ranks(stock, df):
    """
    Find the volume SMA 5 and SMA 20 ranks of a stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - df (DataFrame): A DataFrame containing volume SMA 5 and SMA 20 ranks.

    Returns:
    - volume_sma_ranks (dict) or None: A dictionary containing the volume SMA 5 and 20 ranks, otherwise if the stock is not found.
    """

    if stock in df["Stock"].values:
        row = df.loc[df["Stock"] == stock]
        volume_sma5_rank = row["Volume SMA 5 Rank"].iloc[0]
        volume_sma20_rank = row["Volume SMA 20 Rank"].iloc[0]
        volume_sma_ranks = {
            "Volume SMA 5 Rank": volume_sma5_rank,
            "Volume SMA 20 Rank": volume_sma20_rank
            }
        return volume_sma_ranks
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