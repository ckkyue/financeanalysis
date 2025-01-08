# Imports
import datetime as dt
from helper_functions import get_current_date, generate_end_dates, get_df, get_infix
from backtest import calculate_stats, get_momentum_labels
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from plot import *
from scipy.stats import t
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
    if backtest:
        result_folder = "Backtest"
    else:
        result_folder = "Result"

    # Define the folder for saving figures
    figure_folder = os.path.join(result_folder, "Figure")

    # Convert data to a DataFrame
    df = pd.DataFrame(data, columns=["x", "y", "z"])

    # Pivot the DataFrame to create a matrix for the heatmap
    matrix = df.pivot(index="y", columns="x", values="z")

    # Extract the maximum value from the matrix
    matrix_max = matrix.max().max()

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
    infix = get_infix("^GSPC", index_dict, True)

    # Get the current date
    current_date = get_current_date(start, index_name)
    current_date = "2024-12-27"

    # Parameters for backtesting the momentum strategy
    years = 5
    interval = "2w"
    top = 5
    cap_threshold = 10
    stoploss_threshold = None
    momentum_params = {"years": years, 
                       "interval": interval, 
                       "top": top, 
                       "cap_threshold": cap_threshold, 
                       "stoploss_threshold": stoploss_threshold, 
                       "period_short": 1, 
                       "period_long": 200, 
                       "sma_crossover": False, 
                       "leverage": 1, 
                       "fee_rate": 0.001}
    
    # Create the end dates
    end_dates = generate_end_dates(7, current_date, interval=interval)
    end_dates.append(current_date)
    if years < 7:
        end_dates = [end_date for end_date in end_dates if end_date >= generate_end_dates(years, current_date, interval=interval)[0]]

    # Parameters of the KNN model
    knn_params = None

    # Get the labels of the momentum strategy
    sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    # Filter the data
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Get the infix
    infix = get_infix("^GSPC", index_dict, True)

    # Load the statistics of all factors
    factors_stats = np.load(f"Backtest/{infix}factors_statsyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.npy", allow_pickle=True)

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

    # Calculate the mean, SD, and t-statistic of CAGR, Sharpe ratio, and Sortino ratio values
    cagr_mean = np.mean(cagr_values)
    t_cagr, p_cagr = ttest_1sample(cagr_values, cagr_index)
    sharpe_ratio_mean = np.mean(sharpe_ratio_values)
    t_sharpe_ratio, p_sharpe_ratio = ttest_1sample(sharpe_ratio_values, sharpe_ratio_index)
    sortino_ratio_mean = np.mean(sortino_ratio_values)
    t_sortino_ratio, p_sortino_ratio = ttest_1sample(sortino_ratio_values, sortino_ratio_index)

    # Print the p-values
    print(f"The mean of CAGR is {cagr_mean:.3e}, and the p-value of is {p_cagr:.3e}.")
    print(f"The mean of Sharpe ratio is {sharpe_ratio_mean:.3e}, and the p-value is {p_sharpe_ratio:.3e}.")
    print(f"The mean of Sortino ratio is {sortino_ratio_mean:.3e}, and the p-value is {p_sortino_ratio:.3e}.")

    # Plot the heatmaps
    plot_heatmap(cagr_data, "MVP factor", "EPS YoY factor", f"CAGR distribution ({years} years {interval} cap {cap_threshold})", benchmark=cagr_index, filename=f"cagrdistyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png", save=True, backtest=True)
    plot_heatmap(sharpe_ratio_data, "MVP factor", "EPS YoY factor", f"Sharpe distribution ({years} years {interval} cap {cap_threshold})", benchmark=sharpe_ratio_index, filename=f"sharpedistyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png", save=True, backtest=True)
    plot_heatmap(sortino_ratio_data, "MVP factor", "EPS YoY factor", f"Sortino distribution ({years} years {interval} cap {cap_threshold})", benchmark=sortino_ratio_index, filename=f"sortinodistyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png", save=True, backtest=True)

    # Plot the histograms
    plot_hist(cagr_values, "CAGR (%)", f"CAGR distribution ({years} years {interval} cap {cap_threshold})", benchmark=cagr_index, filename=f"cagrhistyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png", save=True, backtest=True)
    plot_hist(sharpe_ratio_values, "Sharpe", f"Sharpe distribution ({years} years {interval} cap {cap_threshold})", benchmark=sharpe_ratio_index, filename=f"sharpehistyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png", save=True, backtest=True)
    plot_hist(sortino_ratio_values, "Sortino", f"Sortino distribution ({years} years {interval} cap {cap_threshold})", benchmark=sortino_ratio_index, filename=f"sortinohistyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png", save=True, backtest=True)

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()