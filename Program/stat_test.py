# Imports
import datetime as dt
from helper_functions import get_current_date, generate_end_dates, get_df, get_infix
from backtest import calculate_stats, get_momentum_labels
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
    CAGR_values = []
    sharpe_ratio_values = []
    sortino_ratio_values = []

    # Iterate over the statistics of all factors to extract values
    for stats in factors_stats:
        mvp_factor, eps_yoy_factor, eps_qoq_factor = stats[0]
        CAGR = stats[1][1][2] * 100 # Extract and convert CAGR to percentage
        sharpe_ratio = stats[1][1][4]
        sortino_ratio = stats[1][1][5]
        CAGR_values.append(CAGR)
        sharpe_ratio_values.append(sharpe_ratio)
        sortino_ratio_values.append(sortino_ratio)

    # Calculate the CAGR, Sharpe ratio, and Sortino ratio values of the index
    stats_index = calculate_stats(index_df, len(index_df) / 252)[1]
    CAGR_index = stats_index[2] * 100
    print(f"CAGR of index: {CAGR_index:.3e}.")
    sharpe_ratio_index = stats_index[4]
    print(f"Sharpe ratio of index: {sharpe_ratio_index:.3e}.")
    sortino_ratio_index = stats_index[5]
    print(f"Sortino ratio of index: {sortino_ratio_index:.3e}.")

    # Calculate the mean, SD, and t-statistic of CAGR, Sharpe ratio, and Sortino ratio values
    CAGR_mean = np.mean(CAGR_values)
    t_CAGR, p_CAGR = ttest_1sample(CAGR_values, CAGR_index)
    sharpe_ratio_mean = np.mean(sharpe_ratio_values)
    t_sharpe_ratio, p_sharpe_ratio = ttest_1sample(sharpe_ratio_values, sharpe_ratio_index)
    sortino_ratio_mean = np.mean(sortino_ratio_values)
    t_sortino_ratio, p_sortino_ratio = ttest_1sample(sortino_ratio_values, sortino_ratio_index)

    # Print the p-values
    print(f"The mean of CAGR is {CAGR_mean:.3e}, and the p-value of is {p_CAGR:.3e}.")
    print(f"The mean of Sharpe ratio is {sharpe_ratio_mean:.3e}, and the p-value is {p_sharpe_ratio:.3e}.")
    print(f"The mean of Sortino ratio is {sortino_ratio_mean:.3e}, and the p-value is {p_sortino_ratio:.3e}.")

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()