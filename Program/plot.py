# Imports
import datetime as dt
from dateutil.relativedelta import relativedelta
from helper_functions import get_df, get_infix, merge_stocks
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import os
import pandas as pd
from scipy.signal import argrelextrema
from scipy.stats import norm, kurtosis, linregress
import seaborn as sns
from statsmodels.tsa.stattools import acf
from technicals import *

# Visualize the closing price history
def plot_close(stock, df, show=120, MVP_VCP=True, local_extrema=False, local_extrema_period=5, FTD_DD=False, save=False):
    # Add technical indicators to the data
    add_indicator(df)

    # Find the local extrema
    df = get_local_extrema(df, period=local_extrema_period)

    # Calculate the retracement
    local_min1, local_max1, retracement = calculate_retracement(df)

    # Calculate the percentage of retracement
    retracement_pct = round(retracement * 100, 2) if retracement is not None else None

    # Filter the data
    df = df[- show:]

    # Define the widths
    width_candle = 1
    width_stick = 0.2

    # Separate the dataframe into green and red candlesticks
    up_df = df[df["Close"] >= df["Open"]]
    down_df = df[df["Close"] <= df["Open"]]
    colour_up = "green"
    colour_down = "red"

    # Create a figure with two subplots, one for the closing price and one for the volume
    if stock == "^VIX":
        fig, ax1 = plt.subplots(1, 1, figsize=(10, 6))
    else:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [5, 1]}, sharex=True)
        
    # Plot the up prices on the top subplot
    ax1.bar(up_df.index, up_df["Close"] - up_df["Open"], width_candle, bottom=up_df["Open"], color=colour_up)
    ax1.bar(up_df.index, up_df["High"] - up_df["Close"], width_stick, bottom=up_df["Close"], color=colour_up)
    ax1.bar(up_df.index, up_df["Low"] - up_df["Open"], width_stick, bottom=up_df["Open"], color=colour_up)

    # Plot the down prices on the top subplot
    ax1.bar(down_df.index, down_df["Close"] - down_df["Open"], width_candle, bottom=down_df["Open"], color=colour_down)
    ax1.bar(down_df.index, down_df["High"] - down_df["Open"], width_stick, bottom=down_df["Open"], color=colour_down)
    ax1.bar(down_df.index, down_df["Low"] - down_df["Close"], width_stick, bottom=down_df["Close"], color=colour_down)

    # Plot the MVP and VCP conditions on the top subplot
    if MVP_VCP:
        ax1.scatter(df.index[df["MVP"] == "M"], df["Close"][df["MVP"] == "M"], marker="^", edgecolor="black", facecolors="grey", label="M")
        ax1.scatter(df.index[df["MVP"] == "MP"], df["Close"][df["MVP"] == "MP"], marker="^", edgecolor="black", facecolors="yellow", label="MP")
        ax1.scatter(df.index[df["MVP"] == "MV"], df["Close"][df["MVP"] == "MV"], marker="^", edgecolor="black", facecolors="blue", label="MV")
        ax1.scatter(df.index[df["MVP"] == "MVP"], df["Close"][df["MVP"] == "MVP"], marker="^", edgecolor="black", facecolors="green", label="MVP")
        ax1.scatter(df.index[df["VCP"] == True], df["Close"][df["VCP"] == True], marker=">", edgecolor="black", facecolors="orange", label="VCP")

    # Plot FTDs and DDs on the top subplot
    if FTD_DD:
        ax1.scatter(df.index[df["FTD"]], df["Low"][df["FTD"]] * 0.98, marker="x", color="green", label="FTD")
        ax1.scatter(df.index[df["DD"]], df["Low"][df["DD"]] * 0.98, marker="x", color="red", label="DD")

    # Scatter points for local minima and maxima
    if local_extrema:
        ax1.scatter(df.index[df["Local Min"]], df["Low"][df["Local Min"]], label="Local extrema", marker="x", color="black")
        ax1.scatter(df.index[df["Local Max"]], df["High"][df["Local Max"]], marker="x", color="black")

        # Add retracement percentage as text on the plot
        if retracement_pct is not None:
            ax1.text(0.4, 0.95, f"Retracement: {retracement_pct}%\nRecent min: {round(local_min1, 2)}\nRecent max: {round(local_max1, 2)}", 
                    transform=ax1.transAxes, fontsize=10, ha="left", va="top", bbox=dict(facecolor="white", alpha=0.5))
            
    # Plot the SMAs on the top subplot
    periods = [5, 20, 50, 200]
    for i in periods:
        ax1.plot(df[f"SMA {str(i)}"], label=f"SMA {str(i)}")

    # Set the y label of the top subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the top subplot
    buffer = relativedelta(days=1)
    ax1.set_xlim(df.index[0] - buffer, df.index[-1] + buffer)

    if stock != "^VIX":
        # Plot the volume on the bottom subplot
        ax2.bar(up_df.index, up_df["Volume"], label="Volume (+)", color=colour_up)
        ax2.bar(down_df.index, down_df["Volume"], label="Volume (-)", color=colour_down)

        # Plot the volume SMA 50 on the bottom subplot
        ax2.plot(df["Volume SMA 50"], label="Volume SMA 50", color="purple")

        # Plot the follow-through days (FTDs) and distribution days (DDs)

        # Set the label of the bottom subplot
        ax2.set_ylabel("Volume")

        # Set the x label
        plt.xlabel("Date")

        # Combine the legends and place them at the top subplot
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
        plt.savefig(f"Result/Figure/close{stock}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the MACD indicator
def plot_MACD(stock, df, period=252, show=252, save=False):
    # Add technical indicators to the data
    add_indicator(df)

    # Calculate the z-score of MACD bar
    df = calculate_ZScore(df, ["MACD Bar"], period)

    # Filter the data
    df = df[- show:]

    # Separate the dataframe into green and red MACD bars
    up_df = df[df["MACD Bar"] > 0]
    down_df = df[df["MACD Bar"] <= 0]
    colour_up = "green"
    colour_down = "red"

    # Create a figure with three subplots, one for the closing price, one for the MACD indicator, and one for the MACD bar z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    buffer = relativedelta(days=1)
    ax1.set_xlim(df.index[0] - buffer, df.index[-1] + buffer)

    # Plot the MACD indicator on the second subplot
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

    # Combine the legends and place them at the top subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/MACD{stock}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the MFI/RSI indicator
def plot_MFI_RSI(stock, df, period=252, show=252, save=False):
    # Add technical indicators to the data
    add_indicator(df)

    # Calculate the z-scores of MFI and RSI
    df = calculate_ZScore(df, ["MFI", "RSI"], period)

    # Filter the data
    df = df[- show:]

    # Create a figure with three subplots, one for the closing price, one for the MFI/RSI indicator, and one for the MFI/RSI z-score
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

    # Combine the legends and place them at the top subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/MFIRSI{stock}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the ADX indicator
def plot_ADX(stock, df, period=252, show=252, save=False):
    # Add technical indicators to the data
    add_indicator(df)

    # Calculate the Z-score of ADX
    df = calculate_ZScore(df, "ADX", period)

    # Filter the data
    df = df[- show:]

    # Create a figure with three subplots, one for the closing price, one for the ADX indicator, and one for the ADX z-score
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

    # Combine the legends and place them at the top subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/ADX{stock}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the volatility
def plot_volatility(stock, df, period=252, show=120, save=False):
    # Add technical indicators to the data
    add_indicator(df)

    # Calculate the TR/ATR ratio
    df["TR/ATR"] = df["TR"] / df["ATR"]

    # Calculate the volume SMA 50 ratio
    df["Vol/SMA50"] = df["Volume"] / df["Volume SMA 50"]

    # Calculate the product of TR/ATR ratio and volume SMA 50 ratio
    df["TR/ATR * Vol/SMA50"] = df["TR/ATR"] * df["Vol/SMA50"]

    # Calculate the z-scores of TR/ATR ratio, volume SMA 50 ratio and their product
    df = calculate_ZScore(df, ["TR/ATR", "Vol/SMA50", "TR/ATR * Vol/SMA50"], period)

    # Filter the data
    df = df[- show:]

    # Create a figure with four subplots, one for the price, one for the TR/ATR z-score, one for the volume SMA 50 ratio z-score, and one for the combined z-score
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

    # Combine the legends and place them at the top subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/volatility{stock}.png", dpi=300)    

    # Show the plot
    plt.show()

# Plot the follow-through days (FTDs) and distribution days (DDs)
def plot_FTD_DD(stock, df, show=252*2, save=False):
    # Add technical indicators to the data
    add_indicator(df)
    
    # Filter the data
    df = df[- show:]
    
    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the closing price
    plt.plot(df["Close"])

    # Plot the FTDs
    plt.scatter(df.index[df["FTD"]], df["Close"][df["FTD"]], marker="x", color="green")

    # Plot the DDs
    plt.scatter(df.index[df["DD"]], df["Close"][df["DD"]], marker="x", color="red")
    
    # Plot if there are at least four follow-through days over the past month
    plt.scatter(df.index[df["Multiple FTDs"]], df["Close"][df["Multiple FTDs"]] - 10, marker="d", color="green")
    
    # Plot if there are at least four distribution days over the past month
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
        plt.savefig(f"Result/Figure/FTDDD{stock}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the market breadth indicators
def plot_market_breadth(index_name, index_df, stocks, periods=[20, 50, 200], show=120, save=False):
    # Add technical indicators to the data
    add_indicator(index_df)

    # Filter the data
    index_df = index_df[- show:]

    # Define the widths
    width_candle = 1
    width_stick = 0.2

    # Separate the dataframe into green and red candlesticks
    up_df = index_df[index_df["Close"] > index_df["Open"]]
    down_df = index_df[index_df["Close"] <= index_df["Open"]]
    colour_up = "green"
    colour_down = "red"

    # Create a figure with three subplots, one for the closing price, one for the SMAs, and one for the AD line
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

    # Combine the legends and place them at the first subplot
    handles, labels = ax1.get_legend_handles_labels()
    handles += ax2.get_legend_handles_labels()[0]
    labels += ax2.get_legend_handles_labels()[1]
    ax1.legend(handles, labels)

    # Adjust the spacing between subplots
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/marketbreadth{index_name}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot to compare the closing price history of stocks
def plot_stocks(stocks, current_date, column="Close", show=120, save=False):
    # Merge dataframes of stocks
    df_merged = merge_stocks(stocks, current_date)

    # Filter the data
    df_merged = df_merged[- show:]

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the closing price history of the stocks
    for stock in stocks:
        close_first = df_merged[f"{column} ({stock})"].iloc[0]
        plt.plot(100 / close_first * df_merged[f"{column} ({stock})"], label=f"{stock} (scaled)")

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
        plt.savefig("Result/Figure/closestocks.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the JdK RS-Ratio and Momentum of a sector
def plot_JdK(sector, sector_dict, index_df, show=120, save=False):
    # Filter the data
    index_df = index_df[- show:]

    # Extract the columns
    columns = [f"{sector} JdK RS-Ratio", f"{sector} JdK RS-Momentum"]

    # Create a figure with two subplots, one for the JdK RS-Ratio and one for JdK RS-Momentum
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [1, 1]}, sharex=True)

    # Plot the JdK RS-Ratio on the top subplot
    ax1.plot(index_df[columns[0]], label=columns[0])
    ax1.axhline(y=100, linestyle="dotted", color="black")

    # Set the y label of the top subplot
    ax1.set_ylabel("JdK RS-Ratio")

    # Set the x limit of the top subplot
    ax1.set_xlim(index_df.index[- show], index_df.index[-1])

    # Set the legend of the top subplot
    ax1.legend()

    # Plot the JdK RS-Momentum on the bottom subplot
    ax2.plot(index_df[columns[1]], label=columns[1])

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
        plt.savefig(f"Result/Figure/JdKRS{sector}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the relative rotation graph
def plot_rrg(sectors, sector_dict, index_df, type, points=8, interval=5, save=False):
    # Define the colors
    colors = plt.cm.tab10(range(10)).tolist() + ["peru", "navy", "mediumspringgreen", "olivexs"]

    # Create a figure and axes
    fig, ax1 = plt.subplots(figsize=(8, 6))

    # Initialize two empty lists to store the data points
    xs = []
    ys = []

    # Plot the JdK RS-Ratio and Momentum for each sector
    for i, sector in enumerate(sectors):
        if sector == "^GSPC":
            continue
        if sector == "GC=F":
            color = "Gold"
        else:
            color = colors[i]
        label = sector_dict[sector]

        # Scatter the points
        for point in range(points):
            x = index_df[f"{sector} JdK RS-Ratio"].iloc[- 1 - point * interval]
            y = index_df[f"{sector} JdK RS-Momentum"].iloc[- 1 - point * interval]
            xs.append(x)
            ys.append(y)
            label = sector_dict[sector]
            if point == 0:
                ax1.scatter(x, y, color=color, s=50, marker=">", label=label)
            elif point == points - 1:
                ax1.scatter(x, y, color=color, s=50, marker="o")
            else:
                ax1.scatter(x, y, color=color, s=10, marker="o")

            # Connect the point with dashed lines
            if point > 0:
                ax1.plot([x_prev, x], [y_prev, y], color=color, linestyle="--")
            x_prev, y_prev = x, y

    # Set the labels
    ax1.set_xlabel("JdK RS-Ratio")
    ax1.set_ylabel("JdK RS-Momentum")

    # Set the title
    if type == "sector":
        ax1.set_title("Relative rotation graph of sectors")
    elif type == "index":
        ax1.set_title("Relative rotation graph of indices")

    # Add horizontal and vertical lines to (100, 100) origin
    ax1.axhline(y=100, linestyle="--", color="black")
    ax1.axvline(x=100, linestyle="--", color="black")

    # Set the limits
    buffer = 0.25
    x_min, x_max = min(xs) - buffer, max(xs) + buffer
    y_min, y_max = min(ys) - buffer, max(ys) + buffer
    ax1.set_xlim(x_min, x_max)
    ax1.set_ylim(y_min, y_max)

    # Colour each quadrant
    ax1.fill_between([100, x_max], [100, 100], [y_max, y_max], color="green", alpha=0.1)
    ax1.fill_between([x_min, 100], [100, 100], [y_max, y_max], color="blue", alpha=0.1)
    ax1.fill_between([100, x_max], [y_min, y_min], [100, 100], color="gold", alpha=0.1)
    ax1.fill_between([x_min, 100], [y_min, y_min], [100, 100], color="red", alpha=0.1)

    # Add text labels in each corner
    ax1.text(x_max, y_max, "Leading", color="green", ha="right", va="top", weight="bold")
    ax1.text(x_min, y_max, "Improving", color="blue", ha="left", va="top", weight="bold")
    ax1.text(x_max, y_min, "Weakening", color="gold", ha="right", va="bottom", weight="bold")
    ax1.text(x_min, y_min, "Lagging", color="red", ha="left", va="bottom", weight="bold")

    # Set the legend outside the plot
    ax1.legend(bbox_to_anchor=(1.04, 1), borderaxespad=0, fontsize=8)

    # Adjust the spacing between subplots
    plt.tight_layout()
    
    # Save the plot
    if save:
        if type == "sector":
            plt.savefig(f"Result/Figure/sectorrrg.png", dpi=300)
        elif type == "index":
            plt.savefig(f"Result/Figure/indexrrg.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the sectors of the selected stocks
def plot_sector_selected(end_date, index_name, index_dict, period=252, RS=90, NASDAQ_all=True, save=False):
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)
    
    # Format the end date
    end_date_fmt = dt.datetime.strptime(end_date, "%Y-%m-%d").strftime("%d-%m-%y")

    # Define the folder path
    folder_path = os.path.join("Result", f"{end_date_fmt}")

    # Define the filename
    filename = os.path.join(folder_path, f"{infix}stock_{end_date_fmt}period{period}RS{RS}.xlsx")
    
    # Read the data of the screened stocks
    df = pd.read_excel(filename)

    # Count the occurrences of each sector
    sector_counts = df["Sector"].value_counts()

    # Customize the colours
    colors = plt.cm.tab10(range(10)).tolist() + ["peachpuff"]

    # Create a pie chart with count numbers
    plt.figure(figsize=(8, 6))
    plt.pie(sector_counts, labels=sector_counts.index, autopct=lambda x: f'{int(round(x*sum(sector_counts)/100))}', colors=colors)

    # Set the title
    plt.title("Sector distribution of selected stocks")

    # Set the axes to be equal
    plt.axis("equal")

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/{infix}sectorselected.png", dpi=300, bbox_inches="tight")

    # Show the plot
    plt.show()

# Plot the correlation matrix of technical indicators
def plot_corr_ta(stock, df, column_list=["Open", "High", "Low", "Close", "Volume", "MACD", "RSI", "RMI", "CCI", "ADX", "MFI", "OBOS"]):
    # Extract the data
    data = df.copy().dropna()[column_list].values

    # Calculate the correlation matrix
    correlation_matrix = np.corrcoef(data, rowvar=False)

    # Create a heatmap to visualize the correlation matrix
    sns.heatmap(correlation_matrix, annot=True, fmt=".2f", xticklabels=column_list, yticklabels=column_list)
    plt.title(f"Correlation matrix of techinical indicators of {stock}")
    plt.show()

# Plot the correlation matrix of stocks
def plot_corr_stocks(stocks, end_date, years):
    # Get the price data of the stocks
    df_merged = merge_stocks(stocks, end_date)

    # Filter the data
    show = int(years * 252)
    df_merged = df_merged[- show:]
    dfs_close = [df_merged[f"Close ({stock})"].values for stock in stocks]

    # Create the data with the aligned values
    data = np.array(dfs_close)

    # Calculate the correlation matrix
    correlation_matrix = np.corrcoef(data)
    
    # Create a heatmap
    tick_labels = stocks
    sns.heatmap(correlation_matrix, annot=True, fmt=".2f", xticklabels=tick_labels, yticklabels=tick_labels)

    # Set the title
    if years == 1:
        plt.title(f"Correlation matrix in the past {years} year")
    else:
        plt.title(f"Correlation matrix in the past {years} years")

    # Show the plot
    plt.show()

# Plot the autocorrelation of a stock
def plot_autocorr(stock, end_date, years):
    # Get the start date
    start_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(years=years)).strftime("%Y-%m-%d")

    # Get the price data of the stock
    df = get_df(stock, end_date)

    # Filter the data
    df = df[start_date : end_date]

    # Drop rows with nan values and get the closing prices
    data = df.dropna()["Close"].values

    # Create a figure
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)

    # Calculate the autocorrelation
    acfs = acf(data, nlags=252*5)

    # Plot the autocorrelation
    ax.plot(np.arange(len(acfs)), acfs)
    
    # Find the local maxima
    maxima_indices = argrelextrema(acfs, np.greater)[0]
    maxima_values = acfs[maxima_indices]
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

    # Adjust the spacing
    plt.tight_layout()

    # Set the legend
    plt.legend()

    # Show the plot
    plt.show()

# Plot the comparison between long term and short term RS
def plot_longshortRS(merged_df, end_date1, end_date2, stock_star=None):
    # Scatter plot of short-term RS against long-term RS
    plt.figure(figsize=(10, 6))
    plt.scatter(merged_df["Long-term RS"], merged_df["Short-term RS"], color="blue", marker="x")

    # Highlight the specific stock with a star
    star = merged_df[merged_df["Stock"] == stock_star]
    if not star.empty:
        plt.scatter(star["Long-term RS"], star["Short-term RS"], color="gold", edgecolor="black", marker="*", s=100, label=stock_star)

    # Plot a red vertical line at long-term RS = 20
    plt.axvline(x=20, color="red", linestyle="--")

    # Calculate the slope and R^2
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

    # Show the plot
    plt.show()

# Plot the comparison between long and short term RS
def plot_compare_longshortRS(index_df, index_name, rs_slopes, r_squareds, end_dates, end_dates2, save=False):
    # Filter the dataframe
    index_df = index_df.loc[(index_df.index >= end_dates[0]) & (index_df.index <= end_dates[-1])]

    # Create a figure with four subplots, one for the closing price, one for the RS slope, one for the R^2 values, and one for the z-Score of product
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 0.5, 0.5, 1]}, sharex=True)

    # Plot the closing price on the first subplot
    ax1.plot(index_df["Close"], label="Close")

    # Set the y label of the first subplot
    ax1.set_ylabel("Price")

    # Set the x limit of the first subplot
    ax1.set_xlim(index_df.index[0], index_df.index[-1])

    # Create a dataframe for RS slope
    rs_slope_df = pd.DataFrame({"RS Slope": rs_slopes}, index=pd.to_datetime(end_dates2))

    # Plot the RS slope on the second subplot
    ax2.plot(rs_slope_df["RS Slope"], color="orange")

    # Add a horizontal line at y=0
    ax2.axhline(y=0, color="black", linestyle="--", linewidth=0.5)

    # Set the y label for the second subplot
    ax2.set_ylabel("RS slope")

    # Create a dataframe for R^2
    r_squareds_df = pd.DataFrame({"R^2": r_squareds}, index=pd.to_datetime(end_dates2))

    # Plot the R^2 on the third subplot
    ax3.plot(r_squareds_df, color="orange")

    # Set the y label for the third subplot
    ax3.set_ylabel(r"$R^2$")

    # Calculate the z-scores of the product of RS slope and R^2
    rs_slopes_r2 = np.array(rs_slopes) * r_squareds
    rs_slopes_r2_mean = np.mean(rs_slopes_r2)
    rs_slopes_r2_std = np.std(rs_slopes_r2)
    z_scores = (rs_slopes_r2 - rs_slopes_r2_mean) / rs_slopes_r2_std

    # Create a dataframe for z-scores
    z_scores_df = pd.DataFrame({"Z-Score": z_scores}, index=pd.to_datetime(end_dates2))

    # Plot the z-scores of the product of RS slope and R^2 on the fourth subplot
    ax4.plot(z_scores_df, color="orange")

    # Add a horizontal line at y=0
    ax4.axhline(y=0, color="black", linestyle="--", linewidth=0.5)

    # Add a red dotted line at y=2
    ax4.axhline(y=2, color="red", linestyle="dotted")

    # Add a red dotted line at y=-2
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
        plt.savefig(f"Result/Figure/RSslope{index_name}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the 5-min intraday volume of a stock on a specific date
def plot_volume5m(stock, volume5m_data, date, period=50, save=False):
    # Extract the data
    if volume5m_data is None:
        return
    
    df_date = volume5m_data["df_date"]
    df0_hours = volume5m_data["df0_hours"]
    volume5m_sma_df0 = volume5m_data["volume5m_sma_df0"]
    volume5m_std_df0 = volume5m_data["volume5m_std_df0"]
    sma_hours = volume5m_data["sma_hours"]

    # Create a figure with two subplots, one for the 5-min volume, one for the 5-min volume SMA 50 ratio, and one for the z-score
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, sharex=True)
    
    # Plot the 5-min volume on the first subplot
    ax1.bar(df0_hours, df_date["Volume"], width=5/60/2, label="5-min Volume", align="edge", alpha=0.7)

    # Plot the 5-min volume SMA 50 on the first subplot
    ax1.plot(sma_hours, volume5m_sma_df0.values, label=f"SMA {period}", color="purple")

    # Calculate the ratio of the first 5-min volume with SMA 50
    ratio = df_date["Volume"].iloc[0] / volume5m_sma_df0.values[0]

    # Add ratio text next to the first volume point
    ax1.text(df0_hours.iloc[0] + 0.05, df_date["Volume"].iloc[0], f"First 5-min ratio: {ratio:.2f}", fontsize=12)

    # Set the y label of the first subplot
    ax1.set_ylabel("Volume")

    # Set the x limit of the first subplot
    ax1.set_xlim(0, df0_hours.iloc[-1] + 5/60/2)

    # Calculate the 5-min volume SMA 50 ratio
    ratios = df_date["Volume"] / volume5m_sma_df0.values

    # Plot the 5-min volume SMA 50 ratio on the second subplot
    ax2.plot(df0_hours, ratios)

    # Set the y label of the second subplot
    ax2.set_ylabel("Vol/SMA 50")

    # Calculate the z-scores
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
        plt.savefig(f"Result/Figure/5minvol{stock}_{date}.png", dpi=300)

    # Show the plot
    plt.show()

# Plot the n days dist
def plot_ndays_dist(df, column, title, xlabel, figure_name=None, save=False):
    # Define the result folder
    result_folder = "Result/Figure"

    # Extract the array
    arr = df[column]

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot histogram with counts
    counts, bins, _ = plt.hist(arr, bins=100, color="blue", edgecolor="black", alpha=0.7)

    # Fit Gaussian curve
    mean = np.mean(arr)
    sd = np.std(arr)
    xmin = np.min(arr)
    xmax = np.max(arr)
    x = np.linspace(xmin, xmax, 10000)
    p = norm.pdf(x, mean, sd)

    # Scale Gaussian curve to match histogram counts
    bin_width = bins[1] - bins[0]
    scaling_factor = len(arr) * bin_width
    p = p * scaling_factor

    # Plot scaled Gaussian curve
    plt.plot(x, p, color="red")

    # Add a dotted line for the mean value
    plt.axvline(mean, color="black", linestyle="dotted")
    
    # Calculate the minimum and maximum z-score
    zscore_min = np.ceil((mean - xmin) / sd)
    zscore_max = np.ceil((xmax - mean) / sd)

    # Add dotted lines for standard deviations
    for i in range(1, int(zscore_min)):
        plt.axvline(mean - i * sd, color="red", linestyle="dotted")
    for i in range(1, int(zscore_max)):
        plt.axvline(mean + i * sd, color="red", linestyle="dotted")

    # Calculate the kurtosis
    kurt_value = kurtosis(arr)

    # Add mean and kurtosis to the plot
    plt.text(0.95, 0.95, f"Mean: {mean:.4f}\nKurtosis: {kurt_value:.2f}", 
             ha="right", va="top", transform=plt.gca().transAxes, 
             bbox={'facecolor': 'white', 'alpha': 0.8, 'pad': 5})

    # Set title and labels
    plt.title(f"{title}")
    plt.xlabel(f"{xlabel}")
    plt.ylabel("Count")

    # Set y-ticks to only show integers
    plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(os.path.join(result_folder, figure_name), dpi=300)

    # Show the plot
    plt.show()