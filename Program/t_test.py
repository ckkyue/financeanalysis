# Imports
import datetime as dt
from helper_functions import get_current_date, generate_end_dates, get_df, get_infix
from backtest import calculate_stats
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import t

# Calculate the p-value of one-sample t-test
def ttest_1sample(values, specified_value):
    n = len(values)
    dof = n - 1
    mean = np.mean(values)
    sd = np.std(values)
    t_statistic = (mean - specified_value) / (sd / np.sqrt(n))
    p_value = t.cdf(-t_statistic, df=dof)

    return t_statistic, p_value

# Main program
def main():
    # Start of the program
    start = dt.datetime.now()

    # Variables
    HKEX_all = True
    NASDAQ_all = True
    period_hk = 60 # Period for HK stocks
    period_us = 252 # Period for US stocks
    RS = 90
    backtest = True

    # Index
    index_name = "^GSPC"
    index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite"}

    # Get the current date
    current_date = get_current_date(start, index_name)

    # Create the end dates
    years = 5
    end_dates = generate_end_dates(years, current_date)
    end_dates.append(current_date)

    # Number of stocks to be selected
    top = 5

    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    # Filter the data
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Get the infix
    infix = get_infix("^GSPC", index_dict, True)

    # Load the statistics of all factors
    factors_stats = np.load(f"Backtest/{infix}factors_statsyears{years}top{top}.npy", allow_pickle=True)

    # Calculate the CAGR, Sharpe ratio and Sortino ratio values of momentum strategies
    # Initialize three empty lists to store the metrics
    CAGR_values = []
    sharpe_ratio_values = []
    sortino_ratio_values = []

    # Iterate over all factors
    for stats in factors_stats:
        factors = stats[0]
        mvp_factor, eps_yoy_factor, eps_qoq_factor = factors
        if mvp_factor < 0.5:
            CAGR = stats[1][1][2] * 100
            sharpe_ratio = stats[1][1][4]
            sortino_ratio = stats[1][1][5]
            CAGR_values.append(CAGR)
            sharpe_ratio_values.append(sharpe_ratio)
            sortino_ratio_values.append(sortino_ratio)

    # Calculate the CAGR, Sharpe ratio and Sortino ratio values of the index
    stats_index = calculate_stats(index_df, len(index_df) / 252)[1]
    CAGR_index = stats_index[2] * 100
    print(f"CAGR of index: {CAGR_index:.3e}.")
    sharpe_ratio_index = stats_index[4]
    print(f"Sharpe ratio of index: {sharpe_ratio_index:.3e}.")
    sortino_ratio_index = stats_index[5]
    print(f"Sortino ratio of index: {sortino_ratio_index:.3e}.")

    # Calculate the mean, SD, and t-statistic of CAGR, Sharpe ratio and Sortino ratio values
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