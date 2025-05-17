# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
from helper_functions import get_df, get_infix, merge_stocks
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
import os
import pandas as pd
from scipy.signal import argrelextrema
from scipy.stats import kurtosis, linregress, norm, skew
import seaborn as sns
from statsmodels.tsa.stattools import acf
from technicals import *

def plot_close(stock, df, show=120, sma=True, MVP_VCP=True, local_extrema=False, local_extrema_period=5, FTD_DD=False, save=False):
    """
    Visualize the closing price history of a stock with optional technical indicators.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - show (int, optional): The number of most recent data points to display. Default is 120.
    - sma (bool, optional): Whether to plot Simple Moving Averages (SMA). Default is True.
    - MVP_VCP (bool, optional): Whether to plot MVP (Market Value Patterns) and VCP (Volatility Contraction Patterns) markers. Default is True.
    - local_extrema (bool, optional): Whether to identify and plot local extrema. Default is False.
    - local_extrema_period (int, optional): The period used for calculating local extrema. Default is 5.
    - FTD_DD (bool, optional): Whether to plot Follow-Through Days (FTD) and Distribution Days (DD). Default is False.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Check for candlestick columns
    cols_cs = ["High", "Low", "Open"]
    cond_cs = all(col in df.columns for col in cols_cs)
    
    # Add technical indicators to the data
    if cond_cs:
        df = add_indicator(df)
    else:
        print(f"Missing columns: {', '.join([col for col in cols_cs if col not in df.columns])}. Candlestick chart not created.")

    # Find and process local extrema if requested
    if local_extrema:
        df = get_local_extrema(df, period=local_extrema_period)

        # Calculate retracement values
        local_min1, local_max1, retracement = calculate_retracement(df)

        # Calculate the percentage of retracement
        retracement_pct = round(retracement * 100, 2) if retracement is not None else None

    # Filter the DataFrame to show the most recent data points
    df = df[- show:]
    
    if cond_cs:
        # Define widths for candlestick representation
        width_candle = 1
        width_stick = 0.2

        # Separate the DataFrame into upward and downward candlesticks
        up_df = df[df["Close"] >= df["Open"]]
        down_df = df[df["Close"] <= df["Open"]]
        colour_up = "green"
        colour_down = "red"

    # Create a figure with two subplots: top for closing prices, bottom for volume
    if "Volume" in df.columns and stock != "^VIX":
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [5, 1]}, sharex=True)
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(10, 6))

    if cond_cs:
        # Plot the green candlesticks (up prices)
        ax1.bar(up_df.index, up_df["Close"] - up_df["Open"], width_candle, bottom=up_df["Open"], color=colour_up)
        ax1.bar(up_df.index, up_df["High"] - up_df["Close"], width_stick, bottom=up_df["Close"], color=colour_up)
        ax1.bar(up_df.index, up_df["Low"] - up_df["Open"], width_stick, bottom=up_df["Open"], color=colour_up)

        # Plot the red candlesticks (down prices)
        ax1.bar(down_df.index, down_df["Close"] - down_df["Open"], width_candle, bottom=down_df["Open"], color=colour_down)
        ax1.bar(down_df.index, down_df["High"] - down_df["Open"], width_stick, bottom=down_df["Open"], color=colour_down)
        ax1.bar(down_df.index, down_df["Low"] - down_df["Close"], width_stick, bottom=down_df["Close"], color=colour_down)

        # Plot MVP and VCP conditions if requested
        if MVP_VCP and all(col in df.columns for col in ["MVP", "VCP"]):
            ax1.scatter(df.index[df["MVP"] == "M"], df["Close"][df["MVP"] == "M"], marker="^", edgecolor="black", facecolors="grey", label="M")
            ax1.scatter(df.index[df["MVP"] == "MP"], df["Close"][df["MVP"] == "MP"], marker="^", edgecolor="black", facecolors="yellow", label="MP")
            ax1.scatter(df.index[df["MVP"] == "MV"], df["Close"][df["MVP"] == "MV"], marker="^", edgecolor="black", facecolors="blue", label="MV")
            ax1.scatter(df.index[df["MVP"] == "MVP"], df["Close"][df["MVP"] == "MVP"], marker="^", edgecolor="black", facecolors="green", label="MVP")
            ax1.scatter(df.index[df["VCP"] == True], df["Close"][df["VCP"] == True], marker=">", edgecolor="black", facecolors="orange", label="VCP")

        # Plot FTDs and DDs if requested
        if FTD_DD and all(col in df.columns for col in ["FTD", "DD"]):
            ax1.scatter(df.index[df["FTD"]], df["Low"][df["FTD"]] * 0.98, marker="x", color="green", label="FTD")
            ax1.scatter(df.index[df["DD"]], df["Low"][df["DD"]] * 0.98, marker="x", color="red", label="DD")

        # Plot SMAs if requested
        periods = [5, 20, 50, 200]
        sma_cols = [f"SMA {str(i)}" for i in periods]
        if sma and all(col in df.columns for col in sma_cols):
            for period, col in zip(periods, sma_cols):
                ax1.plot(df.index, df[col], label=f"SMA {period}")
    else:
        # Plot the closing prices
        ax1.plot(df.index, df["Close"])

    # Scatter plot for local minima and maxima if requested
    if local_extrema:
        ax1.scatter(df.index[df["Local Min"]], df["Low"][df["Local Min"]], label="Local extrema", marker="x", color="black")
        ax1.scatter(df.index[df["Local Max"]], df["High"][df["Local Max"]], marker="x", color="black")

        # Add retracement percentage information as text on the plot
        if retracement_pct is not None:
            ax1.text(0.4, 0.95, f"Retracement: {retracement_pct}%\nRecent min: {round(local_min1, 2)}\nRecent max: {round(local_max1, 2)}", 
                    transform=ax1.transAxes, fontsize=10, ha="left", va="top", bbox=dict(facecolor="white", alpha=0.5))

    # Set the y label of the top subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the top subplot
    buffer = relativedelta(days=1)
    ax1.set_xlim(df.index[0] - buffer, df.index[-1] + buffer)

    if "Volume" in df.columns and stock != "^VIX":
        # Plot the volume on the bottom subplot
        ax2.bar(up_df.index, up_df["Volume"], label="Volume (+)", color=colour_up)
        ax2.bar(down_df.index, down_df["Volume"], label="Volume (\N{MINUS SIGN})", color=colour_down)

        # Plot the 50-day SMA of volume
        ax2.plot(df["Volume SMA 50"], label="Volume SMA 50", color="purple")

        # Set the label of the bottom subplot
        ax2.set_ylabel("Volume")

        # Set the x label
        plt.xlabel("Date")

        # Combine legends from both subplots and place in the top subplot
        handles, labels = ax1.get_legend_handles_labels()
        handles += ax2.get_legend_handles_labels()[0]
        labels += ax2.get_legend_handles_labels()[1]
        ax1.legend(handles, labels)

    # Set the title
    plt.suptitle(f"Closing price history for {stock}")

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"close{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_volume_profile(stock, df, interval_num=200, price_interval=0.1, show=252, window=20, tol=0.01, save=False):
    """
    Plots the candlestick chart and volume profile for a given stock.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - interval_num (int, optional): Number of price bins to uniformly span the price range. Default is 200.
    - price_interval (float, optional): Interval to discretize the price range of each candle. Default is 0.1.
    - show (int, optional): The number of most recent data points to display. Default is 252.
    - window (int, optional): The window size for calculating the rolling maximum of the volume profile. Default is 20.
    - tol (float, optional): Tolerance for grouping proximate price levels. Default is 0.005 (0.5%).
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Get the volume profile
    if "Volume" in df.columns:
        volume_profile = compute_volume_profile(df, period=show, interval_num=interval_num, price_interval=price_interval)
    else:
        print("Volume data not found. Volume profile not created.")
        return
    
    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Check for candlestick columns
    cols_cs = ["High", "Low", "Open"]
    cond_cs = all(col in df.columns for col in cols_cs)

    # Add technical indicators to the data
    if cond_cs:
        df = add_indicator(df)
    else:
        print(f"Missing columns: {', '.join([col for col in cols_cs if col not in df.columns])}. Candlestick chart not created.")

    # Filter the DataFrame to show the most recent data points
    df = df[- show:]

    if cond_cs:
        # Define widths for candlestick representation
        width_candle = 1
        width_stick = 0.2

        # Separate the DataFrame into upward and downward candlesticks
        up_df = df[df["Close"] >= df["Open"]]
        down_df = df[df["Close"] <= df["Open"]]
        colour_up = "green"
        colour_down = "red"

    # Create a figure
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Create an additional axis on the right, sharing the y-axis with ax1
    divider = make_axes_locatable(ax1)
    ax2 = divider.append_axes("right", size="25%", pad=0.3, sharey=ax1)

    if cond_cs:
        # Plot the green candlesticks (up prices)
        ax1.bar(up_df.index, up_df["Close"] - up_df["Open"], width_candle, bottom=up_df["Open"], color=colour_up)
        ax1.bar(up_df.index, up_df["High"] - up_df["Close"], width_stick, bottom=up_df["Close"], color=colour_up)
        ax1.bar(up_df.index, up_df["Low"] - up_df["Open"], width_stick, bottom=up_df["Open"], color=colour_up)

        # Plot the red candlesticks (down prices)
        ax1.bar(down_df.index, down_df["Close"] - down_df["Open"], width_candle, bottom=down_df["Open"], color=colour_down)
        ax1.bar(down_df.index, down_df["High"] - down_df["Open"], width_stick, bottom=down_df["Open"], color=colour_down)
        ax1.bar(down_df.index, down_df["Low"] - down_df["Close"], width_stick, bottom=down_df["Close"], color=colour_down)
    else:
        # Plot the closing prices
        ax1.plot(df.index, df["Close"])

    # Set the labels and title
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Price")
    ax1.set_title(f"Closing price history and volume profile for {stock}")

    # Set the x limit of the left subplot
    buffer = pd.Timedelta(days=1)
    ax1.set_xlim(df.index[0] - buffer, df.index[-1] + buffer)

    # Plot the volume profile on the right subplot as a horizontal bar chart
    ax2.barh(volume_profile.index, volume_profile["Volume"], color="blue", alpha=0.7)

    # Extract the price levels for edge points of the volume profile
    prices = volume_profile.index.to_numpy()
    
    # Append the last bin edge to cover the final range
    edges = np.append(prices, prices[-1] + (prices[-1] - prices[-2]))
    heights = np.diff(edges)
    for bar, h in zip(ax2.patches, heights):
        bar.set_height(h)
    
    # Set the x label of the right subplot
    ax2.set_xlabel("Volume")
    ax2.yaxis.set_visible(False)

    # Invert the x-axis of ax2 for improved visual alignment
    ax2.invert_xaxis()

    # Calculate the rolling maximum of the volume profile and filter out zero volumes
    local_max = volume_profile[(volume_profile["Volume"] == volume_profile["Volume"].rolling(window=window, center=True).max()) & (volume_profile["Volume"] > 0)]
    local_prices = sorted(local_max.index)

    # Initialise two lists to store the combined price levels
    combined_prices = []
    group = []

    # Group proximate price levels within the tolerance to determine support/resistance levels
    for price in local_prices:
        if not group or np.abs(price - group[-1]) < tol * group[-1]:
            group.append(price)
        else:
            combined_prices.append(np.mean(group))
            group = [price]

    if group:
        combined_prices.append(np.mean(group))

    # Plot horizontal red dotted lines and add text labels indicating the values on the left
    first = True
    for price in combined_prices:
        ax1.axhline(y=price, linestyle="dotted", color="red", alpha=0.7, label="Support/Resistance" if first else None)

        # Annotate the price level with a text label to the left of the plot
        ax1.annotate(f"{price:.2f}", xy=(df.index[0], price), xytext=(0, -10), textcoords="offset points", va="center", color="black")
        first = False

    # Set the legend
    ax1.legend(loc="best")

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"{stock}_volume_profile.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_MACD(stock, df, zscore_period=252, show=252, save=False):
    """
    Plot the MACD (Moving Average Convergence Divergence) indicator along with its z-score.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - zscore_period (int, optional): The period over which to calculate the z-score of the MACD bar. Default is 252 (1 year of trading days).
    - show (int, optional): The number of most recent data points to display. Default is 252.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Add technical indicators to the DataFrame
    df = add_indicator(df)

    # Calculate the z-score of the MACD bar to standardize its values
    df = calculate_zscore(df, ["MACD Bar"], zscore_period)

    # Filter the DataFrame to show only the most recent data points
    df = df[- show:]

    # Separate the DataFrame into upward and downward MACD bars based on their values
    up_df = df[df["MACD Bar"] > 0]
    down_df = df[df["MACD Bar"] <= 0]
    colour_up = "green"
    colour_down = "red"

    # Create a figure with three subplots： one for the closing price, one for the MACD indicator, and one for the MACD bar z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    buffer = relativedelta(days=1)
    ax1.set_xlim(df.index[0] - buffer, df.index[-1] + buffer)

    # Plot the MACD indicator on the second subplot
    ax2.plot(df.index, df["MACD"], color="darkgreen")
    ax2.plot(df.index, df["MACD Signal Line"], color="darkred")
    ax2.bar(up_df.index, up_df["MACD Bar"], color=colour_up)
    ax2.bar(down_df.index, down_df["MACD Bar"], color=colour_down)
    ax2.axhline(y=0, linestyle="dotted", color="black")

    # Set the y label of the second subplot
    ax2.set_ylabel(f"MACD")

    # Plot the MACD bar z-score on the third subplot
    ax3.plot(df["MACD Bar Z-Score"], color="orange", alpha=0.7)
    ax3.axhline(y=2, linestyle="dotted", color="red")
    ax3.axhline(y=0, linestyle="dotted", color="black")
    ax3.axhline(y=-2, linestyle="dotted", color="red")

    # Set the y label of the third subplot
    ax3.set_ylabel(f"MACD Z-Score")

    # Set the x label
    plt.xlabel("Date")
    
    # Set the title
    plt.suptitle(f"MACD for {stock}")

    # Combine legends from all subplots and place them in the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"MACD{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_MFI_RSI(stock, df, mfi_period=14, rsi_period=14, zscore_period=252, show=252, save=False):
    """
    Plot the Money Flow Index (MFI) and Relative Strength Index (RSI) indicators along with their z-scores.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - mfi_period (int, optional): The period over which to calculate the MFI. Default is 14.
    - rsi_period (int, optional): The period over which to calculate the RSI. Default is 14.
    - zscore_period (int, optional): The period over which to calculate the z-scores of MFI and RSI. Default is 252 (1 year of trading days).
    - show (int, optional): The number of most recent data points to display. Default is 252.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Calculate the MFI and RSI indicators, adding them to the DataFrame
    df = MFI(df, period=mfi_period)
    df = RSI(df, period=rsi_period)

    # Calculate the z-scores for MFI and RSI to standardize their values
    df = calculate_zscore(df, ["MFI", "RSI"], zscore_period)

    # Filter the DataFrame to show only the most recent data points
    df = df[- show:]

    # Create a figure with three subplots: one for the closing price, one for the MFI/RSI indicator, and one for the MFI/RSI z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    ax1.set_xlim(df.index[0], df.index[-1])

    # Plot the MFI/RSI indicator on the second subplot
    ax2.plot(df["MFI"], label="MFI", color="orange", alpha=0.7)
    ax2.plot(df["RSI"], label="RSI", color="green", alpha=0.7)
    ax2.axhline(y=20, linestyle="dotted", label="Oversold/Overbought", color="red")
    ax2.axhline(y=50, linestyle="dotted", color="black")
    ax2.axhline(y=80, linestyle="dotted", color="red")

    # Set the y label of the second subplot
    ax2.set_ylabel(f"MFI/RSI")

    # Plot the MFI/RSI z-score on the third subplot
    ax3.plot(df["MFI Z-Score"], color="orange", alpha=0.7)
    ax3.plot(df["RSI Z-Score"], color="green", alpha=0.7)
    ax3.axhline(y=2, linestyle="dotted", color="red")
    ax3.axhline(y=0, linestyle="dotted", color="black")
    ax3.axhline(y=-2, linestyle="dotted", color="red")

    # Set the y label of the third subplot
    ax3.set_ylabel(f"MFI/RSI Z-Score")

    # Set the x label
    plt.xlabel("Date")
    
    # Set the title
    plt.suptitle(f"MFI/RSI for {stock}")

    # Combine legends from all subplots and place them in the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"MFIRSI{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_RMV(stock, df, rmv_period_short=5, rmv_period_long=14, zscore_period=252, col="Close", show=252, save=False):
    """
    Plot the Relative Momentum Volume (RMV) indicator along with its z-score.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - rmv_period_short (int, optional): The short period for calculating RMV. Default is 5.
    - rmv_period_long (int, optional): The long period for calculating RMV. Default is 14.
    - zscore_period (int, optional): The period over which to calculate the z-scores of RMV. Default is 252.
    - col (str, optional): The column name to be used for RMV calculation. Default is "Close".
    - show (int, optional): The number of most recent data points to display. Default is 252.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Calculate the RMV indicator
    df = RMV(df, period_short=rmv_period_short, period_long=rmv_period_long, col=col)

    # Calculate the z-scores for RMV to standardize its values
    df = calculate_zscore(df, ["RMV"], zscore_period)

    # Filter the DataFrame to show only the most recent data points
    df = df[- show:]

    # Create a figure with three subplots: one for the closing price, one for the RMV indicator, and one for the RMV z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    ax1.set_xlim(df.index[0], df.index[-1])

    # Plot the RMV indicator on the second subplot
    ax2.plot(df["RMV"], label="RMV", color="orange", alpha=0.7)
    ax2.axhline(y=15, linestyle="dotted", color="black")

    # Set the y label of the second subplot
    ax2.set_ylabel(f"RMV")

    # Plot the RMV z-score on the third subplot
    ax3.plot(df["RMV Z-Score"], color="orange", alpha=0.7)
    ax3.axhline(y=2, linestyle="dotted", color="red")
    ax3.axhline(y=0, linestyle="dotted", color="black")
    ax3.axhline(y=-2, linestyle="dotted", color="red")

    # Set the y label of the third subplot
    ax3.set_ylabel(f"RMV Z-Score")

    # Set the x label
    plt.xlabel("Date")
    
    # Set the title
    plt.suptitle(f"RMV for {stock}")

    # Combine legends from all subplots and place them in the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"RMV{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_ADX(stock, df, zscore_period=252, show=252, save=False):
    """
    Plot the Average Directional Index (ADX) and its z-score.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - zscore_period (int, optional): The period over which to calculate the z-score of ADX. Default is 252 (1 year of trading days).
    - show (int, optional): The number of most recent data points to display. Default is 252.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Add technical indicators to the DataFrame
    df = add_indicator(df)

    # Calculate the z-score for the ADX to standardize its values
    df = calculate_zscore(df, "ADX", zscore_period)

    # Filter the DataFrame to show only the most recent data points
    df = df[- show:]

    # Create a figure with three subplots: one for the closing price, one for the ADX indicator, and one for the ADX z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    ax1.set_xlim(df.index[0], df.index[-1])

    # Plot the ADX indicator on the second subplot
    ax2.plot(df["ADX"], label="ADX", color="orange")

    # Set the y label of the second subplot
    ax2.set_ylabel(f"ADX")

    # Plot the ADX z-score on the third subplot
    ax3.plot(df["ADX Z-Score"], label="ADX Z-Score", color="orange")
    ax3.axhline(y=2, linestyle="dotted", color="red")
    ax3.axhline(y=0, linestyle="dotted", color="black")
    ax3.axhline(y=-2, linestyle="dotted", color="red")

    # Set the y label of the third subplot
    ax3.set_ylabel(f"ADX Z-Score")

    # Set the x label
    plt.xlabel("Date")
    
    # Set the title
    plt.suptitle(f"ADX for {stock}")

    # Combine legends from all subplots and place them in the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"ADX{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_signal_bar(stock, df, show=252, save=False):
    """
    Plot the signal bar indicator.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - show (int, optional): The number of most recent data points to display. Default is 120.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Check for candlestick columns
    cols_cs = ["High", "Low", "Open"]
    cond_cs = all(col in df.columns for col in cols_cs)
    
    # Add signal bar indicator to the data
    if cond_cs:
        df = signal_bar(df)
    else:
        print(f"Missing columns: {', '.join([col for col in cols_cs if col not in df.columns])}. Signal bar indicator cannot be plotted.")
        return None

    # Filter the DataFrame to show the most recent data points
    df = df[- show:]
    
    # Define widths for candlestick representation
    width_candle = 1
    width_stick = 0.2

    # Separate the DataFrame into upward and downward candlesticks
    up_df = df[df["Close"] >= df["Open"]]
    down_df = df[df["Close"] <= df["Open"]]
    colour_up = "green"
    colour_down = "red"

    # Create a figure with three subplots: one for closing prices, one for volume, and one for the signal bar indicator
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the green candlesticks (up prices)
    ax1.bar(up_df.index, up_df["Close"] - up_df["Open"], width_candle, bottom=up_df["Open"], color=colour_up)
    ax1.bar(up_df.index, up_df["High"] - up_df["Close"], width_stick, bottom=up_df["Close"], color=colour_up)
    ax1.bar(up_df.index, up_df["Low"] - up_df["Open"], width_stick, bottom=up_df["Open"], color=colour_up)

    # Plot the red candlesticks (down prices)
    ax1.bar(down_df.index, down_df["Close"] - down_df["Open"], width_candle, bottom=down_df["Open"], color=colour_down)
    ax1.bar(down_df.index, down_df["High"] - down_df["Open"], width_stick, bottom=down_df["Open"], color=colour_down)
    ax1.bar(down_df.index, down_df["Low"] - down_df["Close"], width_stick, bottom=down_df["Close"], color=colour_down)

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    buffer = relativedelta(days=1)
    ax1.set_xlim(df.index[0] - buffer, df.index[-1] + buffer)

    # Plot the volume on the second subplot
    ax2.bar(up_df.index, up_df["Volume"], label="+", color=colour_up)
    ax2.bar(down_df.index, down_df["Volume"], label="\N{MINUS SIGN}", color=colour_down)

    # Set the label of the second subplot
    ax2.set_ylabel("Volume")

    # Plot the positive signal bar on the third subplot
    ax3.plot(df["+ Bar"], color=colour_up)

    # Plot the negative signal bar on the third subplot
    ax3.plot(df["- Bar"], color=colour_down)

    # Set the label of the third subplot
    ax3.set_ylabel("Signal bar")

    # Set the x label
    plt.xlabel("Date")

    # Combine legends from both subplots and place in the top subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Set the title
    plt.suptitle(f"Signal bar for {stock}")

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"signalbar{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_volatility(stock, df, zscore_period=252, show=120, save=False):
    """
    Plot the volatility of a stock based on the TR/ATR ratio, volume SMA 50 ratio, and their combined z-scores.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - zscore_period (int, optional): The period over which to calculate the z-scores. Default is 252 (1 year of trading days).
    - show (int, optional): The number of most recent data points to display. Default is 120.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Add technical indicators to the DataFrame
    df = add_indicator(df)

    # Calculate the TR/ATR ratio to measure volatility
    df["TR/ATR"] = df["TR"] / df["ATR"]

    # Calculate the volume SMA 50 ratio to assess relative volume
    df["Vol/SMA50"] = df["Volume"] / df["Volume SMA 50"]

    # Calculate the product of TR/ATR ratio and volume SMA 50 ratio
    df["TR/ATR * Vol/SMA50"] = df["TR/ATR"] * df["Vol/SMA50"]

    # Calculate the z-scores of the TR/ATR ratio, volume SMA 50 ratio, and their product to standardize values
    df = calculate_zscore(df, ["TR/ATR", "Vol/SMA50", "TR/ATR * Vol/SMA50"], zscore_period)

    # Filter the DataFrame to show only the most recent data points
    df = df[- show:]

    # Create a figure with four subplots: one for the price, one for the TR/ATR z-score, one for the volume SMA 50 ratio z-score, and one for the combined z-score
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [1, 1, 1, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    ax1.set_xlim(df.index[0], df.index[-1])

    # Plot the TR/ATR ratio z-score on the second subplot
    ax2.plot(df["TR/ATR Z-Score"])
    ax2.axhline(y=2, linestyle="dotted", label="Expansion", color="red")
    ax2.axhline(y=0, linestyle="dotted", color="black")
    ax2.axhline(y=-2, linestyle="dotted", label="Contraction", color="green")

    # Set the y label of the second subplot
    ax2.set_ylabel("TR/ATR Z-Score")

    # Plot the volume SMA 50 ratio z-score on the third subplot
    ax3.plot(df["Vol/SMA50 Z-Score"])
    ax3.axhline(y=2, linestyle="dotted", label="Expansion", color="red")
    ax3.axhline(y=0, linestyle="dotted", color="black")
    ax3.axhline(y=-2, linestyle="dotted", label="Contraction", color="green")

    # Set the y label of the third subplot
    ax3.set_ylabel("Vol/SMA50 Z-Score")

    # Plot the z-score of the product of TR/ATR ratio and volume SMA 50 ratio
    ax4.plot(df["TR/ATR * Vol/SMA50 Z-Score"])
    ax4.axhline(y=2, linestyle="dotted", label="Expansion", color="red")
    ax4.axhline(y=0, linestyle="dotted", color="black")
    ax4.axhline(y=-2, linestyle="dotted", label="Contraction", color="green")

    # Set the y label of the fourth subplot
    ax4.set_ylabel("Combined Z-Score")

    # Set the x label
    plt.xlabel("Date")

    # Set the title
    plt.suptitle(f"Volatility of {stock}")

    # Combine legends from all subplots and place them in the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"volatility{stock}.png")
        plt.savefig(filename, dpi=300)    

    # Show the plot
    plt.show()

def plot_FTD_DD(stock, df, multiple=False, show=252*2, save=False):
    """
    Plot Follow-Through Days (FTDs) and Distribution Days (DDs) for a stock.

    Parameters:
    - stock (str): The ticker symbol of the stock to be visualized.
    - df (DataFrame): A pandas DataFrame containing stock price data.
    - multiple (bool, optional): Whether to plot multiple FTDs and DDs. Default is False.
    - show (int, optional): The number of most recent data points to display. Default is 504 (2 years of trading days).
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Add technical indicators to the DataFrame
    df = add_indicator(df)
    
    # Filter the DataFrame to show only the most recent data points
    df = df[- show:]
    
    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the closing price
    plt.plot(df["Close"])

    # Plot the FTDs
    plt.scatter(df.index[df["FTD"]], df["Close"][df["FTD"]], marker="x", color="green")

    # Plot the DDs
    plt.scatter(df.index[df["DD"]], df["Close"][df["DD"]], marker="x", color="red")
    
    if multiple:
        # Plot if there are at least four FTDs over the past month
        plt.scatter(df.index[df["Multiple FTDs"]], df["Close"][df["Multiple FTDs"]] - 10, marker="d", color="green")
        
        # Plot if there are at least four DDs over the past month
        plt.scatter(df.index[df["Multiple DDs"]], df["Close"][df["Multiple DDs"]] + 10, marker="d", color="red")

    # Set the x limit
    plt.xlim(df.index[0], df.index[-1])

    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Price")

    # Set the title
    plt.title(f"Follow-through days and distribution days for {stock}")

    # Set the legend
    plt.legend(["Close", "FTD", "DD", "Multiple FTDs", "Multiple DDs"])

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"FTDDD{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_market_breadth(index_name, index_df, stocks, periods=[20, 50, 200], show=120, save=False):
    """
    Plot market breadth indicators including candlestick prices, percentage of stocks above SMAs, and the Accumulation/Distribution (AD) line.

    Parameters:
    - index_name (str): The name of the market index being analysed.
    - index_df (DataFrame): A pandas DataFrame containing index price data with columns for 'Open', 'Close', 'High', 'Low', and 'AD'.
    - stocks (list): A list of stocks in the index for calculating market breadth.
    - periods (list, optional): A list of periods for calculating Simple Moving Averages (SMAs). Default is [20, 50, 200].
    - show (int, optional): The number of most recent data points to display. Default is 120.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Add technical indicators to the DataFrame
    df = add_indicator(index_df)

    # Filter the DataFrame to show only the most recent data points
    index_df = index_df[- show:]

    # Define the widths for candlestick and stick bars
    width_candle = 1
    width_stick = 0.2

    # Separate the DataFrame into up and down candlesticks
    up_df = index_df[index_df["Close"] > index_df["Open"]]
    down_df = index_df[index_df["Close"] <= index_df["Open"]]
    colour_up = "green"
    colour_down = "red"

    # Create a figure with three subplots: one for the closing price, one for the SMAs, and one for the AD line
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the up prices on the first subplot
    ax1.bar(up_df.index, up_df["Close"] - up_df["Open"], width_candle, bottom=up_df["Open"], color=colour_up)
    ax1.bar(up_df.index, up_df["High"] - up_df["Close"], width_stick, bottom=up_df["Close"], color=colour_up)
    ax1.bar(up_df.index, up_df["Low"] - up_df["Open"], width_stick, bottom=up_df["Open"], color=colour_up)

    # Plot the down prices on the first subplot
    ax1.bar(down_df.index, down_df["Close"] - down_df["Open"], width_candle, bottom=down_df["Open"], color=colour_down)
    ax1.bar(down_df.index, down_df["High"] - down_df["Open"], width_stick, bottom=down_df["Open"], color=colour_down)
    ax1.bar(down_df.index, down_df["Low"] - down_df["Close"], width_stick, bottom=down_df["Close"], color=colour_down)
    
    # Set the label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    buffer = relativedelta(days=1)
    ax1.set_xlim(index_df.index[0] - buffer, index_df.index[-1] + buffer)

    # Plot the % of stocks above the SMAs on the second subplot
    for i in periods:
        ax2.plot(index_df.index, index_df[f"Above SMA {str(i)}"] / len(stocks) * 100, label=f"% above SMA {str(i)}")

    # Set the y label of the second subplot
    ax2.set_ylabel(f"% above SMA")

    # Plot the AD line on the third subplot
    index_df["AD"] = index_df["AD"] - index_df["AD"].iloc[0]
    ax3.plot(index_df.index, index_df["AD"], color="red")

    # Set the y label of the third subplot
    ax3.set_ylabel("AD line")

    # Set the x label
    plt.xlabel("Date")

    # Set the title
    plt.suptitle(f"Market breadth of {index_name}")

    # Combine legends from all subplots and place them in the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"marketbreadth{index_name}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_stocks(stocks, current_date, col="Close", show=120, save=False):
    """
    Plot the scaled closing price history of multiple stocks for comparison.

    Parameters:
    - stocks (list): A list of stock ticker symbols to be compared.
    - current_date (str): The current date used to filter stock data.
    - col (str, optional): The column name to be plotted. Default is "Close".
    - show (int, optional): The number of most recent data points to display. Default is 120.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Merge the DataFrames of the specified stocks into a single DataFrame
    df_merged = merge_stocks(stocks, current_date)

    # Filter the DataFrame to show only the most recent data points
    df_merged = df_merged[- show:]

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the closing price history of each stock
    for stock in stocks:
        close_first = df_merged[f"{col} ({stock})"].iloc[0]
        plt.plot(100 / close_first * df_merged[f"{col} ({stock})"], label=f"{stock} (scaled)")

    # Set the x limit
    plt.xlim(df_merged.index[0], df_merged.index[-1])

    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Price")

    # Set the legend
    plt.legend()

    # Set the title
    plt.title(f"Closing price history for {', '.join(stocks)}")
    
    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"close{', '.join(stocks)}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_JdK(sector, sector_dict, index_df, show=120, save=False):
    """
    Plot the JdK RS-Ratio and Momentum for a specified sector.

    Parameters:
    - sector (str): The sector for which the JdK RS-Ratio and Momentum are plotted.
    - sector_dict (dict): A dictionary mapping sector abbreviations to their full names.
    - index_df (DataFrame): A pandas DataFrame containing index data with columns for JdK RS-Ratio and Momentum.
    - show (int, optional): The number of most recent data points to display. Default is 120.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Filter the DataFrame to show only the most recent data points
    index_df = index_df[- show:]

    # Extract the relevant columns for the selected sector
    cols = [f"{sector} JdK RS-Ratio", f"{sector} JdK RS-Momentum"]

    # Create a figure with two subplots: one for the JdK RS-Ratio and one for JdK RS-Momentum
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [1, 1]}, sharex=True)

    # Plot the JdK RS-Ratio on the top subplot
    ax1.plot(index_df[cols[0]], label=cols[0])
    ax1.axhline(y=100, linestyle="dotted", color="black")

    # Set the y label of the top subplot
    ax1.set_ylabel("JdK RS-Ratio")

    # Set the x limit of the top subplot
    ax1.set_xlim(index_df.index[- show], index_df.index[-1])

    # Set the legend of the top subplot
    ax1.legend()

    # Plot the JdK RS-Momentum on the bottom subplot
    ax2.plot(index_df[cols[1]], label=cols[1])

    # Add a horizontal dotted line at 100 to the bottom subplot
    ax2.axhline(y=100, linestyle="dotted", color="black")

    # Set the y label of the bottom subplot
    ax2.set_ylabel("JdK RS-Momentum")

    # Set the legend of the bottom subplot
    ax2.legend()

    # Set the x label
    plt.xlabel("Date")

    # Set the title
    plt.suptitle(f"JdK RS-ratio and momentum for {sector_dict[sector]}")

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"JdKRS{sector}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_rrg(items, item_dict, index_df, region, type, points=8, interval=5, save=False):
    """
    Plot the Relative Rotation Graph (RRG) for specified sectors or indices.

    Parameters:
    - items (list): A list of sector or index symbols to be analysed.
    - item_dict (dict): A dictionary mapping sector or index abbreviations to their full names.
    - index_df (DataFrame): A pandas DataFrame containing index data with JdK RS-Ratio and Momentum.
    - region (str): Specifies the region of the sectors or indices ("HK" or "US").
    - type (str): Specifies whether to plot sectors or indices ("sector" or "index").
    - points (int, optional): The number of points to plot for each sector/index. Default is 8.
    - interval (int, optional): The interval between points in the data. Default is 5.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Define the colours for different items
    colours = plt.cm.tab20(range(20)).tolist()

    # Create a figure and axis for the plot
    fig, ax1 = plt.subplots(figsize=(8, 6))

    # Initialise lists to store the x and y coordinates for the points
    xs = []
    ys = []

    # Loop through each item to plot JdK RS-Ratio and Momentum
    for i, item in enumerate(items):
        if item == "^GSPC":
            continue
        if item == "GC=F":
            colour = "Gold"
        else:
            colour = colours[i]
        label = item_dict[item]

        # Scatter points for the specified number of points
        for point in range(points):
            # Get the JdK RS-Ratio and Momentum values at specified intervals
            x = index_df[f"{item} JdK RS-Ratio"].iloc[-1 - point * interval]
            y = index_df[f"{item} JdK RS-Momentum"].iloc[-1 - point * interval]
            xs.append(x)
            ys.append(y)

            # Scatter the first and last points with different markers
            if point == 0:
                ax1.scatter(x, y, color=colour, s=50, marker=">", label=label)
            elif point == points - 1:
                ax1.scatter(x, y, color=colour, s=50, marker="o")
            else:
                ax1.scatter(x, y, color=colour, s=10, marker="o")

            # Connect the points with dashed lines
            if point > 0:
                ax1.plot([x_prev, x], [y_prev, y], color=colour, linestyle="--")
            x_prev, y_prev = x, y  # Update previous point

    # Set the labels for the axes
    ax1.set_xlabel("JdK RS-Ratio")
    ax1.set_ylabel("JdK RS-Momentum")

    # Set the title of the plot using the appropriate plural
    plural_map = {"sector": "sectors", "index": "indices"}
    ax1.set_title(f"Relative rotation graph of {region} {plural_map.get(type, type + 's')}")

    # Draw horizontal and vertical lines at x = y = 100
    ax1.axhline(y=100, linestyle="--", color="black")
    ax1.axvline(x=100, linestyle="--", color="black")

    # Set the limits for the axes
    buffer = 0.25
    x_min, x_max = min(xs) - buffer, max(xs) + buffer
    y_min, y_max = min(ys) - buffer, max(ys) + buffer
    ax1.set_xlim(x_min, x_max)
    ax1.set_ylim(y_min, y_max)

    # Colour each quadrant of the graph
    ax1.fill_between([100, x_max], [100, 100], [y_max, y_max], color="green", alpha=0.1)
    ax1.fill_between([x_min, 100], [100, 100], [y_max, y_max], color="blue", alpha=0.1)
    ax1.fill_between([100, x_max], [y_min, y_min], [100, 100], color="gold", alpha=0.1)
    ax1.fill_between([x_min, 100], [y_min, y_min], [100, 100], color="red", alpha=0.1)

    # Add text labels in each quadrant
    ax1.text(x_max, y_max, "Leading", color="green", ha="right", va="top", weight="bold")
    ax1.text(x_min, y_max, "Improving", color="blue", ha="left", va="top", weight="bold")
    ax1.text(x_max, y_min, "Weakening", color="gold", ha="right", va="bottom", weight="bold")
    ax1.text(x_min, y_min, "Lagging", color="red", ha="left", va="bottom", weight="bold")

    # Set the legend outside of the plot area
    ax1.legend(bbox_to_anchor=(1.04, 1), borderaxespad=0, fontsize=8)

    # Adjust the spacing between subplots
    plt.tight_layout()
    
    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"{region.lower()}{type}rrg.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_sector_industry_selected(end_date, index_name, index_dict, period=252, RS=90, industry_limit=20, all_stocks=True, save=False):
    """
    Plot the sector and industry distribution of selected stocks in two pie charts.

    Parameters:
    - end_date (str): The end date for the data in 'YYYY-MM-DD' format.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - period (int, optional): The lookback period for stock selection. Default is 252.
    - RS (int, optional): Relative strength threshold. Default is 90.
    - industry_limit (int, optional): The maximum number of industries to display. Default is 20.
    - all_stocks (bool): Flag indicating whether to include all stocks from the market.
    - save (bool, optional): Whether to save the plots as PNG files. Default is False.

    Returns:
    - None: Generates two pie charts for sector and industry distributions.
    """

    # Define the result folder and the figure folder
    result_folder = "Result"
    figure_folder = os.path.join(result_folder, "Figure")

    # Get the infix for file naming
    infix = get_infix(index_name, index_dict, all_stocks)
    
    # Format the end date for use in filenames
    end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%y")

    # Define the folder path where results will be stored
    folder_path = os.path.join(result_folder, f"{end_date_fmt}")

    # Define the filename for the Excel file containing screened stocks
    filename = os.path.join(folder_path, f"{infix}stock_{end_date_fmt}period{period}RS{RS}.xlsx")
    
    # Read the data of the screened stocks from the Excel file
    try:
        df = pd.read_excel(filename)
    except FileNotFoundError as e:
        print(f"File not found: {filename}. Please run the stock screening function first.")
        return

    # Plot sector distribution
    sector_counts = df["Sector"].value_counts()
    colors = plt.cm.tab20(range(20)).tolist()

    plt.figure(figsize=(8, 6))
    plt.pie(sector_counts, labels=sector_counts.index, 
            autopct=lambda x: f'{int(round(x * sum(sector_counts) / 100))}', colors=colors)
    plt.title("Sector distribution of selected stocks")
    plt.axis("equal")
    plt.tight_layout()

    # Save the plot
    if save:
        sector_filename = os.path.join(figure_folder, f"{infix}sectorselected.png")
        plt.savefig(sector_filename, dpi=300, bbox_inches="tight")

    # Show the plot
    plt.show()

    # Plot industry distribution limited to the industry_limit most important industries
    industry_counts = df["Industry"].value_counts().iloc[:industry_limit]

    plt.figure(figsize=(8, 6))
    plt.pie(industry_counts, labels=industry_counts.index, 
            autopct=lambda x: f'{int(round(x * sum(industry_counts) / 100))}', colors=colors)
    plt.title(f"Industry distribution of selected stocks")
    plt.axis("equal")
    plt.tight_layout()

    # Save the plot
    if save:
        industry_filename = os.path.join(figure_folder, f"{infix}industryselected.png")
        plt.savefig(industry_filename, dpi=300, bbox_inches="tight")

    # Show the plot
    plt.show()

def plot_corr_ta(stock, df, cols=["Open", "High", "Low", "Close", "Volume", "MACD", "RSI", "RMI", "CCI", "ADX", "MFI", "OBOS"], save=False):
    """
    Plot the correlation matrix of specified technical indicators for a given stock.

    Parameters:
    - stock (str): The name of the stock being analyzed.
    - df (DataFrame): A pandas DataFrame containing the stock's technical indicators.
    - cols (list, optional): The list of columns (technical indicators) to include in the correlation matrix. Default includes common indicators.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Extract the relevant data and drop any rows with missing values
    data = df.copy().dropna()[cols].values

    # Calculate the correlation matrix for the selected columns
    correlation_matrix = np.corrcoef(data, rowvar=False)

    # Create a heatmap to visualize the correlation matrix
    sns.heatmap(correlation_matrix, annot=True, fmt=".2f", xticklabels=cols, yticklabels=cols)

    # Set the title
    plt.title(f"Correlation matrix of techinical indicators of {stock}")

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"corrta{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_corr_stocks(stocks, dfs, end_date, years, save=False):
    """
    Plot the correlation matrix of closing prices for a list of stocks over a specified period.

    Parameters:
    - stocks (list): A list of stock ticker symbols to analyse.
    - dfs (list): A list of DataFrames containing stock price data.
    - end_date (str): The end date for the price data in "YYYY-MM-DD" format.
    - years (int): The number of years of data to consider for the correlation analysis.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates a plot and displays it.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Get the price data of the specified stocks
    df_merged = merge_stocks(stocks, dfs, end_date)

    # Filter the DataFrame to show only the most recent data points based on the specified number of years
    df_merged = df_merged[- int(years * 252):]
    dfs_close = [df_merged[f"Close ({stock})"].values for stock in stocks]

    # Extract the closing prices for each stock
    data = np.array(dfs_close)

    # Calculate the correlation matrix from the closing prices
    correlation_matrix = np.corrcoef(data)
    
    # Create a heatmap to visualize the correlation matrix
    tick_labels = stocks
    sns.heatmap(correlation_matrix, annot=True, fmt=".2f", xticklabels=tick_labels, yticklabels=tick_labels)

    # Set the title
    if years == 1:
        plt.title(f"Correlation matrix in the past {years} year")
    else:
        plt.title(f"Correlation matrix in the past {years} years")

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"corr{years}{', '.join(stocks)}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_autocorr(stock, end_date, years, save=False):
    """
    Plot the autocorrelation function for a specified stock over a given period.

    Parameters:
    - stock (str): The ticker symbol of the stock to analyse.
    - end_date (str): The end date for the analysis in 'YYYY-MM-DD' format.
    - years (int): The number of years of historical data to consider for autocorrelation.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function generates and displays a plot of the autocorrelation function.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Calculate the start date based on the end date and the number of years
    start_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(years=years)).strftime("%Y-%m-%d")

    # Retrieve the price data for the specified stock
    df = get_df(stock, end_date)

    # Filter the DataFrame to include only the relevant date range
    df = df[start_date : end_date]

    # Drop rows with NaN values and extract the closing prices
    data = df.dropna()["Close"].values

    # Create a figure
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)

    # Calculate the autocorrelation function with specified lags
    acfs = acf(data, nlags=252*5)

    # Plot the autocorrelation values
    ax.plot(np.arange(len(acfs)), acfs)
    
    # Find the indices of local maxima in the autocorrelation
    maxima_indices = argrelextrema(acfs, np.greater)[0]
    maxima_values = acfs[maxima_indices]

    # Print the local maxima values and their indices
    for index, value in zip(maxima_indices, maxima_values):
        print(f"Index: {index}, Value: {value}")
        
    # Mark the local maxima on the plot
    ax.plot(maxima_indices, maxima_values, "rx", label="Local maxima")

    # Set the x limit
    plt.xlim(0, 252 * years)

    # Set the title
    if years == 1:
        plt.title(f"Autocorrelation function for {stock} in the past {years} year")
    else:
        plt.title(f"Autocorrelation function for {stock} in the past {years} years")

    # Set the legend
    plt.legend()

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"autocorr{years}{stock}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_longshort_rs(merged_df, end_date1, end_date2, stock_star=None):
    """
    Plot a scatter plot comparing short-term and long-term relative strength (RS).

    Parameters:
    - merged_df (DataFrame): DataFrame containing long-term and short-term RS values.
    - end_date1 (str): The start date for the data range.
    - end_date2 (str): The end date for the data range.
    - stock_star (str, optional): The specific stock to highlight in the plot.

    Returns:
    - None: This function displays a scatter plot of long-term RS vs. short-term RS.
    """

    # Create a scatter plot of short-term RS against long-term RS
    plt.figure(figsize=(10, 6))
    plt.scatter(merged_df["Long-term RS"], merged_df["Short-term RS"], color="blue", marker="x")

    # Highlight a specific stock with a star marker
    star = merged_df[merged_df["Stock"] == stock_star]
    if not star.empty:
        plt.scatter(star["Long-term RS"], star["Short-term RS"], color="gold", edgecolor="black", marker="*", s=100, label=stock_star)

    # Plot a red vertical line at long-term RS = 20
    plt.axvline(x=20, color="red", linestyle="--")

    # Calculate the slope and R-squared value for the regression line
    slope, intercept, r_value, _, _ = linregress(merged_df["Long-term RS"], merged_df["Short-term RS"])
    r_squared = r_value**2

    # Create the regression line
    x_values = np.linspace(0, 100, 100)
    y_values = slope * x_values + intercept
    plt.plot(x_values, y_values, color="black", linestyle="--", label=fr"slope$={slope:.2f}$, $R^2={r_squared:.2f}$")

    # Set the axes labels
    plt.xlabel("Long-term RS")
    plt.ylabel("Short-term RS")

    # Set the title
    plt.title(f"Long-term vs Short-term RS ({end_date1} to {end_date2})")

    # Set the legend
    plt.legend()

    # Adjust the spacing
    plt.tight_layout()

    # Show the plot
    plt.show()

def plot_compare_longshort_rs(index_df, index_name, rs_slopes, r_squareds, end_dates, end_dates2, save=False):
    """
    Plot the comparison of closing prices, RS slopes, R-squared values, and combined Z-scores.

    Parameters:
    - index_df (DataFrame): DataFrame containing index data.
    - index_name (str): The name of the index being analysed.
    - rs_slopes (list): List of RS slope values.
    - r_squareds (list): List of R-squared values corresponding to the RS slopes.
    - end_dates (list): List of end dates for the RS calculations.
    - end_dates2 (list): List of dates corresponding to the RS slopes and R-squared values.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function displays a series of plots for the comparison.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Filter the index DataFrame for the specified date range
    index_df = index_df.loc[(index_df.index >= end_dates[0]) & (index_df.index <= end_dates[-1])]

    # Create a figure with four subplots: one for the closing price, one for the RS slope, one for the R-squared values, and one for the z-score of their product
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 0.5, 0.5, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(index_df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    ax1.set_xlim(index_df.index[0], index_df.index[-1])

    # Create a DataFrame for RS slope and plot it on the second subplot
    rs_slope_df = pd.DataFrame({"RS Slope": rs_slopes}, index=pd.to_datetime(end_dates2))
    ax2.plot(rs_slope_df["RS Slope"], color="orange")

    # Add a horizontal line at y = 0
    ax2.axhline(y=0, color="black", linestyle="--", linewidth=0.5)

    # Set the y label for the second subplot
    ax2.set_ylabel("RS slope")

    # Create a dataframe for R-squared values and plot it on the third subplot
    r_squareds_df = pd.DataFrame({"R^2": r_squareds}, index=pd.to_datetime(end_dates2))
    ax3.plot(r_squareds_df, color="orange")

    # Set the y label for the third subplot
    ax3.set_ylabel(r"$R^2$")

    # Calculate the z-scores of the product of RS slope and R-squared
    rs_slopes_r2 = np.array(rs_slopes) * r_squareds
    rs_slopes_r2_mean = np.mean(rs_slopes_r2)
    rs_slopes_r2_std = np.std(rs_slopes_r2)
    z_scores = (rs_slopes_r2 - rs_slopes_r2_mean) / rs_slopes_r2_std

    # Create a DataFrame for the z-scores and plot them on the fourth subplot
    z_scores_df = pd.DataFrame({"Z-Score": z_scores}, index=pd.to_datetime(end_dates2))
    ax4.plot(z_scores_df, color="orange")

    # Add a horizontal line at y = 0
    ax4.axhline(y=0, color="black", linestyle="--", linewidth=0.5)

    # Add a red dotted line at y = 2
    ax4.axhline(y=2, color="red", linestyle="dotted")

    # Add a red dotted line at y = -2
    ax4.axhline(y=-2, color="red", linestyle="dotted")

    # Set the y label for the fourth subplot
    ax4.set_ylabel("Combined Z-Score")

    # Ensure y-axis ticks are integers
    ax4.yaxis.set_major_locator(MaxNLocator(integer=True))

    # Set the x label
    plt.xlabel("Date")

    # Set the title
    plt.suptitle(f"RS slope for {index_name}")

    # Set the legend
    ax1.legend()

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"rsslope{index_name}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_volume5m(stock, volume5m_data, date, sma_period=50, save=False):
    """
    Plot the 5-minute intraday volume of a specified stock on a given date.

    Parameters:
    - stock (str): The ticker symbol of the stock to analyze.
    - volume5m_data (dict): A dictionary containing volume data of the stock.
    - date (str): The specific date for which to plot the volume data.
    - sma_period (int, optional): The period for the Simple Moving Average (SMA). Default is 50.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.

    Returns:
    - None: This function displays a plot of the 5-minute intraday volume and related metrics.
    """

    # Define the result folder
    result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Check if the volume data is provided
    if volume5m_data is None:
        return

    # Extract necessary data from the volume5m_data dictionary 
    df_date = volume5m_data["df_date"]
    df0_hours = volume5m_data["df0_hours"]
    volume5m_sma_df0 = volume5m_data["volume5m_sma_df0"]
    volume5m_std_df0 = volume5m_data["volume5m_std_df0"]
    sma_hours = volume5m_data["sma_hours"]

    # Create a figure with three subplots: one for the 5-min volume, one for the 5-min volume SMA 50 ratio, and one for the z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)
    
    # Plot the 5-min volume on the first subplot
    ax1.bar(df0_hours, df_date["Volume"], width=5/60/2, label="5-min Volume", align="edge", alpha=0.7)

    # Plot the 5-min volume SMA 50 on the first subplot
    ax1.plot(sma_hours, volume5m_sma_df0.values, label=f"SMA {sma_period}", color="purple")

    # Calculate the ratio of the first 5-min volume to its SMA
    ratio = df_date["Volume"].iloc[0] / volume5m_sma_df0.values[0]

    # Annotate the ratio next to the first volume bar
    ax1.text(df0_hours.iloc[0] + 0.05, df_date["Volume"].iloc[0], f"First 5-min ratio: {ratio:.2f}", fontsize=12)

    # Set the y label of the first subplot
    ax1.set_ylabel("Volume")

    # Set the x limit of the first subplot
    ax1.set_xlim(0, df0_hours.iloc[-1] + 5/60/2)

    # Calculate the ratio of 5-min volume to its SMA for the second subplot
    ratios = df_date["Volume"] / volume5m_sma_df0.values

    # Plot the 5-min volume SMA 50 ratio on the second subplot
    ax2.plot(df0_hours, ratios)

    # Set the y label of the second subplot
    ax2.set_ylabel("Vol/SMA 50")

    # Calculate the z-scores for the volume data
    volume5m_zscores = (df_date["Volume"] - volume5m_sma_df0.values) / volume5m_std_df0.values

    # Plot the z-scores on the third subplot
    ax3.plot(df0_hours, volume5m_zscores)
    ax3.axhline(y=2, linestyle="dotted", color="red")
    ax3.axhline(y=-2, linestyle="dotted", color="red")

    # Set the y label of the third subplot
    ax3.set_ylabel("Vol/SMA50 Z-Score")

    # Set the x label
    plt.xlabel("Hour")

    # Set the legend
    ax1.legend()

    # Set the title
    plt.suptitle(f"5-min Intraday Volume of {stock} on {date}")
    
    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, f"volume5m{stock}{date}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

def plot_hist(arr, xlabel, title, benchmark=None, filename=None, save=False, backtest=False):
    """
    Plot the distribution of a specified column from a DataFrame using a histogram and overlays a Gaussian curve.

    Parameters:
    - arr (array-like): The numerical data to plot, provided as a list or NumPy array.
    - xlabel (str): The label for the x-axis.
    - title (str): The title of the plot.
    - benchmark (float, optional): A benchmark value to be indicated on the plot. Default is None.
    - filename (str, optional): The name of the file to save the figure. Default is None (no save).
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.
    - backtest (bool): Flag to indicate if backtesting is being performed. Default is False.

    Returns:
    - None: This function generates a histogram with an overlaid Gaussian curve and displays it.
    """

    # Set the result folder based on backtest flag
    if backtest:
        result_folder = "Backtest"
    else:
        result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot histogram of the data
    counts, bins, _ = plt.hist(arr, bins=100, color="blue", edgecolor="black", alpha=0.7)

    # Fit Gaussian curve to the data
    mean = np.mean(arr)
    sd = np.std(arr)
    xmin = np.min(arr)
    xmax = np.max(arr)
    x = np.linspace(xmin, xmax, 10000)
    p = norm.pdf(x, mean, sd)

    # Scale the Gaussian curve to match histogram counts
    bin_width = bins[1] - bins[0]
    scaling_factor = len(arr) * bin_width
    p = p * scaling_factor

    # Plot the scaled Gaussian curve
    plt.plot(x, p, color="red")

    # Add a dotted line for the mean value
    plt.axvline(mean, color="black", linestyle="dotted")

    # Add a dotted line for the benchmark if provided
    if benchmark is not None:
        plt.axvline(benchmark, color="blue", linestyle="dotted")
    
    # Calculate the range for standard deviation lines
    zscore_min = np.ceil((mean - xmin) / sd)
    zscore_max = np.ceil((xmax - mean) / sd)

    # Add dotted lines for standard deviations
    for i in range(1, int(zscore_min)):
        plt.axvline(mean - i * sd, color="red", linestyle="dotted")
    for i in range(1, int(zscore_max)):
        plt.axvline(mean + i * sd, color="red", linestyle="dotted")

    # Calculate the skewness of the data
    skew_value = skew(arr)

    # Calculate the kurtosis of the data
    kurt_value = kurtosis(arr)

    # Add mean and kurtosis to the plot
    if benchmark is not None:
        text = f"Mean: {mean:.4f}\nSkewness: {skew_value:.2f}\nKurtosis: {kurt_value:.2f}\nBenchmark: {benchmark:.4f}"
    else:
        text = f"Mean: {mean:.4f}\nSkewness: {skew_value:.2f}\nKurtosis: {kurt_value:.2f}"
        
    plt.text(0.975, 0.975, text, ha="right", va="top", transform=plt.gca().transAxes, bbox={"facecolor": "white", "alpha": 0.8, "pad": 5})

    # Set the x limit
    plt.xlim(xmin, xmax)

    # Set the labels
    plt.xlabel(f"{xlabel}")
    plt.ylabel("Count")

    # Set the title
    plt.title(f"{title}")

    # Set y-ticks to display only integer values
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, filename)
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()