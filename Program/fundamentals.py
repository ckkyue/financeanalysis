# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
from helper_functions import get_df
import json
import numpy as np
import os
import pandas as pd
from pyfinviz.quote import Quote
import re
import requests
import time
import yfinance as yf

def scrape(url, retry=0, max_retry=10, **kwargs):
    """
    Scrape the specified URL with retry logic for handling HTTP errors.

    Parameters:
    - url (str): The URL to be scraped.
    - retry (int, optional): The current retry attempt. Default is 0.
    - max_retry (int, optional): The maximum number of retry attempts. Default is 10.
    - **kwargs: Additional arguments to pass to the requests.get() method.

    Returns:
    - response (requests.Response): The response object if the request is successful.
    - str: An error message if the request fails after retries or due to a general error.
    """

    session = requests.Session()

    # Update the session headers to mimic a browser
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
         "Accept-Language": "en-US,en;q=0.9",
         "Referer": "https://github.com/ckkyue?tab=repositories",
         "Cache-Control": "no-cache",
         "DNT": "1",
         }
    )

    try:
        response = session.get(url, **kwargs)
        response.raise_for_status() # Raise an exception for non-2xx status codes
        return response

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429: # Too Many Requests
            if retry < max_retry: # Check if maximum retry attempts have been reached
                retry_after = np.ceil(float(e.response.headers.get("Retry-After", 10))) # Default to 10 seconds if Retry-After header is missing
                time.sleep(retry_after)
                print(f"Retry after {retry_after} for {url}.")
                return scrape(url, retry=retry+1, max_retry=max_retry, **kwargs) # Retry the scrape after waiting
            else:
                return f"Maximum number of retry attempts reached."
        else:
            return f"HTTP error: {e}"

    except Exception as e:
        return f"General error: {e}"

def etl(response):
    """
    Extract, transform, and load data into a DataFrame from the HTTP response.

    Parameters:
    - response (requests.Response): The HTTP response object containing the data.

    Returns:
    - pd.DataFrame: A DataFrame containing the extracted data or an empty DataFrame in case of an error.
    """

    try:
        # Use regex to find relevant data in the response text
        num = re.findall('(?<=div\>\"\,)[0-9\.\"\:\-\, ]*', response.text)
        text = re.findall('(?<=s\: \')\S+(?=\'\, freq)', response.text)

        # Convert the extracted text into a list of dictionaries
        dicts = [json.loads("{" + i + "}") for i in num]

        # Initialise an empty DataFrame to store the data
        df = pd.DataFrame()
        for index, value in enumerate(text):
            df[value] = dicts[index].values()
        
        # Set the DataFrame's index to the keys of the last dictionary
        df.index = dicts[index].keys()
        return df
    
    except Exception:
        return pd.DataFrame()
    
def get_csv_date(current_date, before=True):
    """
    Get the closest CSV date based on the current date.

    Parameters:
    - current_date (str): The current date in 'YYYY-MM-DD' format.
    - before (bool): If True, return the latest date before or on the current date; 
                     if False, return the earliest date after the current date.

    Returns:
    - str: The closest CSV date in 'YYYY-MM-DD' format or None if no valid date is found.
    """

    # Format the current date
    current_date = dt.datetime.strptime(current_date, "%Y-%m-%d")
    
    # Define months that are multiples of 3
    months = [3, 6, 9, 12]
    
    # Create a list of dates for the 1st of the month, including last December
    dates = [dt.datetime(current_date.year, month, 1) for month in months] + [dt.datetime(current_date.year - 1, 12, 1)]

    if before:
        # Filter dates to include only those before or on the current date
        dates = [date for date in dates if date <= current_date]
        csv_date = max(dates) if dates else None
    else:
        # Filter dates to include only those after the current date
        dates = [date for date in dates if date > current_date]
        csv_date = min(dates) if dates else None

    if csv_date:
        return csv_date.strftime("%Y-%m-%d")
    else:
        return None

def fundamentals_csv(stock, end_date, backtest=False):
    """
    Retrieve the fundamentals of a stock and save the data to a CSV file.

    Parameters:
    - stock (str): The stock ticker symbol.
    - end_date (str): The end date for the data in 'YYYY-MM-DD' format.
    - backtest (bool, optional): If True, limits retries. Default to False.

    Returns:
    - pd.DataFrame or None: The DataFrame containing stock fundamentals if successful, or None if an error occurs.
    """
    
    stock = stock.replace("-", ".")

    # Get the latest CSV date
    csv_date = get_csv_date(end_date)

    # Define the folder path for storing CSV files
    folder_path = "Fundamentals"

    # Check for existing data files
    current_files = [file for file in os.listdir(folder_path) if file.startswith(f"{stock}_fundamentals_")]

    # Extract dates from existing files
    dates = [file.split("_")[-1].replace(".csv", "") for file in current_files]

    # Determine the maximum date from the list of existing dates
    max_date = max(dates) if dates else "N/A"

    # Remove old files for dates prior to the maximum date
    if max_date != "N/A":
        for date in dates:
            if date < max_date:
                os.remove(os.path.join(folder_path, f"{stock}_fundamentals_{date}.csv"))
        # Define the filename based on the comparison of csv_date and max_date
        if csv_date > max_date:
            filename = os.path.join(folder_path, f"{stock}_fundamentals_{csv_date}.csv")
        else:
            filename = os.path.join(folder_path, f"{stock}_fundamentals_{max_date}.csv")
    else:
        filename = os.path.join(folder_path, f"{stock}_fundamentals_{csv_date}.csv")
    
    # Save the data to a CSV file if the most updated data does not exist
    if not os.path.isfile(filename):
        try:
            stock_upper = stock.upper()
            url_revenue = f"https://www.macrotrends.net/stocks/charts/{stock_upper}/unknown/revenue"
            max_retry = 2 if backtest else 10
            response_revenue = scrape(url_revenue, max_retry=max_retry)

            try:
                base_url = response_revenue.url

            except AttributeError:
                base_url = None
                print(f"AttributeError: response_revenue = {response_revenue}")
                return None

            # Extract the infix from the base URL
            infix = base_url.split("/")[-2]

            # Set the URLs for scraping income statement and financial ratios
            url1 = f"https://www.macrotrends.net/stocks/charts/{stock_upper}/{infix}/income-statement?freq=Q"
            url2 = f"https://www.macrotrends.net/stocks/charts/{stock_upper}/{infix}/financial-ratios?freq=Q"

            # Scrape the URLs and create DataFrames
            response1 = scrape(url1, max_retry=max_retry)
            df1 = etl(response1)
            response2 = scrape(url2, max_retry=max_retry)
            df2 = etl(response2)

            # Check if either DataFrame is empty
            if df1.empty or df2.empty:
                print(f"Empty dataframe for {stock}.")

                # Attempt to retrieve existing data
                if max_date != "N/A":
                    print(f"Try to retrieve existing data at {max_date}.")
                    filename = os.path.join(folder_path, f"{stock}_fundamentals_{max_date}.csv")
            
            else:
                # Concatenate DataFrames and save to CSV
                df = pd.concat([df1, df2], axis=1)
                df.index.name = "Date"
                df.to_csv(filename)
                print(f"Fundamentals data download completed for {stock}.")
            
                # Remove the old file for the maximum date
                if max_date != "N/A":
                    os.remove(os.path.join(folder_path, f"{stock}_fundamentals_{max_date}.csv"))
        
        except Exception as e:
            print(f"Error for {stock}: {e}\n")

    else:
        print(f"Fundamentals data download completed for {stock} before.\n")

    # Read the fundamentals data from the CSV file if it exists
    if os.path.isfile(filename):
        df = pd.read_csv(filename)
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        return df
    else:
        print(f"File not found: {filename}.")
        return None

def fundamentals_map(x):
    """
    Convert a percentage string to a float.

    Parameters:
    - x (str): The percentage string.

    Returns:
    - float: The numeric value of the percentage or "N/A" if conversion fails.
    """

    try:
        return float(x.replace("%", ""))
    
    except ValueError:
        return "N/A"
    
def earning_dates_csv(stock, end_date):
    """
    Retrieve the earning dates of a stock and save the data to a CSV file.

    Parameters:
    - stock (str): The stock ticker symbol.
    - end_date (str): The end date for the data in 'YYYY-MM-DD' format.

    Returns:
    - pd.DataFrame or None: The DataFrame containing earning dates if successful, or None if an error occurs.
    """

    stock = stock.replace("-", ".")

    # Get the latest CSV date
    csv_date = get_csv_date(end_date)

    # Define the folder path for storing CSV files
    folder_path = "Fundamentals"

    # Check for existing data files
    current_files = [file for file in os.listdir(folder_path) if file.startswith(f"{stock}_earningdates_")]

    # Extract dates from existing files
    dates = [file.split("_")[-1].replace(".csv", "") for file in current_files]

    # Determine the maximum date from the list of existing dates
    max_date = max(dates) if dates else "N/A"

    # Remove old files for dates prior to the maximum date
    if max_date != "N/A":
        for date in dates:
            if date < max_date:
                os.remove(os.path.join(folder_path, f"{stock}_earningdates_{date}.csv"))
        # Define the filename based on the comparison of csv_date and max_date
        if csv_date > max_date:
            filename = os.path.join(folder_path, f"{stock}_earningdates_{csv_date}.csv")
        else:
            filename = os.path.join(folder_path, f"{stock}_earningdates_{max_date}.csv")
    else:
        filename = os.path.join(folder_path, f"{stock}_earningdates_{csv_date}.csv")

    # Save the data to a CSV file if the most updated data does not exist
    if not os.path.isfile(filename):
        try:
            # Set the URL for scraping earning dates
            url = f"https://www.alphaquery.com/stock/{stock}/earnings-history"

            # Create DataFrame by scraping the table from the URL
            df = pd.read_html(url)[0]

            # Check if the DataFrame is empty
            if df.empty:
                print(f"Empty dataframe for {stock}.")

                # Attempt to retrieve existing data
                if max_date != "N/A":
                    print(f"Try to retrieve existing data at {max_date}.")
                    filename = os.path.join(folder_path, f"{stock}_earningdates_{max_date}.csv")

            else:
                df.to_csv(filename)
                print(f"Earning dates data download completed for {stock}.")

                # Remove the old file for the maximum date
                if max_date != "N/A":
                    os.remove(os.path.join(folder_path, f"{stock}_earningdates_{max_date}.csv"))

        except Exception as e:
            print(f"Error for {stock}: {e}.\n")

    else:
        print(f"Earning dates data download completed for {stock} before.\n")

    # Read the earning dates data from the CSV file if it exists
    if os.path.isfile(filename):
        df = pd.read_csv(filename)
        return df
    else:
        print(f"File not found: {filename}.")
        return None

def get_earning_dates(stock, current_date):
    """
    Retrieve the earning announcement dates for a given stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - current_date (str): The current date in 'YYYY-MM-DD' format.

    Returns:
    - list: A list of earning announcement dates.
    """

    try: 
        # Get the latest CSV date
        csv_date = get_csv_date(current_date)

        # Retrieve the DataFrame containing earning dates
        df = earning_dates_csv(stock, csv_date)

        # Get the list of announcement dates and reverse the order
        earning_dates = df["Announcement Date"].tolist()[::-1]

    except Exception as e:
        print(f"Error for {stock}: {e}.")
        earning_dates = []

    try:
        # Get future earning dates from yfinance
        calendar = yf.Ticker(stock).calendar

        # Check if "Earnings Date" is available in the calendar data
        if "Earnings Date" in calendar:
            future_earning_dates = [date.strftime("%Y-%m-%d") for date in calendar["Earnings Date"]]
            # Append future earning dates to the list
            earning_dates.extend(future_earning_dates)
        else:
            print("Next earnings date not available in the calendar data.")

    except Exception as e:
        print(f"Error for {stock}: {e}.")

    return earning_dates

def get_market_cap(stock, stock_info, end_date, current_date, backtest=False):
    """
    Retrieve the market capitalisation of a given stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - stock_info (dict): A dictionary containing stock information.
    - end_date (str): The end date for the data in 'YYYY-MM-DD' format.
    - current_date (str): The current date in 'YYYY-MM-DD' format.
    - backtest (bool, optional): If True, limits retries. Default to False.

    Returns:
    - float or str: The market capitalisation in billions or "N/A" if not available.
    """

    try:
        # Get the earning dates
        earning_dates = get_earning_dates(stock, current_date)

        # Filter the earning dates
        earning_dates = [earning_date for earning_date in earning_dates if earning_date < current_date]

    except Exception as e:
        print(f"Error getting earnings dates {stock}: {e}\n")
        earning_dates = []

    # Get the most recent earning date
    if earning_dates:
        recent_earning_date = max(earning_dates)
    else:
        recent_earning_date = current_date

    # Read the fundamentals data from the CSV file if end date is earlier than the recent earning date
    if end_date < recent_earning_date:
        if earning_dates:
            # Filter the earning dates
            earning_dates = [earning_date for earning_date in earning_dates if earning_date < end_date]
            
            # Get the most recent report date
            recent_report_date = max(earning_dates)

            # Estimate the recent report date by shifting 3 months backwards from end date
        else:
            recent_report_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(months=3)).strftime("%Y-%m-%d")

        # Get the latest CSV date
        csv_date = get_csv_date(current_date)

        # Read the fundamentals data from the CSV file
        df = fundamentals_csv(stock, csv_date, backtest=backtest)

        # Check if the DataFrame is None
        if df is not None:
            # Filter the dates
            dates = df.index[df.index <= recent_report_date]

            # Get the closest date
            closest_date = dates[0]

            # Get the number of shares outstanding
            shares = df.loc[closest_date, "shares-outstanding"] * 1e6

            # Get the price data of the stock
            df = get_df(stock, end_date)

            # Get the latest closing price
            closest_close = df.loc[df.index[df.index <= closest_date].max(), "Close"]

            # Calculate the market capitalisation
            market_cap = round(shares * closest_close / 1e9, 2)
        
        else:
            market_cap = "N/A"
        
    else:
        # Retrieve market cap from stock_info if no recent earnings date
        market_cap = stock_info.get("marketCap", "N/A")
        market_cap = round(market_cap / 1e9, 2) if market_cap != "N/A" else "N/A"

    return market_cap

def get_fundamentals(stock, end_date, current_date, columns=["EPS past 5Y", "EPS this Y", "EPS Q/Q", "ROE"], backtest=False):
    """
    Retrieve the fundamentals data of a stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - end_date (str): The end date for the data in 'YYYY-MM-DD' format.
    - current_date (str): The current date in 'YYYY-MM-DD' format.
    - columns (list, optional): List of columns to retrieve; defaults to specific EPS and ROE values.
    - backtest (bool, optional): If True, limits retries. Default to False.

    Returns:
    - tuple: A tuple containing EPS past 5Y growth, EPS this Y growth, EPS Q/Q growth, and ROE.
    """
    
    try:
        # Get the earning dates
        earning_dates = get_earning_dates(stock, current_date)

        # Filter the earning dates
        earning_dates = [earning_date for earning_date in earning_dates if earning_date < current_date]

    except Exception as e:
        print(f"Error getting earnings dates {stock}: {e}\n")
        earning_dates = []

    # Get the most recent earning date
    if earning_dates:
        recent_earning_date = max(earning_dates)
    else:
        recent_earning_date = current_date

    # Read the fundamentals data from CSV if end date is earlier than recent earning date
    if end_date < recent_earning_date:
        if earning_dates:
            # Filter the earning dates
            earning_dates = [earning_date for earning_date in earning_dates if earning_date < end_date]
            
            # Get the most recent report date
            recent_report_date = max(earning_dates)

            # Estimate the recent report date by shifting 3 months backwards from end date
        else:
            recent_report_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(months=3)).strftime("%Y-%m-%d")

        # Get the latest CSV date
        csv_date = get_csv_date(current_date)

        # Read the fundamentals data from the CSV file
        df = fundamentals_csv(stock, csv_date, backtest=backtest)

        # Check if the DataFrame is None
        if df is not None:
            # Filter the dates
            dates = df.index[df.index <= recent_report_date]

            # Get the closest date
            closest_date = dates[0]
            past_dates_annual = {str(i): dates[i * 4 - 1] if i * 4 - 1 < len(dates) else None for i in [1, 2, 5, 6]}
            past_dates_quarter = {str(i): dates[i] if i < len(dates) else None for i in [1, 2, 3]}
            
            # Get the earnings per share (EPS) values
            EPS_thisQ = df.loc[closest_date, "eps-basic-net-earnings-per-share"]
            EPS_last3Q = df.loc[past_dates_quarter["3"], "eps-basic-net-earnings-per-share"] if past_dates_quarter["3"] is not None else "N/A"

            try:
                EPS_thisY = df.loc[closest_date : past_dates_annual["1"], "eps-basic-net-earnings-per-share"].sum()
            except Exception:
                EPS_thisY = "N/A"
            try:
                EPS_last5Y = df.loc[past_dates_annual["5"] : past_dates_annual["6"], "eps-basic-net-earnings-per-share"].sum()
            except Exception:
                EPS_last5Y = "N/A"
            try:
                EPS_lastY = df.loc[past_dates_annual["1"] : past_dates_annual["2"], "eps-basic-net-earnings-per-share"].sum()
            except Exception:
                EPS_lastY = "N/A"

            # Calculate the growth rates of EPS values
            EPS_past5Y_growth = round(1 / 5 * (EPS_thisY / EPS_last5Y) / np.abs(EPS_last5Y) * 100, 2) if EPS_thisY != "N/A" and EPS_last5Y != "N/A" and EPS_last5Y != 0 else "N/A"
            EPS_thisY_growth = round((EPS_thisY - EPS_lastY) / np.abs(EPS_lastY) * 100, 2) if EPS_thisY != "N/A" and EPS_lastY != "N/A" and EPS_lastY != 0 else "N/A"
            EPS_QoQ_growth = round((EPS_thisQ - EPS_last3Q) / np.abs(EPS_last3Q) * 100, 2) if EPS_thisQ != "N/A" and EPS_last3Q != "N/A" and EPS_last3Q != 0 else "N/A"
            
            # Get the ROE
            ROE = round(df.loc[closest_date, "roe"], 2)

        else:
            EPS_past5Y_growth, EPS_thisY_growth, EPS_QoQ_growth, ROE = None, None, None, None

    # Scrape the fundamentals data from Finviz if end date is later than recent earning date
    else:
        quote = Quote(ticker=stock)
        fundamental_df = quote.fundamental_df.loc[:, columns].map(fundamentals_map)
        data = fundamental_df.values[0]
        EPS_past5Y_growth, EPS_thisY_growth, EPS_QoQ_growth, ROE = *data,
    
    return EPS_past5Y_growth, EPS_thisY_growth, EPS_QoQ_growth, ROE

def get_lastQ_growths(stock, index_name, end_date, current_date, backtest=False):
    """
    Get the quarterly growths of a stock.

    Parameters:
    - stock (str): The stock ticker symbol.
    - index_name (str): The index name to identify stock exchange.
    - end_date (str): The end date for the data in 'YYYY-MM-DD' format.
    - current_date (str): The current date in 'YYYY-MM-DD' format.
    - backtest (bool, optional): If True, limits retries. Default to False.

    Returns:
    - tuple: A tuple containing EPS this Q growth, EPS last 1Q growth, and EPS last 2Q growth.
    """

    try:
        # Get the earning dates
        earning_dates = get_earning_dates(stock, current_date)
        earning_dates = [earning_date for earning_date in earning_dates if earning_date < current_date]

    except Exception as e:
        print(f"Error getting earnings dates {stock}: {e}\n")
        earning_dates = []

    # Return "N/A" for HKEX stocks
    if index_name == "^HSI":
        EPS_thisQ_growth, EPS_last1Q_growth, EPS_last2Q_growth = "N/A", "N/A", "N/A"
    
    # Handle non-HKEX stocks
    else:
        if earning_dates:
            # Filter the earning dates
            earning_dates = [earning_date for earning_date in earning_dates if earning_date < end_date]
            
            # Get the most recent report date
            recent_report_date = max(earning_dates)

        # Estimate the recent report date by shifting 3 months backward from end date
        else:
            recent_report_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(months=3)).strftime("%Y-%m-%d")

        # Get the CSV date
        csv_date = get_csv_date(current_date)
        
        # Read the fundamentals data from CSV       
        df = fundamentals_csv(stock, csv_date, backtest=backtest)

        # Check if the DataFrame is None
        if df is not None:
            # Filter the dates
            dates = df.index[df.index <= recent_report_date]

            # Get the closest date
            closest_date = dates[0]
            past_dates_quarter = {str(i): dates[i] if i < len(dates) else None for i in [1, 2, 3]}
            
            # Get the EPS values
            EPS_thisQ = df.loc[closest_date, "eps-basic-net-earnings-per-share"]
            EPS_last1Q = df.loc[past_dates_quarter["1"], "eps-basic-net-earnings-per-share"] if past_dates_quarter["1"] is not None else "N/A"
            EPS_last2Q = df.loc[past_dates_quarter["2"], "eps-basic-net-earnings-per-share"] if past_dates_quarter["2"] is not None else "N/A"
            EPS_last3Q = df.loc[past_dates_quarter["3"], "eps-basic-net-earnings-per-share"] if past_dates_quarter["3"] is not None else "N/A"
            
            # Calculate the growth rates of EPS values
            EPS_thisQ_growth = round((EPS_thisQ - EPS_last1Q) / np.abs(EPS_last1Q) * 100, 2) if EPS_last1Q != "N/A" else "N/A"
            EPS_last1Q_growth = round((EPS_last1Q - EPS_last2Q) / np.abs(EPS_last2Q) * 100, 2) if EPS_last2Q != "N/A" else "N/A"
            EPS_last2Q_growth = round((EPS_last2Q - EPS_last3Q) / np.abs(EPS_last3Q) * 100, 2) if EPS_last3Q != "N/A" else "N/A"

        else:
            EPS_thisQ_growth, EPS_last1Q_growth, EPS_last2Q_growth = "N/A", "N/A", "N/A"

    return EPS_thisQ_growth, EPS_last1Q_growth, EPS_last2Q_growth