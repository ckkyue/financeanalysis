# Imports
import datetime as dt
from helper_functions import modify_current_date, generate_end_dates, get_df, get_infix
from backtest import calculate_stats, get_momentum_labels
import itertools
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import pickle
from plot import *
from scipy.stats import false_discovery_control, t, wilcoxon
import seaborn as sns

def ttest_1sample(values, specified_value):
    """
    Calculate the t-statistic and p-value for a one-sample t-test.

    Parameters:
    - values (array-like): The sample data for which the t-test is to be performed.
    - specified_value (float): The value to test against the sample mean.

    Returns:
    - tuple: A tuple containing:
        - t_stat (float): The calculated t-statistic.
        - p_value (float): The one-tailed p-value of the test.
    
    The function uses the formula for the t-statistic:
    t = (mean - specified_value) / (sd / sqrt(n))
    where:
    - mean is the sample mean,
    - sd is the sample standard deviation,
    - n is the sample size.
    """
    
    n = len(values)
    dof = n - 1
    mean = np.mean(values)
    sd = np.std(values)
    t_stat = (mean - specified_value) / (sd / np.sqrt(n))
    p_value = t.cdf(-t_stat, df=dof)

    return t_stat, p_value

def momentum_returns(momentum_dict, years, interval="1m"):
    """
    Calculate the returns of the momentum strategy.

    Parameters:
    momentum_dict (dict): The momentum dictionary containing the factors and the index DataFrames.
    interval (str, optional): The interval for which the returns are calculated. Default to "1m".

    Returns:
    returns_dict (dict): The dictionary containing the returns of the momentum strategy.
    """

    # Initialise the returns dictionary
    returns_dict = {}

    # Iterate through the factors
    for factors_tuple, df in tqdm(momentum_dict.items()):
        # Get the momentum dataframe
        df = momentum_dict[factors_tuple]

        # Get the start and end date
        start_date = df.index[0]
        start_date = start_date.strftime("%Y-%m-%d")
        end_date = df.index[-1]
        end_date = end_date.strftime("%Y-%m-%d")
        end_dates = generate_end_dates(end_date=end_date, years=years, interval=interval)
        end_dates = [date for date in end_dates if date >= start_date]

        # Calculate percent change and cumulative return for the index
        df["Percent Change"] = df["Close"].pct_change()
        df.fillna({"Percent Change": 0}, inplace=True)
        df["Cumulative Return"] = (1 + df["Percent Change"]).cumprod()

        # Calculate the returns for the index according to the end dates
        closes_index = df.loc[end_dates, "Cumulative Return"].values
        returns_index = np.diff(closes_index) / closes_index[:-1]

        # Calculate the returns of the stocks according to the end dates
        closes_stocks = df.loc[end_dates, "Cumulative Stock Return"].values
        returns_stock = np.diff(closes_stocks) / closes_stocks[:-1]

        # Add the returns to the returns dictionary
        returns_dict[factors_tuple] = {"index": returns_index, "stock": returns_stock}

    return returns_dict

def calculate_wilcoxon_stats(returns_dict):
    """
    Calculate the Wilcoxon statistics of the returns of the stocks and the index.

    Parameters:
    - returns_dict (dict): A dictionary containing the returns of the momentum strategy.

    Returns:
    - wilcoxon_dict (dict): A dictionary containing the Wilcoxon statistics of the returns.
    """
    
    # Create a dictionary to store the Wilcoxon statistics
    wilcoxon_dict = {}

    # Iterate through the factors
    for factors_tuple, returns in tqdm(returns_dict.items()):
        # Get the returns of the stocks and the index
        returns_index = returns["index"]
        returns_stock = returns["stock"]

        # Calculate the difference in returns
        returns_diff = returns_stock - returns_index

        # Calculate the Wilcoxon statistics of the returns
        w_returns, p_w_returns = wilcoxon(returns_diff, alternative="greater", method="exact")

        # Store the Wilcoxon statistics in the dictionary
        wilcoxon_dict[factors_tuple] = {"w": w_returns, "p": p_w_returns}

    return wilcoxon_dict

def plot_heatmap(data, xlabel, ylabel, title, benchmark=None, filename=None, cmap="RdYlGn", save=False, backtest=False):
    """
    Plots a heatmap based on the provided data.

    Parameters:
    - data (list of tuples): Input data in the form of [(x1, y1, z1), (x2, y2, z2), ...].
    - xlabel (str): Label for the x-axis.
    - ylabel (str): Label for the y-axis.
    - title (str): Title of the plot.
    - benchmark (float, optional): A benchmark value to be indicated on the plot. Default is None.
    - filename (str, optional): The name of the file to save the figure. Default is None (no save).
    - cmap (str, optional): Colourmap for the heatmap. Default is "RdYlGn" for a red-green colour scheme.
    - save (bool, optional): Whether to save the plot as a PNG file. Default is False.
    - backtest (bool): Flag to indicate if backtesting is being performed. Default is False.

    Returns:
    - None: This function generates a plot and displays it or saves it to a file.
    """

    # Set the result folder based on backtest flag
    result_folder = "Backtest" if backtest else "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Convert data to a DataFrame
    df = pd.DataFrame(data, columns=["x", "y", "z"])

    # Pivot the DataFrame to create a matrix for the heatmap
    matrix = df.pivot(index="y", columns="x", values="z")

    # Extract the maximum value from the matrix for colour scaling
    matrix_max = matrix.max().max()

    # Create the heatmap
    plt.figure(figsize=(10, 6))

    # Plot heatmap with benchmark as the centre point
    if benchmark is not None:
        ax = sns.heatmap(matrix, annot=True, cmap=cmap, cbar=True, center=benchmark, vmin=0, vmax=matrix_max)

        # Customize the colour bar to indicate where the benchmark is
        ax.collections[0].colorbar.set_ticks([benchmark])
        ax.collections[0].colorbar.set_ticklabels(["Benchmark"])
    else:
        ax = sns.heatmap(matrix, annot=True, cmap="RdYlGn", cbar=True)

    # Reverse the y-axis
    plt.gca().invert_yaxis()

    # Annotate the benchmark value if provided
    if benchmark is not None:
        # Get current axis limits
        xlim = plt.xlim()
        ylim = plt.ylim()

        # Position the benchmark annotation in the upper right corner
        plt.annotate(f"Benchmark: {benchmark:.2f}", xy=(xlim[1], 0.95 * ylim[1]), color="black", ha="right", va="top", bbox={"facecolor": "white", "edgecolor": "black"})

    # Set the title
    plt.title(title)

    # Set the labels
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        filename = os.path.join(figure_folder, filename)
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

# Main program
def main():
    # Start of the program
    start = dt.datetime.now()

    # Index
    index_name = "^GSPC"
    index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite"}

    # Get the infix
    infix = get_infix("^GSPC", index_dict, True, True)

    # Modify the current date
    current_date = modify_current_date(start, index_name)

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
    
    # Create the end dates
    end_dates = generate_end_dates(end_date="2024-12-20", years=7, interval=interval)
    if years < 7:
        start_date = generate_end_dates(end_date=end_dates[-1], years=years, interval=interval)[0]
        end_dates = [date for date in end_dates if date >= start_date]
    
    # Get the labels of the momentum strategy
    sma_label, cap_label, sl_label, sg_label = get_momentum_labels(momentum_params)

    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    # Filter the data
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Get the infix
    infix = get_infix("^GSPC", index_dict, True, True)

    # Load the statistics of all factors
    factors_stats = np.load(f"Backtest/Factors stats/{infix}factors_statsyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.npy", allow_pickle=True)

    # Compare the statistics between the index and stocks selected by the momentum strategy
    # Initialise lists to store various statistics
    cagr_values = []
    cagr_data = []
    sharpe_ratio_values = []
    sharpe_ratio_data = []
    sortino_ratio_values = []
    sortino_ratio_data = []

    # Iterate over the statistics of all factors to extract values
    for stats in factors_stats:
        mvp_factor, eps_yoy_factor, eps_qoq_factor = stats[0]
        cagr = stats[1][1][2] * 100 # Extract and convert CAGR to percentage
        sharpe_ratio = stats[1][1][4]
        sortino_ratio = stats[1][1][5]
        cagr_values.append(cagr)
        cagr_data.append((mvp_factor, eps_yoy_factor, cagr))
        sharpe_ratio_values.append(sharpe_ratio)
        sharpe_ratio_data.append((mvp_factor, eps_yoy_factor, sharpe_ratio))
        sortino_ratio_values.append(sortino_ratio)
        sortino_ratio_data.append((mvp_factor, eps_yoy_factor, sortino_ratio))

    # Calculate the CAGR, Sharpe ratio, and Sortino ratio values of the index
    stats_index = calculate_stats(index_df, len(index_df) / 252)[1]
    cagr_index = stats_index[2] * 100
    print(f"CAGR of index: {cagr_index:.3e}.")
    sharpe_ratio_index = stats_index[4]
    print(f"Sharpe ratio of index: {sharpe_ratio_index:.3e}.")
    sortino_ratio_index = stats_index[5]
    print(f"Sortino ratio of index: {sortino_ratio_index:.3e}.")

    # Calculate the mean, SD, t-statistic, and Wilcoxon statistic of CAGR, Sharpe ratio, and Sortino ratio values
    cagr_mean = np.mean(cagr_values)
    cagr_diff = cagr_values - cagr_index
    t_cagr, p_t_cagr = ttest_1sample(cagr_values, cagr_index)
    w_cagr, p_w_cagr = wilcoxon(cagr_diff, alternative="greater", method="exact")
    sharpe_ratio_mean = np.mean(sharpe_ratio_values)
    sharpe_ratio_diff = sharpe_ratio_values - sharpe_ratio_index
    t_sharpe_ratio, p_t_sharpe_ratio = ttest_1sample(sharpe_ratio_values, sharpe_ratio_index)
    w_sharpe_ratio, p_w_sharpe_ratio = wilcoxon(sharpe_ratio_diff, alternative="greater", method="exact")
    sortino_ratio_mean = np.mean(sortino_ratio_values)
    sortino_ratio_diff = sortino_ratio_values - sortino_ratio_index
    t_sortino_ratio, p_t_sortino_ratio = ttest_1sample(sortino_ratio_values, sortino_ratio_index)
    w_sortino_ratio, p_w_sortino_ratio = wilcoxon(sortino_ratio_diff, alternative="greater", method="exact")

    # Print the statistics
    print(f"The mean of CAGR is {cagr_mean:.3e}, the p-value of t-statistic is {p_t_cagr:.3e}, and the p-value of Wilcoxon statistic is {p_w_cagr:.3e}.")
    print(f"The mean of Sharpe ratio is {sharpe_ratio_mean:.3e}, the p-value of t-statistic is {p_t_sharpe_ratio:.3e}, and the p-value of Wilcoxon statistic is {p_w_sharpe_ratio:.3e}.")
    print(f"The mean of Sortino ratio is {sortino_ratio_mean:.3e}, the p-value of t-statistic is {p_t_sortino_ratio:.3e}, and the p-value of Wilcoxon statistic is {p_w_sortino_ratio:.3e}.")

    # Define the filename for the momentum dictionary
    momentum_dict_filename = f"Backtest/Momentum dict/{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}{sg_label}.pkl"

    # Load the momentum dictionary
    with open(momentum_dict_filename, "rb") as file:
        momentum_dict = pickle.load(file)

    # Calculate the returns of the momentum strategy
    returns_dict = momentum_returns(momentum_dict, years, interval="1m")

    # Calculate the Wilcoxon statistics of the returns
    wilcoxon_dict = calculate_wilcoxon_stats(returns_dict)

    # Extract the p-values of the Wilcoxon statistics
    p_w_returns = [value["p"] for value in wilcoxon_dict.values()]

    # Perform the Benjamini-Hochberg correction
    p_w_returns_bh = false_discovery_control(p_w_returns)

    # Count the number of significant p-values
    print(f"The number of significant Wilcoxon p-values for returns is {sum(p_w_returns_bh < 0.05)}.")

    # Plot the heatmaps
    plot_heatmap(cagr_data, "MVP factor", "EPS YoY factor", f"CAGR distribution ({years} years {interval} cap {cap_threshold})", benchmark=cagr_index, filename=f"cagrdistyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}.png", backtest=True)
    plot_heatmap(sharpe_ratio_data, "MVP factor", "EPS YoY factor", f"Sharpe distribution ({years} years {interval} cap {cap_threshold})", benchmark=sharpe_ratio_index, filename=f"sharpedistyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}.png", backtest=True)
    plot_heatmap(sortino_ratio_data, "MVP factor", "EPS YoY factor", f"Sortino distribution ({years} years {interval} cap {cap_threshold})", benchmark=sortino_ratio_index, filename=f"sortinodistyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}.png", backtest=True)

    # Plot the histograms
    plot_hist(cagr_values, "CAGR (%)", f"CAGR distribution ({years} years {interval} cap {cap_threshold})", benchmark=cagr_index, filename=f"cagrhistyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}.png", backtest=True)
    plot_hist(sharpe_ratio_values, "Sharpe", f"Sharpe distribution ({years} years {interval} cap {cap_threshold})", benchmark=sharpe_ratio_index, filename=f"sharpehistyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}.png", backtest=True)
    plot_hist(sortino_ratio_values, "Sortino", f"Sortino distribution ({years} years {interval} cap {cap_threshold})", benchmark=sortino_ratio_index, filename=f"sortinohistyears{years}itv{interval}top{top}{sma_label}{cap_label}{sl_label}.png", backtest=True)

    # Plot the distribution of the Wilcoxon p-values
    plot_hist(p_w_returns, r"$p$-values of returns", r"Wilcoxon $p$-values distribution", filename="wilcoxonpdist.png")

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()