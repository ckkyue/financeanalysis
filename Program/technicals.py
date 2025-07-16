# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
from helper_functions import get_df, slope_reg
import numpy as np
import os
import pandas as pd
pd.options.mode.chained_assignment = None
from scipy.stats import linregress
from tqdm import tqdm

def create_rs_volume_df(stocks, dfs, end_dates, periods, index_returns, index_shortName, result_folder, infix, backtest, print_multiple=True):
    """
    Create dataframes to store relative strength (RS) ratings and volume ranks for stocks.
    
    Parameters:
    - stocks (list): List of stock identifiers to process.
    - dfs (dict): Dictionary mapping stock identifiers to their respective DataFrames.
    - end_dates (list): List of end dates for the analysis.
    - periods (list): List of periods for cumulative return calculations.
    - index_returns (list): List of index returns corresponding to each period.
    - index_shortName (str): Short name of the index for display purposes.
    - result_folder (str): Directory to save the results.
    - infix (str): Infix to include in filenames.
    - backtest (bool): If True, skip saving results to files.
    - print_multiple (bool): If True, print return multiples for stocks.

    Returns:
    - rs_dfs (DataFrame or list of DataFrames): DataFrame(s) containing RS ratings.
    - volume_dfs (DataFrame or list of DataFrames): DataFrame(s) containing volume ranks.
    - rs_volume_dfs (DataFrame or list of DataFrames): DataFrame(s) containing merged RS and volume data.
    """

    # Convert inputs to lists if they are not already
    if not isinstance(end_dates, list):
        end_dates = [end_dates]
    if not isinstance(periods, list):
        periods = [periods]
    if not isinstance(index_returns, list):
        index_returns = [index_returns]

    # Initialise lists to store results
    rs_dfs = []
    volume_dfs = []
    rs_volume_dfs = []
    
    # Iterate over combinations of end dates, periods, and index returns
    for end_date, period, index_return in zip(end_dates, periods, index_returns):
        return_muls = {}
        volume_smas = {}

        # Iterate over each stock
        for stock in tqdm(stocks, desc=f"Processing data for {end_date}"):
            try:
                df = dfs.get(stock)
                if df is None:
                    continue
                
                # Filter the DataFrame for dates before the end date
                df = df[df.index < end_date]

                # Calculate percent change and stock return
                df["Percent Change"] = df["Close"].pct_change()

                # Calculate return relative to the market
                stock_return = (df["Percent Change"] + 1).tail(period).cumprod().iloc[-1]

                # Calculate the stock return relative to the market
                return_mul = stock_return / index_return
                return_muls[stock] = return_mul
                if print_multiple:
                    print(f"Stock: {stock} ; Return multiple against {index_shortName}: {round(return_mul, 2)}\n")
                
                # Compute moving averages of volume
                df["Volume SMA 5"] = SMA(df, 5, col="Volume")
                df["Volume SMA 20"] = SMA(df, 20, col="Volume")
                volume_smas[stock] = {"Volume SMA 5": df["Volume SMA 5"].iloc[-1], "Volume SMA 20": df["Volume SMA 20"].iloc[-1]}

            except Exception as e:
                print(f"Error processing data for {stock}: {e}\n")
                continue
            
        # Create a DataFrame for RS ratings
        return_muls = dict(sorted(return_muls.items(), key=lambda x: x[1], reverse=True))
        rs_df = pd.DataFrame(return_muls.items(), columns=["Stock", "Value"])
        rs_df["RS"] = rs_df["Value"].rank(pct=True) * 100
        rs_df = rs_df[["Stock", "RS"]]

        # Create a DataFrame for volume ranks
        volume_df = pd.DataFrame.from_dict(volume_smas, orient="index", columns=["Volume SMA 5", "Volume SMA 20"])
        volume_df["Stock"] = volume_df.index
        volume_df.reset_index(drop=True, inplace=True)
        volume_df["Volume SMA 5 Rank"] = volume_df["Volume SMA 5"].rank(ascending=False)
        volume_df["Volume SMA 20 Rank"] = volume_df["Volume SMA 20"].rank(ascending=False)

        # Merge RS and volume DataFrames
        rs_volume_df = pd.merge(rs_df, volume_df, on="Stock")
        rs_volume_df = rs_volume_df.sort_values(by="RS", ascending=False)

        # Handle existing result files
        current_files = [file for file in os.listdir(result_folder) if file.startswith(f"{infix}rs{period}volume_")]

        # Get the list of dates
        dates = [file.split("_")[-1].replace(".csv", "") for file in current_files]

        # Remove old files with dates prior to the current end date
        for date in dates:
            if date < end_date:
                os.remove(os.path.join(result_folder, f"{infix}rs{period}volume_{date}.csv"))
                
        # Define the filename for saving results
        filename = os.path.join(result_folder, f"{infix}rs{period}volume_{end_date}.csv")

        # Save the merged DataFrame to a CSV file if not in backtest mode
        if not backtest:
            rs_volume_df.to_csv(filename, index=False)

        # Append DataFrames to the lists
        rs_dfs.append(rs_df)
        volume_dfs.append(volume_df)
        rs_volume_dfs.append(rs_volume_df)

    # Return results based on the number of processed dates
    if len(rs_dfs) == 1:
        return rs_dfs[0], volume_dfs[0], rs_volume_dfs[0]
    else:
        return rs_dfs, volume_dfs, rs_volume_dfs

def longshort_rs(stocks, index_df, index_name, index_dict, current_date, end_dates1, end_dates2, periods1, periods2, result_folder, infix, volume_filter=None):
    """
    Combine long-term and short-term relative strength (RS) dataframes for given stocks.

    Parameters:
    - stocks (list): List of stock identifiers to process.
    - index_df (DataFrame): DataFrame containing index data.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - current_date (str): The current date for filtering.
    - end_dates1 (list): List of end dates for long-term analysis.
    - end_dates2 (list): List of end dates for short-term analysis.

    Returns:
    - merged_dfs (DataFrame or list of DataFrames): Merged DataFrame(s) containing long-term and short-term RS data.
    """

    # Convert inputs to lists if they are not already
    if not isinstance(end_dates1, list):
        end_dates1 = [end_dates1]
    if not isinstance(end_dates2, list):
        end_dates2 = [end_dates2]
    if not isinstance(periods1, list):
        periods1 = [periods1]
    if not isinstance(periods2, list):
        periods2 = [periods2]
        
    # Initialise an empty list to store the merged dataframes
    merged_dfs = []

    # Initialise an empty list to store the index returns
    index_returns = []

    # Iterate over combinations of end dates and periods
    for end_date1, end_date2, period1, period2 in zip(end_dates1, end_dates2, periods1, periods2):
        # Filter the index data for the respective end dates
        index_df1 = index_df[index_df.index < end_date1]
        index_df2 = index_df[index_df.index < end_date2]

        # Calculate the percent change of the index
        index_df1.loc[:, "Percent Change"] = index_df1["Close"].pct_change()
        index_df2.loc[:, "Percent Change"] = index_df2["Close"].pct_change()
        
        # Calculate the total return of the index for the specified periods
        index_return1 = (index_df1["Percent Change"] + 1).tail(period1).cumprod().iloc[-1]
        index_return2 = (index_df2["Percent Change"] + 1).tail(period2).cumprod().iloc[-1]
        index_shortName = index_dict[f"{index_name}"]
        print(f"Return for {index_shortName} between {index_df1.index[-period1].strftime('%Y-%m-%d')} and {end_date1}: {index_return1:.2f}")
        print(f"Return for {index_shortName} between {index_df2.index[-period2].strftime('%Y-%m-%d')} and {end_date2}: {index_return2:.2f}")

        # Store index returns
        index_returns.extend([index_return1, index_return2])

    # Create RS and volume DataFrames 
    rs_dfs, volume_dfs, _ = create_rs_volume_df(stocks, current_date, end_dates1 + end_dates2, periods1 + periods2, index_returns, index_shortName, result_folder, infix, True, print_multiple=False)

    # Separate the DataFrames into two halves
    length_df = len(rs_dfs) // 2
    rs_dfs1, rs_dfs2 = rs_dfs[:length_df], rs_dfs[length_df:]
    volume_dfs1, volume_dfs2 = volume_dfs[:length_df], volume_dfs[length_df:]

    # Merge the long-term and short-term RS DataFrames
    for rs_df1, rs_df2, volume_df1, volume_df2 in zip(rs_dfs1, rs_dfs2, volume_dfs1, volume_dfs2):
        # Apply volume filter if specified
        if volume_filter is not None:
            volume_df1 = volume_df1[(volume_df1["Volume SMA 5 Rank"] <= volume_filter) | (volume_df1["Volume SMA 20 Rank"] <= volume_filter)]
            volume_df2 = volume_df2[(volume_df2["Volume SMA 5 Rank"] <= volume_filter) | (volume_df2["Volume SMA 20 Rank"] <= volume_filter)]

            # Filter RS DataFrames based on the stocks present in volume DataFrames
            rs_df1 = rs_df1[rs_df1["Stock"].isin(set(volume_df1["Stock"]))]
            rs_df2 = rs_df2[rs_df2["Stock"].isin(set(volume_df2["Stock"]))]

        # Merge and clean data
        merged_df = pd.merge(rs_df1, rs_df2, on="Stock", suffixes=(" 1", " 2"))
        merged_df = merged_df.rename(columns={"RS 1": "Long-term RS", "RS 2": "Short-term RS"}).dropna()
        merged_dfs.append(merged_df)

    # Return a single DataFrame if only one is created, otherwise return a list of DataFrames
    return merged_dfs[0] if len(merged_dfs) == 1 else merged_dfs

def compare_longshort_rs(stocks, index_df, index_name, index_dict, current_date, end_dates, period1, period2, result_folder, infix):
    """
    Compare long-term and short-term relative strength (RS) for given stocks.

    Parameters:
    - stocks (list): List of stock identifiers to process.
    - index_df (DataFrame): DataFrame containing index data.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - current_date (str): The current date for filtering.
    - end_dates (list): List of end dates for analysis.
    - period1 (int): Period for long-term return calculations.
    - period2 (int): Period for short-term return calculations.
    - result_folder (str): Directory to save results.
    - infix (str): Infix to include in filenames.

    Returns:
    - rs_slopes (list): List of slopes of the regression lines for each merged DataFrame.
    - r_squareds (list): List of R-squared values for each merged DataFrame.
    - end_dates2 (list): List of calculated end dates for short-term analysis.
    """

    # Initialise lists to store RS slopes and R^2 values
    rs_slopes = []
    r_squareds = []

    # Define end dates for long-term and short-term analysis
    end_dates1 = []
    end_dates2 = []
    for i in range(len(end_dates) - 1):
        end_date = end_dates[i]
        end_dates1.append(end_date)
        end_dates2.append((dt.datetime.strptime(end_date, "%Y-%m-%d") + relativedelta(days=20)).strftime("%Y-%m-%d"))

    periods1 = [period1] * len(end_dates1)
    periods2 = [period2] * len(end_dates2)

    # Get the merged DataFrame containing long-term and short-term RS data
    merged_dfs = longshort_rs(stocks, index_df, index_name, index_dict, current_date, end_dates1, end_dates2, periods1, periods2, result_folder, infix)
    
    # Iterate over each merged DataFrame to calculate slopes and R^2 values
    for merged_df in merged_dfs:
        # Perform linear regression to find the slope and R^2
        rs_slope, _, r_value, _, _ = linregress(merged_df["Long-term RS"], merged_df["Short-term RS"])
        r_squared = r_value**2
        rs_slopes.append(rs_slope)
        r_squareds.append(r_squared)
        
    return rs_slopes, r_squareds, end_dates2

def SMA(data, period, col="Close"):
    """
    Calculate the Simple Moving Average (SMA) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the SMA.
    - col (str): The column name to calculate the SMA on. Default is "Close".

    Returns:
    - Series: The calculated SMA values.
    """

    return data[col].rolling(window=period).mean()

def EMA(data, period, col="Close"):
    """
    Calculate the Exponential Moving Average (EMA) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the EMA.
    - col (str): The column name to calculate the EMA on. Default is "Close".

    Returns:
    - Series: The calculated EMA values.
    """

    return data[col].ewm(span=period, adjust=False).mean()

def get_volatility(data, periods=[20, 60], col="Close"):
    """
    Calculate the volatility of the stock returns over specified periods.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - periods (list): List of periods over which to calculate volatility. Default is [20, 60].
    - col (str): The column name to calculate volatility on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added volatility columns.
    """

    data_copy = data.copy()

    # Calculate the percent change of the stock
    data_copy.loc[:, "Percent Change"] = data_copy[col].pct_change()

    # Calculate the volatility for each specified period
    for period in periods:
        data[f"Volatility {period}"] = data_copy["Percent Change"].rolling(window=period).std()

    return data

def ATR(data, period=14, col="Close"):
    """
    Calculate the Average True Range (ATR) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the ATR. Default is 14.
    - col (str): The column name to calculate the ATR on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added TR and ATR columns.
    """
    
    # Calculate the true range (TR)
    TR = pd.concat([
        abs(data["High"] - data["Low"]),
        abs(data["High"] - data[col].shift()),
        abs(data["Low"] - data[col].shift())
        ], axis=1).max(axis=1)
    
    # Calculate the ATR by EMA of TR
    ATR = TR.ewm(span=period, adjust=False).mean()
    data["TR"] = TR
    data["ATR"] = ATR

    return data

def RMV(data, period_short=5, period_long=14, col="Close"):
    """
    Calculate the Relative Measured Volatility (RMV) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period_short (int): The short period for calculating the SMA of TR/ATR. Default is 5.
    - period_long (int): The long period for calculating the ATR and RMV. Default is 14.
    - col (str): The column name to calculate the RMV on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added columns for TR/ATR, TR/ATR SMA, and RMV.
    """

    # Calculate the True Range (TR) and Average True Range (ATR)
    data = ATR(data, period=period_long, col=col)

    # Calculate the ratio of TR to ATR
    data["TR/ATR"] = data["TR"] / data["ATR"]

    # Calculate the SMA of the TR/ATR ratio over the short period
    data[f"TR/ATR SMA {period_short}"] = SMA(data, period=period_short, col="TR/ATR")
    
    # Calculate the RMV
    data["RMV"] = 100 * (data[f"TR/ATR SMA {period_short}"] - data[f"TR/ATR SMA {period_short}"].rolling(window=period_long).min()) / \
                (data[f"TR/ATR SMA {period_short}"].rolling(window=period_long).max() - data[f"TR/ATR SMA {period_short}"].rolling(window=period_long).min())

    return data

def MACD(data, period_long, period_short, period_signal, col="Close"):
    """
    Calculate the Moving Average Convergence Divergence (MACD) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period_long (int): The period for the long EMA.
    - period_short (int): The period for the short EMA.
    - period_signal (int): The period for the signal line.
    - col (str): The column name to calculate the MACD on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added MACD and signal line columns.
    """

    # Calculate the short EMA
    EMA_short = EMA(data, period_short, col=col)

    # Calculate the long EMA
    EMA_long = EMA(data, period_long, col=col)

    # Calculate the MACD
    data["MACD"] = EMA_short - EMA_long

    # Calculate the signal line
    data["MACD Signal Line"] = EMA(data, period_signal, col="MACD")

    # Calculate the MACD bar
    data["MACD Bar"] = data["MACD"] - data["MACD Signal Line"]
    
    return data

def RSI(data, period=14, col="Close"):
    """
    Calculate the Relative Strength Index (RSI) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the RSI. Default is 14.
    - col (str): The column name to calculate the RSI on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added RSI column.
    """

    # Calculate the change of the stock
    data["Change"] = data[col].diff()

    # Calculate gains and losses
    gain = data["Change"].copy()
    loss = data["Change"].copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0

    # Calculate relative strength (RS)
    RS = gain.rolling(window=period).mean() / abs(loss.rolling(window=period).mean())

    # Calculate the RSI
    RSI = 100 - (100 / (1 + RS))
    data["RSI"] = RSI

    return data

def RMI(data, period=20, momentum=3, col="Close"):
    """
    Calculate the Relative Momentum Index (RMI) for a given column.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the RMI. Default is 20.
    - momentum (int): The number of periods for momentum calculation. Default is 3.
    - col (str): The column name to calculate the RMI on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added RMI column.
    """

    data_copy = data.copy()

    # Calculate the change of the stock
    data_copy["Change"] = data_copy[col].diff(momentum)[momentum:]

    # Calculate the gains and losses
    gain = data_copy["Change"].copy()
    loss = data_copy["Change"].copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0

    # Calculate relative momentum (RM)
    RM = gain.rolling(window=period).mean() / abs(loss.rolling(window=period).mean())

    # Calculate the RMI
    RMI = 100 - (100 / (1 + RM))
    data["RMI"] = RMI

    return data

def MFI(data, period=14):
    """
    Calculate the Money Flow Index (MFI) for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the MFI. Default is 14.

    Returns:
    - DataFrame: The DataFrame with added MFI column.
    """

    data_copy = data.copy()

    # Calculate HLC3, Raw MF, and the change of HLC3
    data_copy["HLC3"] = (data_copy["High"] + data_copy["Low"] + data_copy["Close"]) / 3
    data_copy["Raw MF"] = data_copy["HLC3"] * data_copy["Volume"]
    data_copy["HLC3 Change"] = data_copy["HLC3"].diff()

    # Calculate +MF and -MF
    data_copy["+MF"] = np.where(data_copy["HLC3 Change"] > 0, data_copy["Raw MF"], 0)
    data_copy["-MF"] = np.where(data_copy["HLC3 Change"] < 0, data_copy["Raw MF"], 0)

    # Calculate the sum of +MF and -MF over a period
    data_copy["+MF Sum"] = data_copy["+MF"].rolling(window=period).sum()
    data_copy["-MF Sum"] = data_copy["-MF"].rolling(window=period).sum()

    # Calculate the MF ratio
    data_copy["MF Ratio"] = data_copy["+MF Sum"] / abs(data_copy["-MF Sum"])

    # Calcualte the MFI
    data["MFI"] = 100 - (100 / (1 + data_copy["MF Ratio"]))

    return data

def PVT(data):
    """
    Calculate the Price Volume Trend Indicator (PVT) for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.

    Returns:
    - DataFrame: The DataFrame with added PVT column.
    """

    data_copy = data.copy()

    # Calculate PVT
    data_copy["PVT"] = 0
    data_copy["Percent Change"] = data_copy["Close"].pct_change()
    data["PVT"] = (data_copy["Percent Change"] * data_copy["Volume"]).cumsum().fillna(0)

    return data

def CCI(data, period=20):
    """
    Calculate the Commodity Channel Index (CCI) for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the CCI. Default is 20.

    Returns:
    - DataFrame: The DataFrame with added CCI column.
    """

    data_copy = data.copy()
    
    # Calculate the average of high, low and closing prices (HLC3)
    data_copy["HLC3"] = (data_copy["High"] + data_copy["Low"] + data_copy["Close"]) / 3

    # Calculate the moving average of HLC3
    data_copy["MA"] = data_copy["HLC3"].rolling(window=period).mean()

    # Calculate the CCI
    data["CCI"] = (data_copy["HLC3"] - data_copy["MA"]) / (0.015 * data_copy["HLC3"].rolling(window=period).std())

    return data

def ADX(data, period=14):
    """
    Calculate the Average Directional Index (ADX) for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the ADX. Default is 14.

    Returns:
    - DataFrame: The DataFrame with added ADX column.
    """

    data_copy = data.copy()

    # Calculate the ATR
    data_copy = ATR(data_copy, period=period)

    # Calculate +DM and -DM
    data_copy["+DM"] = np.where((data_copy["High"] - data_copy["High"].shift()) > np.maximum((data_copy["Low"].shift() - data_copy["Low"]), 0), 
                                data_copy["High"] - data_copy["High"].shift(), 0)
    
    data_copy["-DM"] = np.where((data_copy["Low"].shift() - data_copy["Low"]) > np.maximum((data_copy["High"] - data_copy["High"].shift()), 0), 
                                data_copy["Low"].shift() - data_copy["Low"], 0)

    # Calculate the +DI and -DI by EMA of +DM and -DM, divided by ATR
    data_copy["+DI"] = EMA(data_copy, period, col="+DM") / data_copy["ATR"]
    data_copy["-DI"] = EMA(data_copy, period, col="-DM") / data_copy["ATR"]

    # Calculate the DX
    data_copy["DX"] = (np.abs(data_copy["+DI"] - data_copy["-DI"]) / (data_copy["+DI"] + data_copy["-DI"])) * 100

    # Calculate the ADX
    data["ADX"] = EMA(data_copy, period, col="DX")

    return data

def signal_bar(data):
    """
    Calculates the signal bar indicator for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.

    Returns:
    - DataFrame: The DataFrame with added signal bar columns.
    """

    data_copy = data.copy()

    # Calculate the positive signal bar
    data["+ Bar"] = np.where((data_copy["High"] > data_copy["High"].shift(1)) & 
                              (data_copy["Close"] > data_copy["Open"]), - 1, 0)

    # Calculate the negative signal bar
    data["- Bar"] = np.where((data_copy["Low"] < data_copy["Low"].shift(1)) & 
                             (data_copy["Close"] < data_copy["Open"]), 1, 0)

    return data

def OBOS(data, period=14, col="Close"):
    """
    Calculate the Overbought/Oversold (OB/OS) indicator for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period (int): The number of periods over which to calculate the OBOS. Default is 14.
    - col (str): The column name to calculate the OBOS on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added OBOS column.
    """

    data_copy = data.copy()

    # Calculate the highest and lowest closing price over the past period
    data_copy["HC"] = data_copy[col].rolling(window=period).max()
    data_copy["LC"] = data_copy[col].rolling(window=period).min()

    # Calculate the OB/OS indicator
    data["OBOS"] = (data_copy["Close"] - data_copy["LC"]) / (data_copy["HC"] - data_copy["LC"]) * 100

    return data

def MVP_VCP(data, period_MVP=15, period_VCP=10, contraction=0.05, period=60, col="Close"):
    """
    Calculate the MVP/VCP indicator for the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - period_MVP (int): The number of periods for the MVP calculation. Default is 15.
    - period_VCP (int): The number of periods for the VCP calculation. Default is 10.
    - contraction (float): The contraction threshold for VCP. Default is 0.05 (5%).
    - period (int): The number of periods to look back for counting occurrences. Default is 60.
    - col (str): The column name to calculate the MVP/VCP on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added MVP and VCP columns.
    """

    data_copy = data.copy()
    
    # Check if the M, V, and P conditions are met
    data_copy["M"] = data_copy["Close"].diff().rolling(window=period_MVP).apply(lambda x: (x > 0).sum()).ge(int(period_MVP * 0.8))
    data_copy["V"] = (data_copy["Volume"] >= data_copy["Volume"].shift(period_MVP) * 1.2)
    data_copy["P"] = (data_copy["Close"] >= data_copy["Close"].shift(period_MVP) * 1.2)
    data_copy["MVP"] = ""
    data_copy.loc[data_copy["M"] & ~data_copy["V"] & ~data_copy["P"], "MVP"] = "M"
    data_copy.loc[data_copy["M"] & data_copy["V"] & ~data_copy["P"], "MVP"] = "MV"
    data_copy.loc[data_copy["M"] & data_copy["P"] & ~data_copy["V"], "MVP"] = "MP"
    data_copy.loc[data_copy["M"] & data_copy["V"] & data_copy["P"], "MVP"] = "MVP"
    data["MVP"] = data_copy["MVP"]

    # Count the number of occurrences of M, V, and P over the past period
    data[f"M past {period}"] = data_copy["MVP"].apply(lambda x: x == "M").rolling(window=period).sum()
    data[f"MV past {period}"] = data_copy["MVP"].apply(lambda x: x == "MV").rolling(window=period).sum()
    data[f"MP past {period}"] = data_copy["MVP"].apply(lambda x: x == "MP").rolling(window=period).sum()
    data[f"MVP past {period}"] = data_copy["MVP"].apply(lambda x: x == "MVP").rolling(window=period).sum()

    # Calculate the MVP ratng
    data["MVP Rating"] = ((1 / 3 * data[f"M past {period}"]) + (2 / 3 * (data[f"MV past {period}"] + data[f"MP past {period}"])) + data[f"MVP past {period}"]) / 60 * 100

    # Calculate the highest, median, and lowest closing price over the past period
    data_copy["HC"] = data_copy[col].rolling(window=period_VCP).max()
    data_copy["MC"] = data_copy[col].rolling(window=period_VCP).median()
    data_copy["LC"] = data_copy[col].rolling(window=period_VCP).min()

    # Check if the highest and lowest closing prices differ by less than contraction
    data["VCP"] = (1 - data_copy["LC"] / data_copy["HC"]) <= contraction

    # Check if pivot breakout occurs
    data["Pivot breakout"] = data_copy[col] > 1 / 3 * (data_copy["HC"] + data_copy["MC"] + data_copy["LC"])

    # Check if the volume is shrinking
    data["Volume shrinking"] = data_copy["Volume"].rolling(window=period_VCP).apply(slope_reg) < 0
    
    return data

def FTD_DD(data, volume_period=50, ftd_threshold=0.015, dd_threshold=0.002, ftd_dd_period=20, col="Close"):
    """
    Check for Follow-Through Days (FTD) and Distribution Days (DD) in the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - volume_period (int): The number of periods to calculate the rolling mean for volume. Default is 50.
    - ftd_threshold (float): The percentage threshold for Follow-Through Days (FTD). Default is 0.015 (1.5%).
    - dd_threshold (float): The percentage threshold for Distribution Days (DD). Default is 0.002 (0.2%).
    - ftd_dd_period (int): The number of periods to consider for FTD and DD. Default is 20.
    - col (str): The column name to calculate FTD and DD on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added FTD, DD, Multiple FTDs, and Multiple DDs columns.
    """

    # Check FTD
    data["FTD"] = (data[col] > (1 + ftd_threshold) * data[col].shift(1)) \
        & (data["Volume"] > data["Volume"].shift(1)) \
        & (data["Volume"] > data["Volume"].rolling(window=volume_period).mean())

    # Check DD
    data["DD"] = (data[col] < (1 - dd_threshold) * data[col].shift(1)) \
    & (data["Volume"] > data["Volume"].shift(1)) \
    & (data["Volume"] > data["Volume"].rolling(window=volume_period).mean())

    # Check if there are at least four FTDs or DDs recently
    data["Multiple FTDs"] = data["FTD"].rolling(ftd_dd_period).sum() >= 4
    data["Multiple DDs"] = data["DD"].rolling(ftd_dd_period).sum() >= 4

    return data

def detect_exhaustion(data, volume_period=50, price_period=20, sd_threshold=1, col="Close"):
    """
    Detect exhaustion days based on volume and price movement criteria.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - volume_period (int): The number of periods for volume SMA calculation. Default is 50.
    - price_period (int): The number of periods for price change analysis. Default is 20.
    - sd_threshold (float): The standard deviation threshold for price increase. Default is 1.
    - col (str): The column name to calculate exhaustion on. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added exhaustion detection columns.
    """
    
    data_copy = data.copy()
    
    # Calculate volume SMA
    data_copy[f"Volume SMA {volume_period}"] = SMA(data_copy, volume_period, col="Volume")
    
    # Calculate percent change
    data_copy["Percent Change"] = data_copy[col].pct_change()
    
    # Calculate rolling mean and standard deviation of percent change
    data_copy[f"Percent Change Mean {price_period}"] = data_copy["Percent Change"].rolling(window=price_period).mean()
    data_copy[f"Percent Change SD {price_period}"] = data_copy["Percent Change"].rolling(window=price_period).std()

    # Calculate percent change z-score
    data_copy["Percent Change Z-Score"] = (data_copy["Percent Change"] - data_copy[f"Percent Change Mean {price_period}"]) / data_copy[f"Percent Change SD {price_period}"]

    # Detect exhaustion days
    data["Exhaustion"] = (data_copy["Volume"] > data_copy[f"Volume SMA {volume_period}"]) & (data_copy["Percent Change Z-Score"] > sd_threshold)

    # Add the calculated columns to the original DataFrame
    data["Percent Change Z-Score"] = data_copy["Percent Change Z-Score"]

    return data

def get_local_extrema(data, col_min="Low", col_max="High", period=5):
    """
    Locate local minima and maxima in the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - col_min (str): The column name to find local minima. Default is "Low".
    - col_max (str): The column name to find local maxima. Default is "High".
    - period (int): The number of periods to consider for local extrema. Default is 5.

    Returns:
    - DataFrame: The DataFrame with added Local Min and Local Max columns.
    """

    # Find local minima and maxima
    local_min = data[col_min].rolling(period, center=True, min_periods=2).min() == data[col_min]
    local_max = data[col_max].rolling(period, center=True, min_periods=2).max() == data[col_max]

    # Create new columns for local min and max locations
    data["Local Min"] = local_min
    data["Local Max"] = local_max

    return data

def calculate_retracement(data, col_min="Low", col_max="High", buffer=15):
    """
    Calculate the most recent retracement based on local extrema.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - col_min (str): The column name to find local minima. Default is "Low".
    - col_max (str): The column name to find local maxima. Default is "High".
    - buffer (int): The number of days to look back for local maxima. Default is 15.

    Returns:
    - np.array: An array containing the local minimum, local maximum, and retracement value.
    """

    # Identify the indices of local minima and maxima
    min_indices = data[data["Local Min"]].index
    max_indices = data[data["Local Max"]].index

    # Handle empty cases
    if min_indices.empty or max_indices.empty:
        return None

    # Get the most recent local minimum index
    min_index1 = min_indices[-1]

    # Initialise a list to hold the three most recent local maxima indices
    max_index_list = []

    # Iterate backwards to find the three most recent max
    for i in reversed(max_indices):
        if i < min_index1:
            max_index_list.append(i)
            if len(max_index_list) == 3:
                break

    # Handle empty cases
    if len(max_index_list) < 1:
        return None

    # Retrieve the value of the most recent local minimum
    local_min1 = data.loc[min_index1, col_min]
    
    # Get local maximum values corresponding to the identified indices
    local_max_values = [data.loc[index, col_max] for index in max_index_list]
    local_max = local_max_values[0]

    # Check the conditions for the second and third local maxima
    for i in range(1, len(local_max_values)):
        if (max_index_list[0] - max_index_list[i]).days <= buffer:
            local_max = max(local_max, local_max_values[i])

    retracement = 1 - local_min1 / local_max

    return np.array([local_min1, local_max, retracement])

def calculate_zscore(data, indicators, zscore_period):
    """
    Calculate the z-score for specified indicators in the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - indicators (str or list): The indicator(s) for which to calculate the z-score. Can be a single string or a list of strings.
    - zscore_period (int): The number of periods over which to calculate the mean and standard deviation.

    Returns:
    - DataFrame: The DataFrame with added columns for mean, standard deviation, and z-score of the indicators.
    """

    # Loop through each specified indicator to calculate z-scores
    if not isinstance(indicators, list):
        indicators = [indicators]

    for indicator in indicators:
        # Calculate the rolling mean of the indicator over the specified period
        data[f"{indicator} Mean"] = data[f"{indicator}"].rolling(window=zscore_period).mean()

        # Calculate the rolling standard deviation of the indicator over the specified period
        data[f"{indicator} SD"] = data[f"{indicator}"].rolling(window=zscore_period).std()

        # Calculate the z-score using the formula: (value - mean) / standard deviation
        data[f"{indicator} Z-Score"] = (data[f"{indicator}"] - data[f"{indicator} Mean"]) / data[f"{indicator} SD"]

    return data

def calculate_beta(stock_df, index_df, period=252):
    """
    Calculate the beta of a stock.

    Parameters:
    - stock_df (DataFrame): The dataframe containing stock price data.
    - index_df (DataFrame): The dataframe containing index price data.
    - period (int, optional): The number of days to calculate the beta. Default is 252.

    Returns:
    - beta (float): The beta of the stock.
    """

    # Adjust period if needed
    used_period = min(period, min(len(stock_df), len(index_df)))
    if used_period < period:
        print(f"Warning: Requested period ({period}) exceeds available data ({used_period}). Using {used_period} days instead.")

    # Calculate percent changes
    stock_returns = stock_df["Close"].pct_change()
    index_returns = index_df["Close"].pct_change()

    # Drop NaN values
    stock_returns.dropna(inplace=True)
    index_returns.dropna(inplace=True)

    # Take the last "period" values
    stock_returns = stock_returns.iloc[-period:]
    index_returns = index_returns.iloc[-period:]

    # Align the data
    stock_returns, index_returns = stock_returns.align(index_returns, join="inner")

    # Calculate beta using covariance and variance
    covariance = np.cov(stock_returns, index_returns)[0, 1]
    variance = np.var(index_returns)
    beta = covariance / variance

    return beta

def calculate_alpha(stock_df, index_df, period=252, risk_free_rate=0.03):
    """
    Calculate the alpha of a stock.

    Parameters:
    - stock_df (DataFrame): The dataframe containing stock price data.
    - index_df (DataFrame): The dataframe containing index price data.
    - period (int, optional): The number of days to calculate the beta. Default is 252.
    - risk_free_rate (float, optional): The risk-free rate. Default is 0.03.

    Returns:
    - alpha (float): The alpha of the stock, or None if insufficient data.
    """
        
    # Adjust period if needed
    used_period = min(period, min(len(stock_df), len(index_df)))
    if used_period < period:
        print(f"Warning: Requested period ({period}) exceeds available data ({used_period}). Using {used_period} days instead.")
    
    # Calculate the beta of the stock with adjusted period
    beta = calculate_beta(stock_df, index_df, period=used_period)
    
    # Calculate the return of the stock and the index using the adjusted period
    stock_return = stock_df["Close"].iloc[-1] / stock_df["Close"].iloc[-used_period] - 1
    index_return = index_df["Close"].iloc[-1] / index_df["Close"].iloc[-used_period] - 1

    # Calculate the alpha of the stock
    alpha = stock_return - (risk_free_rate + beta * (index_return - risk_free_rate))

    return alpha

def add_indicator(data):
    """
    Add various technical indicators to the given data.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.

    Returns:
    - DataFrame: The DataFrame with added technical indicators.
    """

    # Calculate volatility and other price-based indicators
    get_volatility(data)
    ATR(data)
    MACD(data, 26, 12, 9)
    RSI(data)
    RMI(data)
    CCI(data)
    ADX(data)
    OBOS(data)
    
    # Volume-based indicators
    if "Volume" in data.columns:
        MFI(data)
        MVP_VCP(data)
        FTD_DD(data)
        PVT(data)
        data[f"Volume SMA 50"] = SMA(data, 50, col="Volume")
        data = detect_exhaustion(data)

    # Price-based moving averages
    periods = [5, 10, 20, 50, 100, 200]
    for i in periods:
        data[f"SMA {str(i)}"] = SMA(data, i)
        data[f"EMA {str(i)}"] = EMA(data, i)

    return data

def trend_AD(data, periods=[20, 50, 200], col="Close"):
    """
    Preprocess stock data to calculate market breadth indicators and the Advance-Decline (AD) line.

    Parameters:
    - data (DataFrame): DataFrame containing stock data.
    - periods (list): List of periods for calculating Simple Moving Averages (SMA). Default is [20, 50, 200].
    - col (str): The column name for closing prices. Default is "Close".

    Returns:
    - DataFrame: The DataFrame with added columns for SMA, Above SMA, A (advancing), and D (declining).
    """

    data_copy = data.copy()

    # Calculate the SMAs for the specified periods
    for i in periods:
        data_copy[f"SMA {str(i)}"] = SMA(data_copy, i, col=col)

        # Check if the closing price is above the calculated SMA
        data[f"Above SMA {str(i)}"] = 0
        data.loc[data_copy[col] > data_copy[f"SMA {str(i)}"], f"Above SMA {str(i)}"] = 1
        data.loc[data_copy[col] <= data_copy[f"SMA {str(i)}"], f"Above SMA {str(i)}"] = 0

    # Calculate the daily change in stock prices
    data_copy["Change"] = data_copy[col].diff()

    # Initialise columns for advancing (A) and declining (D) stocks
    data["A"] = 0
    data["D"] = 0

    # Mark advancing stocks (A) where the price increased, and declining stocks (D) where it did not
    data.loc[data_copy["Change"] > 0, "A"] = 1
    data.loc[data_copy["Change"] <= 0, "D"] = 1

    return data

def market_breadth(end_date, index_df, stocks, periods=[20, 50, 200]):
    """
    Calculate market breadth indicators for a given index based on stock performance.

    Parameters:
    - end_date (str): The end date for the stock data.
    - index_df (DataFrame): DataFrame to store the market breadth results.
    - stocks (list): List of stock symbols to analyse.
    - periods (list): List of periods for calculating Simple Moving Averages (SMA). Default is [20, 50, 200].

    Returns:
    - DataFrame: The DataFrame with market breadth indicators and AD line calculations.
    """

    # Initialise the Above SMA columns in the index DataFrame
    for i in periods:
        index_df[f"Above SMA {str(i)}"] = 0

    # Initialise the advancing (A) and declining (D) columns in the index DataFrame
    index_df["A"] = 0
    index_df["D"] = 0

    # Iterate over all stocks to calculate their contributions to market breadth
    for stock in tqdm(stocks):
        # Get the price data for the stock
        df = get_df(stock, end_date)

        # Check if the data exists for the stock
        if df is not None:
            # Preprocess the data to calculate market breadth and AD line
            df = trend_AD(df)

            # Calculate the number of stocks above each SMA
            for i in periods:
                index_df.loc[:, f"Above SMA {str(i)}"] = index_df.loc[:, f"Above SMA {str(i)}"].add(df[f"Above SMA {str(i)}"], fill_value=0)
            
            # Accumulate the advancing (A) and declining (D) values for all stocks
            index_df.loc[:, "A"] = index_df.loc[:, "A"].add(df["A"], fill_value=0)
            index_df.loc[:, "D"] = index_df.loc[:, "D"].add(df["D"], fill_value=0)

    # Calculate the Advance-Decline (AD) line
    index_df["AD Change"] = index_df["A"] - index_df["D"]
    index_df["AD"] = index_df["AD Change"].cumsum()
    
    return index_df

def get_JdK(sectors, index_df, end_date, period_short=12, period_long=26, period_signal=9):
    """
    Calculate the JdK RS-Ratio and Momentum for specified sectors relative to a benchmark index.

    Parameters:
    - sectors (list): List of sector symbols to analyse.
    - index_df (DataFrame): DataFrame containing benchmark index data.
    - end_date (str): The end date for the stock data.
    - period_short (int): Short period for the SMA calculation. Default is 12.
    - period_long (int): Long period for the SMA calculation. Default is 26.
    - period_signal (int): Period for the SMA of the JdK RS-Ratio. Default is 9.

    Returns:
    - DataFrame: The DataFrame updated with JdK RS-Ratio and Momentum for each sector.
    """

    # Iterate over all specified sectors
    for sector in tqdm(sectors):
        # Get the price data of the sector
        df = get_df(sector, end_date)
        df_copy = df.copy()

        # Calculate the relative closing price compared to the benchmark index
        df_copy["Relative Close"] = df["Close"] / index_df["Close"]

        # Calculate the SMAs of the relative closing price
        df_copy[f"Relative Close SMA {period_short}"] = df_copy["Relative Close"].rolling(window=period_short).mean()
        df_copy[f"Relative Close SMA {period_long}"] = df_copy["Relative Close"].rolling(window=period_long).mean()

        # Calculate the JdK RS-Ratio
        df_copy["JdK RS-Ratio"] = 100 * ((df_copy[f"Relative Close SMA {period_short}"] - df_copy[f"Relative Close SMA {period_long}"]) / df_copy[f"Relative Close SMA {period_long}"] + 1)

        # Calculate the SMA of the JdK RS-Ratio over the signal period
        df_copy[f"JdK RS-Ratio SMA {period_signal}"] = df_copy["JdK RS-Ratio"].rolling(window=period_signal).mean()

        # Calculate the JdK RS-Momentum
        df_copy["JdK RS-Momentum"] = 100 * ((df_copy["JdK RS-Ratio"] - df_copy[f"JdK RS-Ratio SMA {period_signal}"]) / df_copy[f"JdK RS-Ratio SMA {period_signal}"] + 1)

        # Insert the calculated JdK RS-Ratio and Momentum into the index DataFrame
        index_df[f"{sector} JdK RS-Ratio"] = df_copy["JdK RS-Ratio"]
        index_df[f"{sector} JdK RS-Momentum"] = df_copy["JdK RS-Momentum"]

        # Forward fill NaN values
        index_df = index_df.ffill()

    return index_df

def check_bgu(df):
    """
    Check for a buyable gap up condition based on closing price and ATR.

    Parameters:
    - df (DataFrame): DataFrame containing stock data.

    Returns:
    - tuple: A tuple containing the calculated gap up price and volume.
    """

    # Retrieve the current closing price
    current_close = df["Close"].iloc[-1]
    
    # Calculate the 40-day ATR
    df = ATR(df, period=40)
    atr = df["ATR"].iloc[-1]

    # Calculate the 50-day SMA of volume
    df["Volume SMA 50"] = SMA(df, 50, col="Volume")
    volume_sma50 = df["Volume SMA 50"].iloc[-1]

    # Calculate the price for the gap up condition
    price_bgu = current_close + 0.75 * atr

    # Calculate the volume for the gap up condition
    volume_bgu = 1.5 * volume_sma50

    return round(price_bgu, 2), round(volume_bgu, 2)

def filter_df_outlier(df, col, zscore, greater=True):
    """
    Filter outliers from the DataFrame based on z-score.

    Parameters:
    - df (DataFrame): DataFrame containing stock data.
    - col (str): The column name to evaluate for outliers.
    - zscore (float): The z-score threshold for identifying outliers.
    - greater (bool): If True, filter for values greater than zscore; otherwise, filter for less.

    Returns:
    - tuple: Two DataFrames, one for inliers and one for outliers.
    """

    # Extract the specified column while dropping any NaN values
    arr = df[col].dropna()

    # Calculate the mean and standard deviation of the column
    mean = np.mean(arr)
    sd = np.std(arr)

    # Filter the DataFrame based on the z-score threshold
    df[f"{col} Z-Score"] = (df[col] - mean) / sd
    if greater:
        df_inlier = df[df[f"{col} Z-Score"] < zscore]
        df_outlier = df[df[f"{col} Z-Score"] >= zscore]
    else:
        df_inlier = df[df[f"{col} Z-Score"] > zscore]
        df_outlier = df[df[f"{col} Z-Score"] <= zscore]

    return df_inlier, df_outlier

def calculate_ndays_return(df, ns):
    """
    Calculate the n-day returns for specified intervals.

    Parameters:
    - df (DataFrame): DataFrame containing stock data.
    - ns (int or list): Number of days for which to calculate returns. Can be a single integer or a list of integers.

    Returns:
    - DataFrame: The DataFrame updated with n-day return columns.
    """

    # Ensure ns is a list to handle multiple intervals
    if isinstance(ns, int):
        ns = [ns]
        
    # Iterate over each specified number of days
    for n in ns:
        df[f"Close {n} Later"] = df["Close"].shift(- n)
        df[f"{n} Days Return (%)"] = ((df[f"Close {n} Later"] / df["Close"]) - 1) * 100

    return df

def compute_volume_profile(df, period=252, interval_num=200, price_interval=0.1):
    """
    Compute the volume profile for a given DataFrame using user-defined lookback period and price interval.

    Parameters:
    - df (DataFrame): DataFrame containing "Open", "High", "Low", "Close", and "Volume" columns.
    - period (int): The lookback period to compute the volume profile. Default is 252.
    - interval_num (int): Number of price bins to uniformly span the price range. Default is 200.
    - price_interval (float): Interval to discretize the price range of each candle. Default is 0.1.

    Returns:
    - volume_profile (DataFrame): DataFrame with the volume profile.
    """
    
    # Filter the DataFrame to the lookback period
    df = df[- period:]
    
    # Define the total price range based on the entire lookback period
    price_min = df["Low"].min()
    price_max = df["High"].max()
    price_bins = np.linspace(price_min, price_max, interval_num)
    
    # Initialise the volume profile DataFrame
    volume_profile = pd.DataFrame(0.0, index=price_bins, columns=["Volume"])
    
    # Vectorize the binning process
    for i in range(len(df)):
        low = df["Low"].iloc[i]
        high = df["High"].iloc[i]
        volume = df["Volume"].iloc[i]
        
        # Round low and high to price_interval precision
        rounded_low = np.floor(low / price_interval) * price_interval
        rounded_high = np.ceil(high / price_interval) * price_interval

        # Calculate bin edges for the candle with fixed increments
        candle_bins = np.arange(rounded_low, rounded_high, price_interval)
        
        # Calculate volume per bin
        bin_volume = volume / (len(candle_bins) - 1) if len(candle_bins) > 1 else 0
        
        # Find the indices where price_bins fall between candle_bins
        indices = np.where((price_bins >= low) & (price_bins < high))[0]
        
        # Update volume profile using vectorized operations
        if len(indices) > 0:
            volume_profile.iloc[indices] += bin_volume

    return volume_profile

def find_market_cycles(df, bear_market_threshold=-20):
    """
    Function to find both bear and bull markets in the S&P 500 data.
    
    Parameters:
    - df (pd.DataFrame): DataFrame containing S&P 500 data with a DateTime index.
    - bear_market_threshold (float, optional): Percentage drop from peak to define a bear market. Default is -20%.
    
    Returns:
    - tuple: Contains (bear_df, bull_df, bear_starts, bear_ends, bull_starts, bull_ends)
        - bear_df (pd.DataFrame): DataFrame containing information about bear markets.
        - bull_df (pd.DataFrame): DataFrame containing information about bull markets.
        - bear_starts (list): List of bear market start dates.
        - bear_ends (list): List of bear market end dates.
        - bull_starts (list): List of bull market start dates.
        - bull_ends (list): List of bull market end dates.
    """

    # Calculate the rolling maximum of the opening price
    df["Rolling Max"] = df["Open"].cummax()

    # Calculate the percentage drop from the peak
    df["Drop From Peak"] = (df["Low"] / df["Rolling Max"] - 1) * 100

    # Identify bear market regions (20% or more drop from peak)
    df["Bear Market"] = df["Drop From Peak"] <= bear_market_threshold

    # Find bear market start and end dates
    bear_starts = []
    bear_ends = []
    in_bear = False
    current_peak = None
    peak_date = None

    for date, row in df.iterrows():
        # Track the peak date when a new high is reached
        if row["Open"] == row["Rolling Max"]:
            peak_date = date
        if not in_bear and row["Drop From Peak"] <= bear_market_threshold:
            # Start of bear market at the peak date
            in_bear = True
            bear_starts.append(peak_date)
            current_peak = row["Rolling Max"]
        elif in_bear and row["Close"] >= current_peak:
            # End of bear market when price surpasses previous peak
            in_bear = False
            bear_ends.append(date)

    # If still in bear market at the end of the data, add the last date
    if in_bear:
        bear_ends.append(df.index[-1])

    # Find bull market periods
    bull_starts = []
    bull_ends = []
    
    # First bull market starts from the beginning of data
    if bear_starts:
        bull_starts.append(df.index[0])
        bull_ends.append(bear_starts[0])
    
    # Bull markets between bear markets
    for i in range(len(bear_ends) - 1):
        bull_starts.append(bear_ends[i])
        bull_ends.append(bear_starts[i + 1])
    
    # Last bull market
    if bear_ends and bear_ends[-1] < df.index[-1]:
        bull_starts.append(bear_ends[-1])
        bull_ends.append(df.index[-1])
    
    # If no bear markets found, entire period is bull market
    if not bear_starts:
        bull_starts.append(df.index[0])
        bull_ends.append(df.index[-1])

    # Create bear market information
    bear_info = []
    for i, (start, end) in enumerate(zip(bear_starts, bear_ends)):
        start_price = df.loc[start, "Open"]
        end_price = df.loc[end, "Close"]
        lowest_price = df.loc[start:end, "Low"].min()
        lowest_date = df.loc[start:end, "Low"].idxmin()
        max_drop = (lowest_price / df.loc[start, "Rolling Max"] - 1) * 100
        duration_days = (end - start).days

        bear_info.append({
            "Bear Market #": i + 1,
            "Start Date": start.strftime('%Y-%m-%d'),
            "End Date": end.strftime('%Y-%m-%d'),
            "Start Price": f"{start_price:.2f}",
            "End Price": f"{end_price:.2f}",
            "Duration (days)": duration_days,
            "Max Drop (%)": f"{max_drop:.2f}%",
            "Lowest Date": lowest_date.strftime('%Y-%m-%d')
        })

    # Create bull market information
    bull_info = []
    for i, (start, end) in enumerate(zip(bull_starts, bull_ends)):
        start_price = df.loc[start, "Open"]
        end_price = df.loc[end, "Close"]
        total_return = (end_price / start_price - 1) * 100
        duration_days = (end - start).days

        bull_info.append({
            "Bull Market #": i + 1,
            "Start Date": start.strftime('%Y-%m-%d'),
            "End Date": end.strftime('%Y-%m-%d'),
            "Start Price": f"{start_price:.2f}",
            "End Price": f"{end_price:.2f}",
            "Duration (days)": duration_days,
            "Total Return (%)": f"{total_return:.2f}%"
        })

    # Create DataFrames
    bear_df = pd.DataFrame(bear_info)
    bear_df = bear_df.set_index("Bear Market #") if bear_info else pd.DataFrame()
    
    bull_df = pd.DataFrame(bull_info)
    bull_df = bull_df.set_index("Bull Market #") if bull_info else pd.DataFrame()

    return bear_df, bull_df, bear_starts, bear_ends, bull_starts, bull_ends