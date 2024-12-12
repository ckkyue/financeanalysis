# Imports
import concurrent.futures
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

# Define the folder path
folder_path = "Fundamentals"

# Check if there are pre-existing data
current_files = [file for file in os.listdir(folder_path) if file.endswith("_fundamentals_2024-12-01.csv")]
stocks_fund = [file.split("_")[0] for file in current_files]

stocks = stock_market(current_date, current_date, index_name, HKEX_all, NASDAQ_all)
stocks = [stock for stock in stocks if stock > "GLSTR"]
stocks = [stock for stock in stocks if stock not in stocks_fund]

for stock in tqdm(stocks):
    fundamentals_csv(stock, current_date)