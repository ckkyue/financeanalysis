# Imports
import datetime as dt
from fundamentals import *
from functools import partial
from helper_functions import get_current_date, get_df, get_volume5m_data, generate_end_dates, merge_stocks, stock_market
import matplotlib.pyplot as plt
import multiprocessing
import numpy as np
import pandas as pd
pd.options.mode.chained_assignment = None
from plot import *
from scipy.stats import linregress, pearsonr, ttest_ind
from stock_screener import check_conds_tech, get_stock_info, stoploss_target
from technicals import *
from tqdm import tqdm

# Start of the program
start = dt.datetime.now()

# Variables
HKEX_all = False
NASDAQ_all = True
period_hk = 60 # Period for HK stocks
period_us = 252 # Period for US stocks
RS = 90
factors = [1, 1, 1]
backtest = False

# Index
index_name = "^GSPC"
index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite"}

# Get the infix
infix = get_infix(index_name, index_dict, NASDAQ_all)

# Get the current date
current_date = get_current_date(start, index_name)

# Define the result folder
result_folder = "Result"

# Get the stocks of the stock market
stocks = stock_market(current_date, current_date, index_name, HKEX_all, NASDAQ_all)
stocks = [stock for stock in stocks if stock > "REG"]

# for stock in stocks:
#     fundamentals_csv(stock, current_date)

if __name__ == "__main__":
    # Create a partial function with current_date
    partial_fundamentals_csv = partial(fundamentals_csv, end_date=current_date)
    # Create a pool of worker processes
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = list(tqdm(pool.imap(partial_fundamentals_csv, stocks), total=len(stocks)))