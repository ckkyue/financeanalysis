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

# Create dataframes to store RS ratings and volume ranks
def create_rs_volume_df(stocks, dfs, end_dates, periods, index_returns, index_shortName, result_folder, infix, backtest, print_multiple=True):
    # Convert inputs to lists
    if not isinstance(end_dates, list):
        end_dates = [end_dates]
    if not isinstance(periods, list):
        periods = [periods]
    if not isinstance(index_returns, list):
        index_returns = [index_returns]

    # Initialize three empty lists to store rs_df, volume_df, and rs_volume_df
    rs_dfs = []
    volume_dfs = []
    rs_volume_dfs = []
    
    # Iterate over all combinations of end dates, periods, and index return
    for end_date, period, index_return in zip(end_dates, periods, index_returns):
        return_muls = {}
        volume_smas = {}

        # Iterate over all stocks
        for stock in tqdm(stocks, desc=f"Processing data for {end_date}"):
            try:
                df = dfs.get(stock)
                if df is None:
                    continue
                
                # Filter the data
                df = df[df.index < end_date]

                # Calculate the percent change of the stock
                df["Percent Change"] = df["Close"].pct_change()

                # Calculate the stock return
                stock_return = (df["Percent Change"] + 1).tail(period).cumprod().iloc[-1]

                # Calculate the stock return relative to the market
                return_mul = stock_return / index_return
                return_muls[stock] = return_mul
                if print_multiple:
                    print(f"Stock: {stock} ; Return multiple against {index_shortName}: {round(return_mul, 2)}\n")
                
                # Calculate the moving averages of volume
                df["Volume SMA 5"] = SMA(df, 5, column="Volume")
                df["Volume SMA 20"] = SMA(df, 20, column="Volume")
                volume_smas[stock] = {"Volume SMA 5": df["Volume SMA 5"].iloc[-1], "Volume SMA 20": df["Volume SMA 20"].iloc[-1]}

            except Exception as e:
                print(f"Error processing data for {stock}: {e}\n")
                continue

            # time.sleep(0.05)
            
        # Create a dataframe to store the RS ratings of stocks
        return_muls = dict(sorted(return_muls.items(), key=lambda x: x[1], reverse=True))
        rs_df = pd.DataFrame(return_muls.items(), columns=["Stock", "Value"])
        rs_df["RS"] = rs_df["Value"].rank(pct=True) * 100
        rs_df = rs_df[["Stock", "RS"]]

        # Create a dataframe to store the volume ranks of stocks
        volume_df = pd.DataFrame.from_dict(volume_smas, orient="index", columns=["Volume SMA 5", "Volume SMA 20"])
        volume_df["Stock"] = volume_df.index
        volume_df.reset_index(drop=True, inplace=True)
        volume_df["Volume SMA 5 Rank"] = volume_df["Volume SMA 5"].rank(ascending=False)
        volume_df["Volume SMA 20 Rank"] = volume_df["Volume SMA 20"].rank(ascending=False)

        # Merge the dataframes
        rs_volume_df = pd.merge(rs_df, volume_df, on="Stock")
        rs_volume_df = rs_volume_df.sort_values(by="RS", ascending=False)

        # Check if there are pre-existing data
        current_files = [file for file in os.listdir(result_folder) if file.startswith(f"{infix}rsvolume_")]

        # Get the list of dates
        dates = [file.split("_")[-1].replace(".csv", "") for file in current_files]

        # Remove the old files for dates prior to the end date
        for date in dates:
            if date < end_date:
                os.remove(os.path.join(result_folder, f"{infix}rsvolume_{date}.csv"))
                
        # Define the filename
        filename = os.path.join(result_folder, f"{infix}rsvolume_{end_date}.csv")

        # Save the merged dataframe to a .csv file
        if not backtest:
            rs_volume_df.to_csv(filename, index=False)

        rs_dfs.append(rs_df)
        volume_dfs.append(volume_df)
        rs_volume_dfs.append(rs_volume_df)

    if len(rs_dfs) == 1:
        return rs_dfs[0], volume_dfs[0], rs_volume_dfs[0]
    else:
        return rs_dfs, volume_dfs, rs_volume_dfs

# Combine the long term and short term RS dataframes
def longshortRS(stocks, index_df, index_name, index_dict, NASDAQ_all, current_date, end_dates1, end_dates2, periods1, periods2, result_folder, infix, volume_filter=None):
    # Convert inputs to lists
    if not isinstance(end_dates1, list):
        end_dates1 = [end_dates1]
    if not isinstance(end_dates2, list):
        end_dates2 = [end_dates2]
    if not isinstance(periods1, list):
        periods1 = [periods1]
    if not isinstance(periods2, list):
        periods2 = [periods2]
        
    # Initialize an empty list to store the merged dataframes
    merged_dfs = []

    # Initialize an empty list to store the index returns
    index_returns = []

    # Iterate over all combinations
    for end_date1, end_date2, period1, period2 in zip(end_dates1, end_dates2, periods1, periods2):
        # Filter the data
        index_df1 = index_df[index_df.index < end_date1]
        index_df2 = index_df[index_df.index < end_date2]

        # Calculate the percent change of the index
        index_df1.loc[:, "Percent Change"] = index_df1["Close"].pct_change()
        index_df2.loc[:, "Percent Change"] = index_df2["Close"].pct_change()
        
        # Calculate the total return of the index
        index_return1 = (index_df1["Percent Change"] + 1).tail(period1).cumprod().iloc[-1]
        index_return2 = (index_df2["Percent Change"] + 1).tail(period2).cumprod().iloc[-1]
        index_shortName = index_dict[f"{index_name}"]
        print(f"Return for {index_shortName} between {index_df1.index[-period1].strftime('%Y-%m-%d')} and {end_date1}: {index_return1:.2f}")
        print(f"Return for {index_shortName} between {index_df2.index[-period2].strftime('%Y-%m-%d')} and {end_date2}: {index_return2:.2f}")

        index_returns.extend([index_return1, index_return2])
        
    rs_dfs, volume_dfs, _ = create_rs_volume_df(stocks, current_date, end_dates1 + end_dates2, periods1 + periods2, index_returns, index_shortName, result_folder, infix, True, print_multiple=False)

    # Separate the dataframes into two halves
    length_df = len(rs_dfs) // 2
    rs_dfs1, rs_dfs2 = rs_dfs[:length_df], rs_dfs[length_df:]
    volume_dfs1, volume_dfs2 = volume_dfs[:length_df], volume_dfs[length_df:]

    for rs_df1, rs_df2, volume_df1, volume_df2 in zip(rs_dfs1, rs_dfs2, volume_dfs1, volume_dfs2):
        if volume_filter is not None:
            volume_df1 = volume_df1[(volume_df1["Volume SMA 5 Rank"] <= volume_filter) | (volume_df1["Volume SMA 20 Rank"] <= volume_filter)]
            volume_df2 = volume_df2[(volume_df2["Volume SMA 5 Rank"] <= volume_filter) | (volume_df2["Volume SMA 20 Rank"] <= volume_filter)]

            # Filter rs_df1 and rs_df2 based on the stocks present in volume dataframes
            rs_df1 = rs_df1[rs_df1["Stock"].isin(set(volume_df1["Stock"]))]
            rs_df2 = rs_df2[rs_df2["Stock"].isin(set(volume_df2["Stock"]))]

        # Merge and clean data
        merged_df = pd.merge(rs_df1, rs_df2, on="Stock", suffixes=(" 1", " 2"))
        merged_df = merged_df.rename(columns={"RS 1": "Long-term RS", "RS 2": "Short-term RS"}).dropna()
        merged_dfs.append(merged_df)

    return merged_dfs[0] if len(merged_dfs) == 1 else merged_dfs

# Compare the long and short term RS
def compare_longshortRS(stocks, index_df, index_name, index_dict, NASDAQ_all, current_date, end_dates, period1, period2, result_folder, infix):
    # Initialize two empty lists to store the RS slopes and R^2 values
    rs_slopes = []
    r_squareds = []

    # Define the end dates and periods
    end_dates1 = []
    end_dates2 = []
    for i in range(len(end_dates) - 1):
        end_date = end_dates[i]
        end_dates1.append(end_date)
        end_dates2.append((dt.datetime.strptime(end_date, "%Y-%m-%d") + relativedelta(days=20)).strftime("%Y-%m-%d"))
    periods1 = [period1] * len(end_dates1)
    periods2 = [period2] * len(end_dates2)

    # Get the merged dataframe
    merged_dfs = longshortRS(stocks, index_df, index_name, index_dict, NASDAQ_all, current_date, end_dates1, end_dates2, periods1, periods2, result_folder, infix)
    
    # Iterate over merged dataframe
    for merged_df in merged_dfs:
        # Calculate the slope and R^2
        rs_slope, _, r_value, _, _ = linregress(merged_df["Long-term RS"], merged_df["Short-term RS"])
        r_squared = r_value**2
        rs_slopes.append(rs_slope)
        r_squareds.append(r_squared)
        
    return rs_slopes, r_squareds, end_dates2

# Calculate the simple moving average (SMA)
def SMA(data, period, column="Close"):
    return data[column].rolling(window=period).mean()

# Calculate the exponential moving average (EMA)
def EMA(data, period, column="Close"):
    return data[column].ewm(span=period, adjust=False).mean()

# Get the volatility
def get_volatility(data, periods=[20, 60], column="Close"):
    data_copy = data.copy()

    # Calculate the percent change of the stock
    data_copy.loc[:, "Percent Change"] = data_copy[column].pct_change()

    # Calculate the volatility
    for period in periods:
        data[f"Volatility {period}"] = data_copy["Percent Change"].rolling(window=period).std()

    return data

# Calculate the average true range (ATR)
def ATR(data, period=14, column="Close"):
    # Calculate the true range (TR)
    TR = pd.concat([
        abs(data["High"] - data["Low"]),
        abs(data["High"] - data[column].shift()),
        abs(data["Low"] - data[column].shift())
        ], axis=1).max(axis=1)
    
    # Calculate the ATR by EMA of TR
    ATR = TR.ewm(span=period, adjust=False).mean()
    data["TR"] = TR
    data["ATR"] = ATR

    return data

# Calculate the moving average convergence/divergence (MACD)
def MACD(data, period_long, period_short, period_signal, column="Close"):
    # Calculate the short EMA
    EMA_short = EMA(data, period_short, column=column)

    # Calculate the long EMA
    EMA_long = EMA(data, period_long, column=column)

    # Calculate the MACD
    data["MACD"] = EMA_short - EMA_long

    # Calculate the signal line
    data["MACD Signal Line"] = EMA(data, period_signal, column="MACD")

    # Calculate the MACD bar
    data["MACD Bar"] = data["MACD"] - data["MACD Signal Line"]
    
    return data

# Calculate the Relative Strength Index (RSI)
def RSI(data, period=14, column="Close"):
    # Calculate the change of the stock
    data["Change"] = data[column].diff()

    # Calculate the gains and losses
    gain = data["Change"].copy()
    loss = data["Change"].copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0

    # Calculate the relative strength (RS)
    RS = gain.rolling(window=period).mean() / abs(loss.rolling(window=period).mean())

    # Calculate the RSI
    RSI = 100 - (100 / (1 + RS))
    data["RSI"] = RSI

    return data

# Calculate the Relative Momentum Index (RMI)
def RMI(data, period=20, momentum=3, column="Close"):
    data_copy = data.copy()

    # Calculate the change of the stock
    data_copy["Change"] = data_copy[column].diff(momentum)[momentum:]

    # Calculate the gains and losses
    gain = data_copy["Change"].copy()
    loss = data_copy["Change"].copy()
    gain[gain < 0] = 0
    loss[loss > 0] = 0

    # Calculate the relative momentum (RM)
    RM = gain.rolling(window=period).mean() / abs(loss.rolling(window=period).mean())

    # Calculate the RMI
    RMI = 100 - (100 / (1 + RM))
    data["RMI"] = RMI

    return data

# Calculate the Money Flow Index (MFI)
def MFI(data, period=14):
    data_copy = data.copy()

    # Calculate HLC3, Raw MF, and the change of HLC3
    data_copy["HLC3"] = (data_copy["High"] + data_copy["Low"] + data_copy["Close"]) / 3
    data_copy["Raw MF"] = data_copy["HLC3"] * data_copy["Volume"]
    data_copy["HLC3 Change"] = data_copy["HLC3"].diff()

    # Calculate the +MF and -MF
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

# Calculate the Commodity Channel Index (CCI)
def CCI(data, period=20):
    data_copy = data.copy()
    
    # Calculate the average of high, low and closing prices (HLC3)
    data_copy["HLC3"] = (data_copy["High"] + data_copy["Low"] + data_copy["Close"]) / 3

    # Calculate the moving average of HLC3
    data_copy["MA"] = data_copy["HLC3"].rolling(window=period).mean()

    # Calculate the CCI
    data["CCI"] = (data_copy["HLC3"] - data_copy["MA"]) / (0.015 * data_copy["HLC3"].rolling(window=period).std())

    return data

# Calculate the Average Directional Index (ADX)
def ADX(data, period=14):
    data_copy = data.copy()

    # Calculate the ATR
    data_copy = ATR(data_copy, period=period)

    # Calculate the +DM and -DM
    data_copy["+DM"] = np.where((data_copy["High"] - data_copy["High"].shift()) > np.maximum((data_copy["Low"].shift() - data_copy["Low"]), 0), 
                                data_copy["High"] - data_copy["High"].shift(), 0)
    
    data_copy["-DM"] = np.where((data_copy["Low"].shift() - data_copy["Low"]) > np.maximum((data_copy["High"] - data_copy["High"].shift()), 0), 
                                data_copy["Low"].shift() - data_copy["Low"], 0)

    # Calculate the +DI and -DI by EMA of +DM and -DM, divided by ATR
    data_copy["+DI"] = EMA(data_copy, period, column="+DM") / data_copy["ATR"]
    data_copy["-DI"] = EMA(data_copy, period, column="-DM") / data_copy["ATR"]

    # Calculate the DX
    data_copy["DX"] = (np.abs(data_copy["+DI"] - data_copy["-DI"]) / (data_copy["+DI"] + data_copy["-DI"])) * 100

    # Calculate the ADX
    data["ADX"] = EMA(data_copy, period, column="DX")

    return data

# Calcualte the OB/OS indicator (OBOS)
def OBOS(data, period=14, column="Close"):
    data_copy = data.copy()

    # Calculate the highest and lowest closing price over the past period
    data_copy["HC"] = data_copy[column].rolling(window=period).max()
    data_copy["LC"] = data_copy[column].rolling(window=period).min()

    # Calculate the OB/OS indicator
    data["OBOS"] = (data_copy["Close"] - data_copy["LC"]) / (data_copy["HC"] - data_copy["LC"]) * 100

    return data

# Calculate the MVP/VCP indicator
def MVP_VCP(data, period_MVP=15, period_VCP=10, contraction=0.05, period=60, column="Close"):
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
    data_copy["HC"] = data_copy[column].rolling(window=period_VCP).max()
    data_copy["MC"] = data_copy[column].rolling(window=period_VCP).median()
    data_copy["LC"] = data_copy[column].rolling(window=period_VCP).min()

    # Check if the highest and lowest closing prices differ by less than contraction
    data["VCP"] = (1 - data_copy["LC"] / data_copy["HC"]) <= contraction

    # Check if pivot breakout occurs
    data["Pivot breakout"] = data_copy[column] > 1 / 3 * (data_copy["HC"] + data_copy["MC"] + data_copy["LC"])

    # Check if the volume is shrinking
    data["Volume shrinking"] = data_copy["Volume"].rolling(window=period_VCP).apply(slope_reg) < 0
    
    return data

# Check follow-through day (FTD) and distribution day (DD)
def FTD_DD(data, period=50, threshold=0.015, column="Close"):
    # Check FTD
    data["FTD"] = (data[column] > (1 + threshold) * data[column].shift(1)) \
        & (data["Volume"] > data["Volume"].shift(1)) \
        & (data["Volume"] > data["Volume"].rolling(window=period).mean())
    
    # Check DD
    data["DD"] = (data[column] < (1 - threshold) * data[column].shift(1)) \
    & (data["Volume"] > data["Volume"].shift(1)) \
    & (data["Volume"] > data["Volume"].rolling(window=period).mean())

    # Check if there are at least four FTDs or DDs recently
    data["Multiple FTDs"] = data["FTD"].rolling(period).sum() >= 4
    data["Multiple DDs"] = data["DD"].rolling(period).sum() >= 4

    return data

# Locate the local extrema
def get_local_extrema(data, min_column="Low", max_column="High", period=5):
    # Find local minima and maxima
    local_min = data[min_column].rolling(period, center=True, min_periods=2).min() == data[min_column]
    local_max = data[max_column].rolling(period, center=True, min_periods=2).max() == data[max_column]

    # Create new columns for local min and max locations
    data["Local Min"] = local_min
    data["Local Max"] = local_max

    return data

# Calculate the most recent retracement
def calculate_retracement(data, min_column="Low", max_column="High", buffer=15):
    # Find indices of local mins and maxes
    min_indices = data[data["Local Min"]].index
    max_indices = data[data["Local Max"]].index

    # Handle empty cases
    if min_indices.empty or max_indices.empty:
        return None

    min_index1 = min_indices[-1]

    # Initialize an empty list to store the most recent max
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
    
    local_min1 = data.loc[min_index1, min_column]
    
    # Retrieve local max values
    local_max_values = [data.loc[index, max_column] for index in max_index_list]
    local_max = local_max_values[0]

    # Check conditions for local_max2 and local_max3
    for i in range(1, len(local_max_values)):
        if (max_index_list[0] - max_index_list[i]).days <= buffer:
            local_max = max(local_max, local_max_values[i])

    retracement = 1 - local_min1 / local_max

    return np.array([local_min1, local_max, retracement])

# Calculate the z-score
def calculate_zscore(data, indicators, zscore_period):
    # Convert inputs to lists
    if not isinstance(indicators, list):
        indicators = [indicators]

    for indicator in indicators:
        # Calculat the mean of indicator
        data[f"{indicator} Mean"] = data[f"{indicator}"].rolling(window=zscore_period).mean()

        # Calculate the SD of indicator
        data[f"{indicator} SD"] = data[f"{indicator}"].rolling(window=zscore_period).std()

        # Calculate the z-score of indicator
        data[f"{indicator} Z-Score"] = (data[f"{indicator}"] - data[f"{indicator} Mean"]) / data[f"{indicator} SD"]

    return data

# Add technical indicators to the data
def add_indicator(data):
    get_volatility(data)
    ATR(data)
    MACD(data, 26, 12, 9)
    RSI(data)
    RMI(data)
    MFI(data)
    CCI(data)
    ADX(data)
    OBOS(data)
    MVP_VCP(data)
    FTD_DD(data)

    # Calculate the moving averages of closing prices and volumes
    periods = [5, 10, 20, 50, 100, 200]
    for i in periods:
        data[f"SMA {str(i)}"] = SMA(data, i)
        data[f"EMA {str(i)}"] = EMA(data, i)
        data[f"Volume SMA {str(i)}"] = SMA(data, i, column="Volume")

    return data

# Preprocess the data to get the market breadth and AD line
def trend_AD(data, periods=[20, 50, 200], column="Close"):
    data_copy = data.copy()

    # Calculate the SMAs
    for i in periods:
        data_copy[f"SMA {str(i)}"] = SMA(data_copy, i, column=column)

        # Check if the closing price is above SMAs
        data[f"Above SMA {str(i)}"] = 0
        data.loc[data_copy[column] > data_copy[f"SMA {str(i)}"], f"Above SMA {str(i)}"] = 1
        data.loc[data_copy[column] <= data_copy[f"SMA {str(i)}"], f"Above SMA {str(i)}"] = 0

    # Calculate the change of the stock
    data_copy["Change"] = data_copy[column].diff()

    # Initialize the advancing (A) and declining (D) columns
    data["A"] = 0
    data["D"] = 0

    # Check if the price advances (A) or declines (D)
    data.loc[data_copy["Change"] > 0, "A"] = 1
    data.loc[data_copy["Change"] <= 0, "D"] = 1

    return data

# Calculate the market breadth indicators
def market_breadth(end_date, index_df, stocks, periods=[20, 50, 200]):
    # Initialize the Above SMA columns
    for i in periods:
        index_df[f"Above SMA {str(i)}"] = 0

    # Initialize the advancing (A) and declining (D) columns
    index_df["A"] = 0
    index_df["D"] = 0

    # Iterate over all stocks
    for stock in tqdm(stocks):
        # Get the price data of the stock
        df = get_df(stock, end_date)

        # Check if the data exist
        if df is not None:
            # Preprocess the data to get the market breadth and AD line
            df = trend_AD(df)

            # Calculate the number of stocks above SMAs
            for i in periods:
                index_df.loc[:, f"Above SMA {str(i)}"] = index_df.loc[:, f"Above SMA {str(i)}"].add(df[f"Above SMA {str(i)}"], fill_value=0)
            
            # Accumulate the advancing (A) and declining (D) values for all stocks
            index_df.loc[:, "A"] = index_df.loc[:, "A"].add(df["A"], fill_value=0)
            index_df.loc[:, "D"] = index_df.loc[:, "D"].add(df["D"], fill_value=0)

    # Calculate the AD line
    index_df["AD Change"] = index_df["A"] - index_df["D"]
    index_df["AD"] = index_df["AD Change"].cumsum()
    
    return index_df

# Calculate the JdK RS-Ratio and Momentum
def get_JdK(sectors, index_df, end_date, period_short=12, period_long=26, period_signal=9):
    # Iterate over all sectors
    for sector in tqdm(sectors):
        # Get the price data of the sector
        df = get_df(sector, end_date)
        df_copy = df.copy()

        # Calculate the closing price relative to benchmark
        df_copy["Relative Close"] = df["Close"] / index_df["Close"]

        # Calculate the SMAs of relative closing price
        df_copy[f"Relative Close SMA {period_short}"] = df_copy["Relative Close"].rolling(window=period_short).mean()
        df_copy[f"Relative Close SMA {period_long}"] = df_copy["Relative Close"].rolling(window=period_long).mean()

        # Calculate the JdK RS-Ratio
        df_copy["JdK RS-Ratio"] = 100 * ((df_copy[f"Relative Close SMA {period_short}"] - df_copy[f"Relative Close SMA {period_long}"]) / df_copy[f"Relative Close SMA {period_long}"] + 1)

        # Calculate the SMA of JdK RS-Ratio
        df_copy[f"JdK RS-Ratio SMA {period_signal}"] = df_copy["JdK RS-Ratio"].rolling(window=period_signal).mean()

        # Calculate the JdK RS-Momentum
        df_copy["JdK RS-Momentum"] = 100 * ((df_copy["JdK RS-Ratio"] - df_copy[f"JdK RS-Ratio SMA {period_signal}"]) / df_copy[f"JdK RS-Ratio SMA {period_signal}"] + 1)

        # Insert the results into index_df
        index_df[f"{sector} JdK RS-Ratio"] = df_copy["JdK RS-Ratio"]
        index_df[f"{sector} JdK RS-Momentum"] = df_copy["JdK RS-Momentum"]

        # Fill NaN values with the previous value
        index_df = index_df.ffill()

    return index_df

# Check buyable gap up
def check_bgu(df):
    # Get the current closing price
    current_close = df["Close"].iloc[-1]
    
    # Calculate the 40 days ATR
    df = ATR(df, period=40)
    atr = df["ATR"].iloc[-1]

    # Calculate the 50 days volume
    df["Volume SMA 50"] = SMA(df, 50, column="Volume")
    volume_sma50 = df["Volume SMA 50"].iloc[-1]

    # Calculate the gap up price
    price_bgu = current_close + 0.75 * atr

    # Calculate the gap up volume
    volume_bgu = 1.5 * volume_sma50

    return round(price_bgu, 2), round(volume_bgu, 2)

# Filter out the outlier of the dataframe
def filter_df_outlier(df, column, zscore, greater=True):
    # Extract the column
    arr = df[column].dropna()

    # Calculate the mean, SD
    mean = np.mean(arr)
    sd = np.std(arr)

    # Filter the dataframe
    df[f"{column} Z-Score"] = (df[column] - mean) / sd
    if greater:
        df_inlier = df[df[f"{column} Z-Score"] < zscore]
        df_outlier = df[df[f"{column} Z-Score"] >= zscore]
    else:
        df_inlier = df[df[f"{column} Z-Score"] > zscore]
        df_outlier = df[df[f"{column} Z-Score"] <= zscore]

    return df_inlier, df_outlier

# Calculate the n days return
def calculate_ndays_return(df, ns):
    # Ensure ns is a list
    if isinstance(ns, int):
        ns = [ns]
        
    # Iterate over all ns
    for n in ns:
        df[f"Close {n} Later"] = df["Close"].shift(- n)
        df[f"{n} Days Return (%)"] = ((df[f"Close {n} Later"] / df["Close"]) - 1) * 100

    return df