# Imports
import ast
import datetime as dt
from dateutil.relativedelta import relativedelta
from functools import partial
from helper_functions import modify_current_date, generate_end_dates, get_df, get_infix, randomise_array
import itertools
import matplotlib.pyplot as plt
import multiprocessing
import numpy as np
import os
import pandas as pd
pd.options.mode.chained_assignment = None
import pickle
from plot import *
from scipy.stats import kurtosis, skew
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from stock_screener import create_stock_dict
from technicals import *
from tqdm import tqdm

def get_momentum_labels(momentum_params):
    """
    Construct labels for the momentum strategy based on provided parameters.

    Parameters:
    - momentum_params (dict): Parameters for the momentum strategy.

    Returns:
    - tuple: A tuple containing the labels for SMA, capitalization, and stop loss.
    """

    # Extract parameters from the momentum strategy
    sma_crossover = momentum_params["sma_crossover"]
    period_short = momentum_params["period_short"]
    period_long = momentum_params["period_long"]
    cap_threshold = momentum_params["cap_threshold"]
    stoploss_threshold = momentum_params["stoploss_threshold"]
    stopgain_threshold = momentum_params["stopgain_threshold"]

    # Construct the labels
    sma_label = f"sma{period_short}x{period_long}" if sma_crossover else ""
    cap_label = f"cap{cap_threshold}" if cap_threshold else ""
    sl_label = f"sl{int(stoploss_threshold * 100)}" if stoploss_threshold else ""
    sg_label = f"sg{int(stopgain_threshold * 100)}" if stopgain_threshold else ""

    return sma_label, cap_label, sl_label, sg_label

def momentum_equity_curve(end_dates, current_date, index_name, index_dict, all_stocks, factors, momentum_params, reanalyse=False, save=True):
    """
    Calculates the equity curve of a momentum strategy.

    Parameters:
    - end_dates (list): List of end dates for backtesting.
    - current_date (str): The current date.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - factors (list): Factor combination of the strategy.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - reanalyse (bool): If True, reanalyse and overwrite existing data. Default to False.
    - save (bool, optional): If True, save the index DataFrame as a file. Default to True.

    Returns:
    - index_df (DataFrame): Contains the equity curve.
    """

    # Extract parameters from the momentum strategy
    years, interval, top = momentum_params["years"], momentum_params["interval"], momentum_params["top"]
    sma_crossover, period_short, period_long = momentum_params["sma_crossover"], momentum_params["period_short"], momentum_params["period_long"]
    stoploss_threshold, stopgain_threshold, fee_rate, slippage, leverage = momentum_params["stoploss_threshold"], momentum_params["stopgain_threshold"], momentum_params["fee_rate"], momentum_params["slippage"], momentum_params["leverage"]

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    # Define the filename for saving the index DataFrame
    eqcurve_folder = os.path.join(result_folder, "Equity curve")
    filename = os.path.join(eqcurve_folder, f"{infix}eqcurve{factors}years{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.csv")

    # Save the index DataFrame
    if not os.path.isfile(filename) or reanalyse:
        # Define the folder containing stock dictionaries
        stock_dict_folder = os.path.join(result_folder, "Stock dict")

        # Define the filename of the stock dictionary
        stock_dict_filename = os.path.join(stock_dict_folder, f"{infix}stock_dict{factors}{cap_label}.txt")
        
        # Attempt to load the stock dictionary from file
        try:
            if os.path.isfile(stock_dict_filename):
                with open(stock_dict_filename, "r") as file:
                    stock_dict = ast.literal_eval(file.read())
            else:
                print("Error: stock_dict file not found.")
                return None
        except Exception as e:
            print(f"Error reading stock_dict file: {e}")
            return None

        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Calculate moving averages if required
        if sma_crossover:
            for i in [period_short, period_long]:
                index_df[f"SMA {i}"] = SMA(index_df, i)
                index_df[f"EMA {i}"] = EMA(index_df, i)

        # Filter index data to the backtesting period
        index_df = index_df[end_dates[0] : end_dates[-1]]

        # Calculate percent change and cumulative return for the index
        index_df["Percent Change"] = index_df["Close"].pct_change().fillna(0)
        index_df["Cumulative Return"] = (index_df["Percent Change"] + 1).cumprod()

        # Extract the list of stocks for each interval
        stocks_dates = stock_dict.keys()
        stocks_list = [stock_dict[max(date for date in stocks_dates if date <= end_date)] for end_date in end_dates[:-1]]
        
        # Initialise dictionaries to track stop loss and stop gain statuses for each stock during backtesting
        stoploss_prev, trigger_3r_prev, trigger_2r_prev = {}, {}, {}

        # Pre-compute constants
        fee_factor = 1 + fee_rate
        slippage_factor = 1 + slippage
        buy_factor = fee_factor * slippage_factor
        sell_factor = (1 - fee_rate) * (1 - slippage)

        # Iterate over all intervals
        for i in range(len(end_dates) - 1):
            start_date, end_date = end_dates[i], end_dates[i + 1]
            stocks_prev = stocks_list[i - 1] if i > 0 else None
            stocks = stocks_list[i]
            stocks_next = stocks_list[i + 1] if i < len(end_dates) - 2 else None

            # Determine if short SMA is above long SMA or if SMA crossover is disabled
            if sma_crossover:
                sma_cond = index_df[f"SMA {period_short}"].shift(1).loc[start_date] > index_df[f"SMA {period_long}"].shift(1).loc[start_date]
                factor = 1 if sma_cond else 0
            else:
                factor = 1

            if stocks is None:
                continue

            # Iterate over selected stocks
            for j, stock in enumerate(stocks[:top]):
                # Get the price data of the stock
                df = get_df(stock, current_date)
                
                # Check if the DataFrame is empty
                if df is None or df.empty:
                    continue
                    
                try:
                    # Filter price data of the stock to the backtesting period
                    df = df[end_dates[0] : end_dates[-1]]

                    # Calculate the percentage change of the stock
                    df["Percent Change"] = df["Close"].pct_change()
                    
                    # Check if we need to buy the stock
                    is_new_position = (stocks_prev is None or stock not in stocks_prev or 
                                     stoploss_prev.get(f"{stock} {i - 1}", False) or 
                                     trigger_3r_prev.get(f"{stock} {i - 1}", False))
                    
                    if is_new_position:
                        # Buy the stock at the start date
                        open_price = df.loc[start_date, "Open"]
                        close_price = df.loc[start_date, "Close"]
                        
                        if trigger_2r_prev.get(f"{stock} {i - 1}", False):
                            df.loc[start_date, "Percent Change"] = 0.5 * df.loc[start_date, "Percent Change"] + 0.5 * (close_price - buy_factor * open_price) / (buy_factor * open_price)
                        else:
                            df.loc[start_date, "Percent Change"] = (close_price - buy_factor * open_price) / (buy_factor * open_price)

                    # Filter the price data of the stock to the interval
                    df = df[start_date : end_date].fillna({"Percent Change": 0})

                    # Record the price of the stock at the start date
                    price_start = df["Close"].iloc[0]

                    # Calculate the stoploss, 1R, 2R, and 3R prices
                    if stoploss_threshold:
                        price_sl = price_start * (1 - stoploss_threshold)
                        price_sl_tight = price_start * (1 - 0.5 * stoploss_threshold)
                        price_1r = price_start * (1 + stoploss_threshold)
                    if stopgain_threshold:
                        price_2r = price_start * (1 + stopgain_threshold)
                        price_3r = price_start * (1 + 1.5 * stopgain_threshold)

                    # Calculate the cumulative return of the stock
                    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

                    # Initialise variables for stop loss and stop gain handling
                    sell_date = None
                    stoploss_active = False
                    trigger_flags = {"1r": False, "2r": False, "3r": False}

                    # Check if stop loss and stop gain threshold is defined
                    if stoploss_threshold:
                        df["Stop Loss Triggered"] = df["Close"].shift(1) <= price_sl
                        df["1R Triggered"] = df["Close"].shift(1) >= price_1r
                    if stopgain_threshold:
                        df["2R Triggered"] = df["Close"].shift(1) >= price_2r
                        df["3R Triggered"] = df["Close"].shift(1) >= price_3r

                    # Process each date in the interval
                    for idx in df.index:
                        if stoploss_active or trigger_flags["3r"]:
                            # After selling the stock, set the percent change to 0
                            df.loc[idx, "Percent Change"] = 0
                        elif trigger_flags["2r"]:
                            # Apply half of the percent change if 2R is triggered
                            df.loc[idx, "Percent Change"] *= 0.5
                        elif stoploss_threshold and df.loc[idx, "Stop Loss Triggered"]:
                            # Apply stop loss and record the sell date
                            stoploss_active = True
                            sell_date = idx
                            prev_close = df["Close"].shift(1).loc[idx]
                            open_price = df.loc[idx, "Open"]
                            change = (sell_factor * open_price - prev_close) / prev_close
                            
                            if trigger_flags["2r"]:
                                df.loc[idx, "Percent Change"] = 0.5 * change
                            else:
                                df.loc[idx, "Percent Change"] = change
                        elif stoploss_threshold and df.loc[idx, "1R Triggered"] and not trigger_flags["1r"]:
                            # Tighten the stop loss if 1R is triggered
                            trigger_flags["1r"] = True
                            price_sl = price_sl_tight
                            df["Stop Loss Triggered"] = df["Close"].shift(1) <= price_sl
                        elif stopgain_threshold and df.loc[idx, "2R Triggered"]:
                            # Sell half of the position if 2R is triggered
                            trigger_flags["2r"] = True
                            price_sl = price_start
                            df["Stop Loss Triggered"] = df["Close"].shift(1) <= price_sl
                            prev_close = df["Close"].shift(1).loc[idx]
                            open_price = df.loc[idx, "Open"]
                            change = (sell_factor * open_price - prev_close) / prev_close
                            df.loc[idx, "Percent Change"] = 0.5 * df.loc[idx, "Percent Change"] + 0.5 * change
                            trigger_2r_prev[f"{stock} {i}"] = True
                        elif stopgain_threshold and df.loc[idx, "3R Triggered"]:
                            # Sell all of the position if 3R is triggered
                            trigger_flags["3r"] = True
                            sell_date = idx
                            prev_close = df["Close"].shift(1).loc[idx]
                            open_price = df.loc[idx, "Open"]
                            change = (sell_factor * open_price - prev_close) / prev_close
                            df.loc[idx, "Percent Change"] = 0.5 * change
                    
                    # If no stop loss or stop gain triggered, handle end of interval
                    if sell_date is None:
                        sell_date = end_date
                        if stocks_next is None or stock not in stocks_next:
                            # Sell the stock at the sell date
                            prev_close = df["Close"].shift(1).loc[sell_date]
                            open_price = df.loc[sell_date, "Open"]
                            change = (sell_factor * open_price - prev_close) / prev_close
                            
                            if trigger_flags["2r"]:
                                df.loc[sell_date, "Percent Change"] = 0.5 * change
                            else:
                                df.loc[sell_date, "Percent Change"] = change
                    
                    # Record the stop loss or stop gain status of the stock
                    if sell_date != end_date:
                        if stoploss_active:
                            stoploss_prev[f"{stock} {i}"] = True
                        elif trigger_flags["3r"]:
                            trigger_3r_prev[f"{stock} {i}"] = True

                    # Calculate the cumulative return of the stock again
                    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

                    # Store results in the index DataFrame
                    index_df.loc[start_date : end_date, f"Stock {j + 1}"] = stock
                    index_df.loc[start_date : sell_date, f"Buy Stock {j + 1} Percent Change"] = df["Percent Change"]
                    index_df.loc[sell_date, f"Buy Stock {j + 1} Percent Change"] = 0
                    index_df.loc[sell_date, f"Sell Stock {j + 1} Percent Change"] = df.loc[sell_date, "Percent Change"]
                    index_df.loc[start_date : end_date, f"Stock {j + 1} Cumulative Return"] = df["Cumulative Return"]

                except Exception as e:
                    print(f"Error calculating returns for {stock}: {e}")
                    continue

            # Adjust percent change columns by the number of stocks
            for j in range(min(top, len(stocks))):
                col_buy = f"Buy Stock {j + 1} Percent Change"
                col_sell = f"Sell Stock {j + 1} Percent Change"
                adjustment_factor = factor / top
                
                for col in [col_buy, col_sell]:
                    if col in index_df.columns:
                        index_df.loc[start_date : end_date, col] *= adjustment_factor
                
        # Calculate overall stock percent change and cumulative return
        stock_percent_changes = []
        for i in range(top):
            buy_col = f"Buy Stock {i + 1} Percent Change"
            sell_col = f"Sell Stock {i + 1} Percent Change"
            if buy_col in index_df.columns and sell_col in index_df.columns:
                stock_percent_changes.append(index_df[buy_col].fillna(0) + index_df[sell_col].fillna(0))
        
        if stock_percent_changes:
            index_df["Stock Percent Change"] = sum(stock_percent_changes) * leverage
        else:
            index_df["Stock Percent Change"] = 0
            
        index_df["Cumulative Stock Return"] = (index_df["Stock Percent Change"] + 1).cumprod()

        # Save the index DataFrame to a CSV file
        if save:
            index_df.to_csv(filename)
            print(f"Equity curve {filename} saved.")
    else:
        print(f"Equity curve {filename} saved before.")
        index_df = pd.read_csv(filename, parse_dates=["Date"], index_col="Date")

        # Modify the end dates if the backtesting period is less than 7 years            
        if years < 7:
            start_date = generate_end_dates(end_date=end_dates[-1], years=years, interval=interval)[0]
            end_dates = [date for date in end_dates if date >= start_date]
            index_df = index_df.loc[end_dates[0] : end_dates[-1]]

    return index_df

def partial_momentum_equity_curve(args):
    """
    Same as momentum_equity_curve, but with parameters other than factors fixed for parallel processing.

    Parameters:
    - args (tuple): A tuple containing the following elements:
        - end_dates (list): List of end dates for backtesting.
        - current_date (str): The current date.
        - index_name (str): Name of the index being analyzed.
        - index_dict (dict): Dictionary mapping index symbols to their respective names.
        - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
        - factors (list): Factors to consider in the strategy.
        - momentum_params (dict): Parameters for backtesting the momentum strategy.
        - reanalyse (bool): If True, reanalyse and overwrite existing data. Default to False.
        

    Returns:
    - tuple: A tuple containing:
        - factors (tuple): Factor combination of the strategy.
        - index_df (DataFrame): DataFrame with columns ["Close", "Stock Percent Change", "Cumulative Stock Return"].
    """

    # Unpack the arguments from the tuple
    end_dates, current_date, index_name, index_dict, all_stocks, factors, momentum_params, reanalyse = args

    # Calculate the equity curve using the main momentum function
    index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, all_stocks, factors, momentum_params, reanalyse=reanalyse)

    # Return the factors and relevant columns from the index DataFrame
    return tuple(factors), index_df.loc[:, ["Close", "Stock Percent Change", "Cumulative Stock Return"]]

def create_momentum_dict(end_dates, current_date, index_name, index_dict, all_stocks, factors_group, momentum_params, recreate_dict=False, reanalyse=False, speedup=True):
    """
    Create a dictionary to store the returns of all factor combinations for the momentum strategy.

    Parameters:
    - end_dates (list): List of end dates for backtesting.
    - current_date (str): The current date.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - recreate_dict (bool): If True, recreate the dictionary even if it already exists. Default to False.
    - reanalyse (bool): If True, reanalyse and overwrite existing data. Default to False.
    - speedup (bool, optional): If True, use multiprocessing to speed up the process. Default to True.

    Returns:
    - None: This function saves a dictionary of equity curves to a file.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    # Define the filename for saving the momentum dictionary
    momentum_dict_folder = os.path.join(result_folder, "Momentum dict")
    filename = os.path.join(momentum_dict_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.pkl")

    # Check if the file exists and whether to recreate it
    if not os.path.isfile(filename) or recreate_dict:
        if speedup:
            # Prepare arguments for processing each factor combination in parallel
            args_list = [(end_dates, current_date, index_name, index_dict, all_stocks, factors, momentum_params, reanalyse) for factors in factors_group]

            # Create a pool of worker processes to fetch the equity curves
            with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
                results = list(tqdm(pool.imap(partial_momentum_equity_curve, args_list), total=len(args_list)))

            # Create a dictionary to map each factor combination to its equity curve
            momentum_dict = dict(results)

        else:
            # Initialise an empty dictionary to store the equity curves for each combination of factors
            momentum_dict = {}

            # Iterate over all factor combinations
            for factors in tqdm(factors_group):
                # Get the equity curve for the current combination of factors
                factor_index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, all_stocks, factors, momentum_params, reanalyse=reanalyse)

                # Convert the list of factors to a tuple for the dictionary key
                factors_tuple = tuple(factors)

                # Store the equity curve in the dictionary
                momentum_dict[factors_tuple] = factor_index_df.loc[:, ["Close", "Stock Percent Change", "Cumulative Stock Return"]]

        # Save the momentum dictionary to a file
        with open(filename, "wb") as file:
            pickle.dump(momentum_dict, file)
        print("Dictionary of the momentum strategy saved.")

    else:
        print("Dictionary of the momentum strategy saved before.")

def plot_momentum_equity_curve(index_df, index_name, index_dict, all_stocks, factors, factors_group, momentum_params, plot_group=False, save=False):
    """
    Plot the equity curve of stocks for the momentum strategy.

    Parameters:
    - index_df (DataFrame): Contains the equity curve.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - factors (list): Factor combination of the strategy.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for backtesting the momentum strategy.
    - plot_group (bool, optional): If True, plot equity curves for all factor combinations. Default to False.
    - save (bool, optional): If True, save the plot as a file. Default to False.

    Returns:
    - None: This function generates and displays a plot of the equity curve.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)

    # Define the result folder
    result_folder = "Backtest"

    # Calculate percent change and cumulative return for the index
    index_df["Percent Change"] = index_df["Close"].pct_change()
    index_df.fillna({"Percent Change": 0}, inplace=True)
    index_df["Cumulative Return"] = (index_df["Percent Change"] + 1).cumprod()

    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    if not plot_group:
        # Create a figure for the single plot
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return and cumulative stock return
        plt.plot(index_df["Cumulative Return"], label=index_dict[index_name])
        scaling_factor = 1 / index_df["Cumulative Stock Return"].iloc[0] * index_df["Cumulative Return"].iloc[0]
        plt.plot(index_df["Cumulative Stock Return"] * scaling_factor, label=f"Stocks {factors}")

        # Set the labels
        plt.xlabel("Date")
        plt.ylabel("Cumulative return")

        # Set the x limit
        plt.xlim(index_df.index[0], index_df.index[-1])

        # Set the title
        plt.title("Equity curve")

        # Set the legend
        plt.legend(loc="upper left")
        # Adjust the spacing
        plt.tight_layout()

        # Save the plot
        if save:
            figure_folder = os.path.join(result_folder, "Figure")
            filename = os.path.join(figure_folder, f"{infix}eqcurve{factors}{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.png")
            plt.savefig(filename, dpi=300)
        
        # Show the plot
        plt.show()
        
    else:
        # Load the momentum dictionary if it exists
        momentum_dict_folder = os.path.join(result_folder, "Momentum dict")
        momentum_dict_filename = os.path.join(momentum_dict_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.pkl")
        if os.path.isfile(momentum_dict_filename):
            with open(momentum_dict_filename, "rb") as file:
                momentum_dict = pickle.load(file)
        else:
            print("Error: momentum_dict not found.")
            return None
    
        # Create a figure for plotting all factor combinations
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return
        plt.plot(index_df["Cumulative Return"], label=index_dict[index_name])

        # Create an empty DataFrame to store cumulative stock returns
        cumulative_stock_returns_df = pd.DataFrame()

        # Iterate over all factor combinations
        for factors in tqdm(factors_group):
            # Convert the factors to a tuple for dictionary access
            factors_tuple = tuple(factors)

            # Retrieve the equity curve for the current factor combination
            factor_index_df = momentum_dict[factors_tuple]

            # Plot the cumulative stock return for the current factor combination
            scaling_factor = 1 / factor_index_df["Cumulative Stock Return"].iloc[0] * index_df["Cumulative Return"].iloc[0]
            plt.plot(factor_index_df["Cumulative Stock Return"] * scaling_factor, alpha=0.5)

            # Merge the cumulative stock return into the DataFrame
            cumulative_stock_returns_df = cumulative_stock_returns_df.join(factor_index_df["Cumulative Stock Return"] * scaling_factor, how="outer", rsuffix=f"_{factors_tuple}")

        # Set the labels
        plt.xlabel("Date")
        plt.ylabel("Cumulative return")

        # Set the x limit
        plt.xlim(index_df.index[0], index_df.index[-1])

        # Set the title
        plt.title("Equity curve")

        # Set the legend
        plt.legend(loc="upper left")

        # Adjust the spacing
        plt.tight_layout()

        # Save the plot
        if save:
            figure_folder = os.path.join(result_folder, "Figure")
            filename = os.path.join(figure_folder, f"{infix}eqcurveallyears{years}itv{interval}top{top}{sma_label}{cap_label}.png")
            plt.savefig(filename, dpi=300)

        # Show the plot
        plt.show()

        # Average the cumulative stock returns across the columns
        eqcurve_mean = cumulative_stock_returns_df.mean(axis=1)

        # Align the index of eqcurve_mean with index_df
        eqcurve_mean = eqcurve_mean.reindex(index_df.index, method="ffill")

        # Calculate the mean CAGR
        cagr_mean = (eqcurve_mean.iloc[-1] / eqcurve_mean.iloc[0])**(1 / (len(eqcurve_mean) / 252)) - 1

        # Create a figure
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return
        plt.plot(index_df.index, index_df["Cumulative Return"], label=index_dict[index_name])

        # Plot the mean equity curve
        plt.plot(index_df.index, eqcurve_mean, label=f"Mean CAGR: {cagr_mean * 100:.2f}%")

        # Set the labels
        plt.xlabel("Date")
        plt.ylabel("Mean Cumulative return")

        # Set the x limit
        plt.xlim(index_df.index[0], index_df.index[-1])

        # Set the title
        plt.title("Mean equity curve")

        # Set the legend
        plt.legend(loc="upper left")

        # Adjust the spacing
        plt.tight_layout()

        # Save the plot
        if save:
            filename_mean = os.path.join(figure_folder, f"{infix}eqcurvemeanyears{years}itv{interval}top{top}{sma_label}{cap_label}.png")
            plt.savefig(filename_mean, dpi=300)

        # Show the plot
        plt.show()

def plot_comparison(index_name, index_dict, all_stocks, momentum_params, x_values, y_values, z_values, z_index, z_label, regression_model="RandomForest", save=False):
    """
    Plot a 3D comparison between an index and stocks based on selected metrics.

    Parameters:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - x_values (array-like): Values for the x-axis.
    - y_values (array-like): Values for the y-axis.
    - z_values (array-like): Values for the z-axis.
    - z_index (array-like): Index values for the z-axis.
    - z_label (str): Label for the z-axis.
    - regression_model (str, optional): The regression model to use ("LinearRegression", "RandomForest", "SVM"). Default to "RandomForest".
    - save (bool, optional): If True, save the plot as a file. Default to False.

    Returns:
    - None: This function creates a 3D plot.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    # Create a 3D figure
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    # Scatter the data points in 3D space
    scatter = ax.scatter3D(x_values, y_values, z_values, c=z_values, cmap="Blues", alpha=1)

    # Set the labels for the axes
    ax.set_xlabel(r"$\mu$ (MVP)")
    ax.set_ylabel(r"$\nu$ (EPS YoY)")

    # Create a coordinate grid for the surface plot
    xx, yy = np.meshgrid(np.linspace(min(x_values), max(x_values), 10), np.linspace(min(y_values), max(y_values), 10))

    # Define the label for the surface based on the index
    label = f"{index_dict[index_name]}: {round(z_index, 2)}"

    # Get the maximum values in the data for labeling
    max_x = x_values[np.argmax(z_values)]
    max_y = y_values[np.argmax(z_values)]
    max_z = np.max(z_values)

    # Update the labels based on the z_label, handling percentage formats
    max_z_label = f"{round(max_z, 2)}"
    if z_label == "CAGR":
        label += "%"
        max_z_label += "%"

    # Plot a surface at the z_index level
    ax.plot_surface(xx, yy, z_index.reshape(1, -1), color="r", alpha=0.5, label=label)

    # Split the data into training and testing sets for regression
    x_train, x_test, y_train, y_test, z_train, z_test = train_test_split(x_values, y_values, z_values, test_size=0.2, random_state=42)

    # Split the data into training and testing sets for regression
    if regression_model == "LinearRegression":
        reg = LinearRegression()
    elif regression_model == "RandomForest":
        reg = RandomForestRegressor()
    elif regression_model == "SVM":
        reg = SVR()
    else:
        raise ValueError("Unsupported regression model. Choose 'SVM', 'LinearRegression', or 'RandomForest'.")

    # Fit the regression model to the training data
    reg.fit(np.column_stack((x_train, y_train)), z_train)

    # Make predictions for the test data
    z_pred = reg.predict(np.column_stack((x_test, y_test)))

    # Calculate the R-squared score for the predictions
    score = r2_score(z_test, z_pred)

    # Fit the regression model on the entire dataset for the best-fit plane
    reg.fit(np.column_stack((x_values, y_values)), z_values)
    plane_z = reg.predict(np.column_stack((xx.ravel(), yy.ravel())))

    # Plot the best-fit plane
    ax.plot_surface(xx, yy, plane_z.reshape(xx.shape), color="g", alpha=0.5, label="Best-fit Plane")

    # Add a label for the regression model being used
    model_label = {"LinearRegression": "Linear regression", "RandomForest": "Random forest", "SVM": "SVM"}[regression_model]

    # Add text annotations for maximum values and R-squared score
    text = fr"$\mu={max_x}$, $\nu={max_y}$, max {z_label}: {max_z_label}" + "\n" + fr"$R^2$ score: {round(score, 2)} ({model_label})"
    ax.text(0.15, 0.85, max_z, text, color="black")
    
    # Set the title
    plt.title(f"{z_label} comparison with {index_dict[index_name]}")

    # Set the legend
    plt.legend(loc="best")
    
    # Add a color bar to indicate the scale of z_values
    plt.colorbar(scatter, shrink=0.7).set_label(z_label)

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        figure_folder = os.path.join(result_folder, "Figure")
        filename = os.path.join(figure_folder, f"{infix}{z_label.replace(' ', '')}cfyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

# Calculate various financial statistics for a given dataframe
def calculate_stats(df, years, name=None, risk_free_rate=0.03):
    """
    Calculate various financial statistics for a given dataframe.

    Parameters:
    - df (DataFrame): DataFrame with a "Close" column.
    - years (int): Number of years for CAGR and other metrics.
    - name (str, optional): Name of the strategy. Default is None.
    - risk_free_rate (float, optional): Risk-free return rate. Default to 3%.

    Returns:
    - tuple: (yearly returns, stats array)
    """

    # Filter the data to the last "years" worth of trading days (assuming 252 trading days per year)
    df = df.tail(int(years * 252))

    # Capitalise name for consistency
    name = name.capitalize() if name and name[0].islower() else name

    # Calculate percent change and cumulative return of the original DataFrame
    df["Percent Change"] = df["Close"].pct_change()
    df.fillna({"Percent Change": 0}, inplace=True)
    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

    # Calculate the percent change and cumulative return of the strategy
    if name == "Strategy":
        # Calculate the total return for the strategy
        total_return = df[f"Cumulative {name} Return"].iloc[-1]
    elif name is not None:
        df[f"Cumulative {name} Return"] = (1 + df[f"{name} Percent Change"]).cumprod()
        total_return = df[f"Cumulative {name} Return"].iloc[-1]
    else:
        # If no name is provided, use the total return from the original dataframe
        total_return = df["Cumulative Return"].iloc[-1]

    # Calculate peak return and CAGR
    return_peak = df[f"Cumulative {name} Return"].max() if name else df["Cumulative Return"].max()
    cagr = total_return ** (1 / years) - 1

    # Calculate the Sharpe ratio
    percent_change_label = f"{name} Percent Change" if name else "Percent Change"
    return_mean = df[percent_change_label].mean() * 252
    volatility = df[percent_change_label].std() * (252 ** 0.5)
    sharpe_ratio = (return_mean - risk_free_rate) / volatility if volatility != 0 else np.nan

    # Calculate the Sortino ratio
    downside_deviation = df[percent_change_label].where(df[percent_change_label] < 0).std()
    sortino_ratio = (return_mean - risk_free_rate) / (downside_deviation * (252 ** 0.5)) if downside_deviation != 0 else np.nan

    # Calculate the Calmar ratio
    max_drawdown = (df[f"Cumulative {name} Return"] / df[f"Cumulative {name} Return"].cummax() - 1).min() if name else \
                    (df["Cumulative Return"] / df["Cumulative Return"].cummax() - 1).min()
    calmar_ratio = (cagr / abs(max_drawdown)) if max_drawdown != 0 else np.nan

    # Calculate annual returns
    indices = [- 1 - (i * 252) for i in range(int(np.ceil(years)))]
    dates = [df.index[index] for index in indices if index >= - len(df)][::-1]
    closes = df.loc[dates, f"Cumulative {name} Return" if name else "Cumulative Return"].values
    returns = np.diff(closes) / closes[:-1]

    # Calculate statistics of yearly returns
    returns_mean = np.mean(returns)
    returns_sd = np.std(returns)
    returns_skew = skew(returns)
    returns_kurt = kurtosis(returns)

    # Organise the statistics into an array
    stats = np.array([total_return, return_peak, cagr, volatility, sharpe_ratio, sortino_ratio, 
                      max_drawdown, calmar_ratio, returns_mean, returns_sd, returns_skew, returns_kurt])
    
    return returns, stats

def save_momentum_stats(index_name, index_dict, all_stocks, factors_group, momentum_params, reanalyse=False):
    """
    Save the statistics of all factor combinations of the momentum strategy.

    Parameters:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - reanalyse (bool, optional): If True, reanalyse and overwrite existing data. Default to False.

    Returns:
    - None: This function saves the statistics as a .npy file.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    # Define the filename for saving the statistics
    factors_stats_folder = os.path.join(result_folder, "Factors stats")
    filename = os.path.join(factors_stats_folder, f"{infix}factors_statsyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.npy")

    # Check if pre-existing data exists or if reanalysis is required
    if not os.path.isfile(filename) or reanalyse:
        # Initialise an empty array to store statistics for each factor combination
        factors_stats = np.empty((len(factors_group), 2), dtype=object)

        # Define the filename for the momentum dictionary
        momentum_dict_folder = os.path.join(result_folder, "Momentum dict")
        momentum_dict_filename = os.path.join(momentum_dict_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.pkl")

        # Load the momentum dictionary from file
        with open(momentum_dict_filename, "rb") as file:
            momentum_dict = pickle.load(file)

        # Iterate over all factor combinations to calculate and store statistics
        for i, factors in enumerate(tqdm(factors_group)):
            # Convert the list of factors to a tuple for dictionary access
            factors_tuple = tuple(factors)

            # Retrieve the equity curve for the current factor combination
            index_df = momentum_dict[factors_tuple]

            # Calculate statistics for the equity curve
            stats = calculate_stats(index_df, len(index_df) / 252, name="stock")
            
            # Store the factors and their corresponding statistics in the array
            factors_stats[i, 0] = np.array(factors)
            factors_stats[i, 1] = stats

        # Save the calculated statistics to a .npy file
        np.save(filename, factors_stats)
        print("Statistics of the momentum strategy saved.")
    else:
        print("Statistics of the momentum strategy saved before.")

def compare_index_momentum(index_df, index_name, index_dict, all_stocks, factors_stats, momentum_params, regression_model="RandomForest", save=False):
    """
    Compare the statistics between the index and stocks selected by the momentum strategy.

    Parameters:
    - index_df (DataFrame): DataFrame containing index data for analysis.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market. When True, all eligible stocks are included; otherwise, only a subset is used.
    - factors_stats (list): Statistics of the momentum strategy.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - regression_model (str, optional): The regression model to use ("LinearRegression", "RandomForest", "SVM"). Default to "RandomForest".
    - save (bool, optional): If True, save the comparison plots. Default to False.
    
    Returns:
    - None: This function prints comparison statistics and generates plots.
    """

    # Initialise lists to store various statistics
    xs = []
    ys = []
    cagr_values = []
    sharpe_ratio_values = []
    sortino_ratio_values = []

    # Calculate statistics for the index
    stats_index = calculate_stats(index_df, len(index_df) / 252)[1]
    cagr_index = stats_index[2]
    sharpe_ratio_index = stats_index[4]
    sortino_ratio_index = stats_index[5]
    
    # Iterate over the statistics of all factors to extract values
    for stats in factors_stats:
        mvp_factor, eps_yoy_factor, eps_qoq_factor = stats[0]
        cagr = stats[1][1][2] * 100 # Extract and convert CAGR to percentage
        sharpe_ratio = stats[1][1][4]
        sortino_ratio = stats[1][1][5]
        xs.append(mvp_factor)
        ys.append(eps_yoy_factor)
        cagr_values.append(cagr)
        sharpe_ratio_values.append(sharpe_ratio)
        sortino_ratio_values.append(sortino_ratio)

    # Calculate the proportion of CAGRs higher than the index's CAGR
    cagr_mean = np.mean(cagr_values)
    cagr_higher = sum(cagr > cagr_index * 100 for cagr in cagr_values) / len(cagr_values)

    # Calculate the proportion of Sharpe ratios higher than the index's Sharpe ratio
    sharpe_ratio_mean = np.mean(sharpe_ratio_values)
    sharpe_higher = sum(sharpe_ratio > sharpe_ratio_index for sharpe_ratio in sharpe_ratio_values) / len(sharpe_ratio_values)

    # Calculate the proportion of Sortino ratios higher than the index's Sortino ratio
    sortino_ratio_mean = np.mean(sortino_ratio_values)
    sortino_higher = sum(sortino_ratio > sortino_ratio_index for sortino_ratio in sortino_ratio_values) / len(sortino_ratio_values)

    # Print the calculated statistics
    print(f"Mean of screened stocks' CAGR: {round(cagr_mean, 2)}%.")
    print(f"Mean of screened stocks' Sharpe ratio: {round(sharpe_ratio_mean, 2)}.")
    print(f"Mean of screened stocks' Sortino ratio: {round(sortino_ratio_mean, 2)}.")
    print(f"CAGR of {index_dict[index_name]}: {round(cagr_index * 100, 2)}%.")
    print(f"Sharpe ratio of {index_dict[index_name]}: {round(sharpe_ratio_index, 2)}.")
    print(f"Sortino ratio of {index_dict[index_name]}: {round(sortino_ratio_index, 2)}.")
    print(f"Proportion of screened stocks' CAGR higher than {index_dict[index_name]}: {round(cagr_higher * 100, 2)}%.")
    print(f"Proportion of screened stocks' Sharpe ratio higher than {index_dict[index_name]}: {round(sharpe_higher * 100, 2)}%.")
    print(f"Proportion of screened stocks' Sortino ratio higher than {index_dict[index_name]}: {round(sortino_higher * 100, 2)}%.")
    
    # Generate and save plots for comparisons
    plot_comparison(index_name, index_dict, all_stocks, momentum_params, xs, ys, cagr_values, cagr_index * 100, "CAGR", regression_model=regression_model, save=save)
    plot_comparison(index_name, index_dict, all_stocks, momentum_params, xs, ys, sharpe_ratio_values, sharpe_ratio_index, "Sharpe ratio", regression_model=regression_model, save=save)
    plot_comparison(index_name, index_dict, all_stocks, momentum_params, xs, ys, sortino_ratio_values, sortino_ratio_index, "Sortino ratio", regression_model=regression_model, save=save)

def record_asset(df):
    """
    Record the asset after buy/sell signals.

    Parameters:
    - df (DataFrame): DataFrame containing "Buy" and "Sell" signals.

    Returns:
    - df (DataFrame): The modified DataFrame with "Asset Buy" and "Asset Sell" columns.
    """
    
    # Initialise columns for asset buy and sell positions
    df["Asset Buy"] = np.nan
    df["Asset Sell"] = np.nan
    
    # Set buy and sell positions based on signals
    df.loc[df["Buy"], "Asset Buy"] = 1
    df.loc[df["Sell"], "Asset Buy"] = 0
    df.loc[df["Sell"], "Asset Sell"] = 1
    df.loc[df["Buy"], "Asset Sell"] = 0
    
    # Forward fill the asset positions to carry forward the last known position
    df["Asset Buy"] = df["Asset Buy"].ffill().fillna(0)
    df["Asset Sell"] = df["Asset Sell"].ffill().fillna(0)
    
    # Shift the positions by one to reflect the previous day's position
    df["Asset Buy"] = df["Asset Buy"].shift(1)
    df["Asset Sell"] = df["Asset Sell"].shift(1)

    return df

def extract_position(s):
    """
    Extract positions from the asset signals.

    Parameters:
    - s (Series): Series of asset signals (1 for position taken, 0 otherwise).

    Returns:
    - tuple: (start_indices, end_indices)
    """

    # Determine start indices where a position is taken
    if s.iloc[0] == 1:
        start_index = [s.index[0], *s.loc[(s == 1) & (s.shift(1) == 0)].index]
    else:
        start_index = [*s.loc[(s == 1) & (s.shift(1) == 0)].index]
    
    # Determine end indices where a position is closed
    if s.iloc[-1] == 1:
        end_index = [*s.loc[(s.shift(-1) == 0) & (s == 1)].index, s.index[-1]]
    else:
        end_index = [*s.loc[(s.shift(-1) == 0) & (s == 1)].index]
        
    return np.array(start_index), np.array(end_index)

def plot_strategy_equity_curve(stock, df, col="Cumulative Strategy Return"):
    """
    Plot the equity curve of a given strategy.

    Parameters:
    - stock (str): Name of the stock being analysed.
    - df (DataFrame): DataFrame containing strategy returns and buy/sell signals.
    - col (str, optional): Column name of the cumulative strategy return. Default is "Cumulative Strategy Return".

    Returns:
    - None: This function plots an equity curve.
    """

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the cumulative strategy return
    plt.plot(df[col])

    # Plot the buy signals
    plt.scatter(df.index[df["Buy"]], df[col][df["Buy"]], marker="^", color="green", label="Buy")
    
    # Plot the sell signals
    plt.scatter(df.index[df["Sell"]], df[col][df["Sell"]], marker="v", color="red", label="Sell")

    # Set the title
    plt.title(f"Equity curve for {stock}")
    
    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Equity")

    # Set the x limit
    plt.xlim(df.index[0], df.index[-1])

    # Set the legend
    plt.legend([col] + ["Buy", "Sell"])

    # Adjust the spacing
    plt.tight_layout()

    # Show the plot
    plt.show()

def SMA_strategy(df, period_buy=200, period_sell=200, col="Close"):
    """
    Simple Moving Average (SMA) strategy implementation.

    Parameters:
    - df (DataFrame): DataFrame containing price data.
    - period_buy (int, optional): Period for SMA calculation used to generate buy signals. Default is 200.
    - period_sell (int, optional): Period for SMA calculation used to generate sell signals. Default is 200.
    - col (str, optional): Column name for price data. Default is "Close".

    Returns:
    - df (DataFrame): Modified DataFrame with "Buy" and "Sell" signals.
    """

    # Calculate the SMA for the specified periods
    df[f"SMA {period_buy}"] = SMA(df, period_buy, col=col)
    df[f"SMA {period_sell}"] = SMA(df, period_sell, col=col)

    # Identify buy and sell conditions based on price crossing the SMAs
    buy_conds = (df["Close"] >= df[f"SMA {period_buy}"]) & (df["Close"].shift(1) < df[f"SMA {period_buy}"].shift(1))
    sell_conds = (df["Close"] <= df[f"SMA {period_sell}"]) & (df["Close"].shift(1) > df[f"SMA {period_sell}"].shift(1))

    # Extract buy and sell indices
    buy_indices = df[buy_conds].index
    sell_indices = df[sell_conds].index
    buy_indices_int, sell_indices_int = [], []

    # Generate buy/sell signals by alternating based on indices
    if len(buy_indices) > 0 and len(sell_indices) > 0:
        next_index = "buy" if buy_indices[0] < sell_indices[0] else "sell"

        # Alternate between buying and selling based on the indices
        while len(buy_indices) > 0 and len(sell_indices) > 0:
            if next_index == "buy":
                buy_indices_int.append(buy_indices[0])
                buy_indices = buy_indices[1:]
                # Remove sell indices that occur before the last buy
                sell_indices = sell_indices[sell_indices > buy_indices_int[-1]]
                next_index = "sell"
            else:
                sell_indices_int.append(sell_indices[0])
                sell_indices = sell_indices[1:]
                # Remove buy indices that occur before the last sell
                buy_indices = buy_indices[buy_indices > sell_indices_int[-1]]
                next_index = "buy"
    else:
        print("No buy/sell signal generated.")

    # Assign the buy/sell signals to the DataFrame
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

def double_SMA_strategy(df, period_1=20, period_2=50, col="Close"):
    """
    Double Simple Moving Average (SMA) strategy implementation.

    Parameters:
    - df (DataFrame): DataFrame containing price data.
    - period_1 (int, optional): Period for the first SMA calculation. Default is 20.
    - period_2 (int, optional): Period for the second SMA calculation. Default is 50.
    - col (str, optional): Column name for price data. Default is "Close".

    Returns:
    - df (DataFrame): Modified DataFrame with "Buy" and "Sell" signals.
    """

    # Calculate the SMA for the specified periods
    df[f"SMA {period_1}"] = SMA(df, period_1, col=col)
    df[f"SMA {period_2}"] = SMA(df, period_2, col=col)

    # Identify buy and sell conditions based on SMA crossover
    buy_conds = (df[f"SMA {period_1}"] >= df[f"SMA {period_2}"]) & (df[f"SMA {period_1}"].shift(1) < df[f"SMA {period_2}"].shift(1))
    sell_conds = (df[f"SMA {period_1}"] <= df[f"SMA {period_2}"]) & (df[f"SMA {period_1}"].shift(1) > df[f"SMA {period_2}"].shift(1))

    # Extract buy and sell indices
    buy_indices = df[buy_conds].index
    sell_indices = df[sell_conds].index
    buy_indices_int, sell_indices_int = [], []

    # Generate buy/sell signals by alternating based on indices
    if len(buy_indices) > 0 and len(sell_indices) > 0:
        next_index = "buy" if buy_indices[0] < sell_indices[0] else "sell"

        # Alternate between buying and selling based on the indices
        while len(buy_indices) > 0 and len(sell_indices) > 0:
            if next_index == "buy":
                buy_indices_int.append(buy_indices[0])
                buy_indices = buy_indices[1:]
                # Remove sell indices that occur before the last buy
                sell_indices = sell_indices[sell_indices > buy_indices_int[-1]]
                next_index = "sell"
            else:
                sell_indices_int.append(sell_indices[0])
                sell_indices = sell_indices[1:]
                # Remove buy indices that occur before the last sell
                buy_indices = buy_indices[buy_indices > sell_indices_int[-1]]
                next_index = "buy"
    else:
        print("No buy/sell signal generated.")

    # Assign the buy/sell signals to the DataFrame
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

def RSI_strategy(df, period=14, col="Close", oversold=30, overbought=70):
    """
    Relative Strength Index (RSI) strategy implementation.

    Parameters:
    - df (DataFrame): DataFrame containing price data.
    - period (int, optional): Look-back period for RSI calculation. Default is 14.
    - col (str, optional): Column name for price data. Default is "Close".
    - oversold (float, optional): RSI level indicating oversold conditions. Default is 30.
    - overbought (float, optional): RSI level indicating overbought conditions. Default is 70.

    Returns:
    - df (DataFrame): Modified DataFrame with "Buy" and "Sell" signals.
    """

    # Calculate the RSI
    df = RSI(df, period=period, col=col)

    # Identify buy and sell conditions based on RSI levels
    buy_conds = (df["RSI"] <= oversold) & (df["RSI"].shift(1) > oversold)
    sell_conds = (df["RSI"] >= overbought) & (df["RSI"].shift(1) < overbought)

    # Extract buy and sell indices
    buy_indices = df[buy_conds].index
    sell_indices = df[sell_conds].index
    buy_indices_int, sell_indices_int = [], []

    # Generate buy/sell signals by alternating based on indices
    if len(buy_indices) > 0 and len(sell_indices) > 0:
        next_index = "buy" if buy_indices[0] < sell_indices[0] else "sell"

        # Alternate between buying and selling based on the indices
        while len(buy_indices) > 0 and len(sell_indices) > 0:
            if next_index == "buy":
                buy_indices_int.append(buy_indices[0])
                buy_indices = buy_indices[1:]
                # Remove sell indices that occur before the last buy
                sell_indices = sell_indices[sell_indices > buy_indices_int[-1]]
                next_index = "sell"
            else:
                sell_indices_int.append(sell_indices[0])
                sell_indices = sell_indices[1:]
                # Remove buy indices that occur before the last sell
                buy_indices = buy_indices[buy_indices > sell_indices_int[-1]]
                next_index = "buy"
    else:
        print("No buy/sell signal generated.")

    # Assign the buy/sell signals to the DataFrame
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

def market_breadth_strategy(df, period=200):
    """
    Market breadth strategy implementation.

    Parameters:
    - df (DataFrame): DataFrame containing price data.
    - period (int, optional): Period for market breadth calculation. Default is 200.

    Returns:
    - df (DataFrame): Modified DataFrame with "Buy" and "Sell" signals.
    """

    # Identify buy and sell conditions based on market breadth
    buy_conds = (df[f"Half Above SMA {period}"] == True) & (df[f"Half Above SMA {period}"].shift(1) == False)
    sell_conds = (df[f"Half Above SMA {period}"] == False) & (df[f"Half Above SMA {period}"].shift(1) == True)

    # Extract buy and sell indices
    buy_indices = df[buy_conds].index
    sell_indices = df[sell_conds].index
    buy_indices_int, sell_indices_int = [], []

    # Generate buy/sell signals by alternating based on indices
    if len(buy_indices) > 0 and len(sell_indices) > 0:
        next_index = "buy" if buy_indices[0] < sell_indices[0] else "sell"

        # Alternate between buying and selling based on the indices
        while len(buy_indices) > 0 and len(sell_indices) > 0:
            if next_index == "buy":
                buy_indices_int.append(buy_indices[0])
                buy_indices = buy_indices[1:]
                # Remove sell indices that occur before the last buy
                sell_indices = sell_indices[sell_indices > buy_indices_int[-1]]
                next_index = "sell"
            else:
                sell_indices_int.append(sell_indices[0])
                sell_indices = sell_indices[1:]
                # Remove buy indices that occur before the last sell
                buy_indices = buy_indices[buy_indices > sell_indices_int[-1]]
                next_index = "buy"
    else:
        print("No buy/sell signal generated.")

    # Assign the buy/sell signals to the DataFrame
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

def test_strategy(stock, df, years, fee_rate=0.00, short=False):
    """
    Test a trading strategy based on buy/sell signals.

    Parameters:
    - stock (str): Name of the stock being analysed.
    - df (DataFrame): DataFrame containing price data.
    - years (int): Number of years to test the strategy.
    - fee_rate (float, optional): Transaction fee rate. Default is 0.001.
    - short (bool, optional): If True, allow short selling. Default is False.

    Returns:
    - None: This function performs calculations and plots an equity curve.
    """

    # Count and print the number of buy and sell signals
    print("Number of Buy signals:", df["Buy"].sum())
    print("Number of Sell signals:", df["Sell"].sum())

    # Record the asset positions after buy/sell actions
    df = record_asset(df)
    
    # Initialise the commission fee column
    df["Fee"] = float(0)

    # Extract buy and sell positions
    buy_start, buy_end = extract_position(df["Asset Buy"])
    sell_start, sell_end = extract_position(df["Asset Sell"])

    # Assign the fee to the appropriate positions
    df.loc[buy_start, "Fee"] = fee_rate
    df.loc[buy_end, "Fee"] = fee_rate
    df.loc[sell_start, "Fee"] = fee_rate
    df.loc[sell_end, "Fee"] = fee_rate

    # Calculate percent change and cumulative return of the original DataFrame
    df["Percent Change"] = df["Close"].pct_change()
    df.fillna({"Percent Change": 0}, inplace=True)
    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

    # Taking fees into account and calculate cumulative return
    df[f"Strategy Percent Change"] = ((df["Percent Change"] - df["Fee"]) * df["Asset Buy"]).fillna(0)
    if short:
        df[f"Strategy Percent Change"] -= ((df["Percent Change"] - df["Fee"]) * df["Asset Sell"]).fillna(0)
    df[f"Cumulative Strategy Return"] = (1 + df[f"Strategy Percent Change"]).cumprod()

    # Print the statistics of the strategy
    print(calculate_stats(df, years, name="strategy")[1])

    # Print statistics of a buy and hold strategy
    print(calculate_stats(df, years)[1])

    # Plot the equity curve of the strategy
    plot_strategy_equity_curve(stock, df)

# Main function
def main():
    # Start of the program
    start = dt.datetime.now()

    # Define the paths for the folders
    folders = ["Backtest", "Backtest/Equity curve", "Backtest/Factors stats", "Backtest/Figure", "Backtest/Momentum dict", "Backtest/Stock dict"]

    # Create folders if they do not exist
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    
    # Variables
    all_stocks = True
    period_short = 60
    period_long = 252
    RS = 90
    factors = [0.1, 0.55, 0.35]
    backtest = False

    # Index
    index_name = "^GSPC"
    index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite"}

    # Get the infix
    infix = get_infix("^GSPC", index_dict, all_stocks)

    # Modify the current date
    current_date = modify_current_date(start, index_name)
    current_date = "2025-01-01"

    # Parameters for backtesting the momentum strategy
    years = 5
    interval = "2w"
    top = 5
    cap_threshold = 10
    stoploss_threshold = 0.08
    stopgain_threshold = 0.16
    momentum_params = {"years": years, 
                       "interval": interval, 
                       "top": top, 
                       "cap_threshold": cap_threshold, 
                       "stoploss_threshold": stoploss_threshold, 
                       "stopgain_threshold": stopgain_threshold, 
                       "period_short": 1, 
                       "period_long": 200, 
                       "sma_crossover": True, 
                       "leverage": 1, 
                       "fee_rate": 0.001, 
                       "slippage": 0}

    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    # Create the end dates
    end_dates = generate_end_dates(end_date="2024-12-20", years=7, interval=interval)
    if years < 7:
        start_date = generate_end_dates(end_date=end_dates[-1], years=years, interval=interval)[0]
        end_dates = [date for date in end_dates if date >= start_date]

    # Create a group of factors
    factors_group = [[i / 20, j / 20, k / 20] 
                     for i, j, k in itertools.product(range(21), repeat=3)
                     if i + j + k == 20]
    
    # Create the stock dictionary for all factor comnbinations
    for factors in tqdm(factors_group):
        create_stock_dict(end_dates, index_name, index_dict, all_stocks, factors, cap_threshold=cap_threshold, backtest=backtest)
    
    generate_stats = False
    if generate_stats:
        # Create a dictionary to store the returns of all factor combinations for the momentum strategy
        create_momentum_dict(end_dates, current_date, index_name, index_dict, all_stocks, factors_group, momentum_params)

        # Save the statistics of all factor combinations of the momentum strategy
        save_momentum_stats(index_name, index_dict, all_stocks, factors_group, momentum_params)

    plot_momentum_equity_curve_single = True
    if plot_momentum_equity_curve_single:
        # Plot the equity curve of stocks of the momentum strategy for one factor combination
        factors = [0.1, 0.55, 0.35]
        index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, all_stocks, factors, momentum_params)
        print(calculate_stats(index_df, len(index_df) / 252, "stock")[0])
        print(calculate_stats(index_df, len(index_df) / 252, "stock")[1])
        plot_momentum_equity_curve(index_df, index_name, index_dict, all_stocks, factors, factors_group, momentum_params)
    
    plot_momentum_equity_curve_all = False
    if plot_momentum_equity_curve_all:
        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Filter index data to the backtesting period
        index_df = index_df.loc[end_dates[0] : end_dates[-1]]

        # Plot the equity curve of stocks of the momentum strategy for all factor combinations
        plot_momentum_equity_curve(index_df, index_name, index_dict, all_stocks, None, factors_group, momentum_params, plot_group=True, save=True)
    
    show_momentum_stats = False
    if show_momentum_stats:
        # Load the statistics of all factor combinations
        factors_stats = np.load(f"Backtest/Factors stats/{infix}factors_statsyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.npy", allow_pickle=True)

        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Filter index data to the backtesting period
        index_df = index_df.loc[end_dates[0] : end_dates[-1]]

        # Compare the statistics between the index and stocks selected by the momentum strategy
        print(calculate_stats(index_df, len(index_df) / 252)[0])
        print(calculate_stats(index_df, len(index_df) / 252)[1])
        compare_index_momentum(index_df, index_name, index_dict, all_stocks, factors_stats, momentum_params, save=True)
    
    index_corr_ta = False
    if index_corr_ta:
        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Add technical indicators to the data
        index_df = add_indicator(index_df)

        # Plot the correlation matrix of technical indicators
        plot_corr_ta(index_name, index_df)
    
    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()