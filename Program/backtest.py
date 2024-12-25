# Imports
import ast
import datetime as dt
from dateutil.relativedelta import relativedelta
from helper_functions import get_current_date, generate_end_dates, get_df, get_infix, randomize_array
import itertools
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import pickle
from plot import plot_autocorr, plot_corr_stocks, plot_corr_ta
from scipy.stats import skew, kurtosis
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from stock_screener import create_stock_dict
from technicals import *
from tqdm import tqdm

# Get the equity curve of stocks
def stocks_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, top, knn_params=None, period_short=50, period_long=200, SMA_crossover=True, factor_bear=1, leverage=1, fee_rate=0.0003):
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest/Stock dict"

    # Define the filename
    filename = os.path.join(result_folder, f"{infix}stock_dict{factors}.txt")
    
    # Open the file if it exists
    if os.path.isfile(filename):
        with open(filename, "r") as file:
            # Retrieve the content of stock_dict as a dictionary
            stock_dict = ast.literal_eval(file.read())
    else:
        print("Error getting stock_dict.")
        return None

    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    # Calculate the moving averages
    for i in [period_short, period_long]:
        index_df.loc[:, f"SMA {str(i)}"] = SMA(index_df, i)
        index_df.loc[:, f"EMA {str(i)}"] = EMA(index_df, i)

    # Run the KNN model if parameters are provided
    if knn_params is not None:
        # Delayed import of the KNN model
        from knn_model import knn_accuracy, preprocess_knn

        # Extract the parameters
        k = knn_params["k"]
        lookback = knn_params["lookback"]
        features = knn_params["features"]

        # Preprocess the data for the KNN model
        X_train_index, Y_train_index, X_test_index, Y_test_index, df_test_index = preprocess_knn(index_df, end_dates[0], end_dates[-1], lookback, features)

        # Run the KNN model
        accuracy_train_knn_index, accuracy_test_knn_index, cm_train_knn_index, cm_test_knn_index, X_train_knn_index, X_test_knn_index = knn_accuracy(X_train_index, Y_train_index, X_test_index, Y_test_index, k)
        accuracy_train_lknn_index, accuracy_test_lknn_index, cm_train_lknn_index, cm_test_lknn_index, X_train_lknn_index, X_test_lknn_index = knn_accuracy(X_train_index, Y_train_index, X_test_index, Y_test_index, k, lorentzian=True)

        # KNN signal
        index_df.loc[end_dates[0] : end_dates[-1], f"Index KNN Signal"] = X_test_knn_index

        # Lorentzian KNN Signal
        index_df.loc[end_dates[0] : end_dates[-1], f"Index LKNN Signal"] = X_test_lknn_index

    # Filter the data
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Calculate the percent change and cumulative return of the index
    index_df["Percent Change"] = index_df["Close"].pct_change()
    index_df["Cumulative Return"] = (index_df["Percent Change"] + 1).cumprod()

    # Get the list of stocks
    stocks_list = [stock_dict[end_date] for end_date in end_dates[:-1]]

    # Iterate over all end dates
    for i in tqdm(range(len(end_dates) - 1)):
        start_date = end_dates[i]
        end_date = end_dates[i + 1]
        stocks = stocks_list[i]
        
        # Check if short SMA is above long SMA
        cond = index_df.loc[start_date, f"SMA {str(period_short)}"] > index_df.loc[start_date, f"SMA {str(period_long)}"] or not SMA_crossover
        if cond:
            factor = 1
        elif not cond:
            factor = factor_bear
        
        # Initialize stocks_num outside the loop
        stocks_num = 0
        
        if stocks is not None:
            # Iterate over all stocks
            for j in range(min(top, len(stocks))):
                stock = stocks[j]

                # Get the price data of the stock
                df = get_df(stock, current_date)
                
                # Check if the dataframe is empty
                if df.empty:
                    continue
                    
                try:
                    # Filter the data
                    df = df[start_date : end_date]

                    # Calculate the percentage change of the stock
                    df["Percent Change"] = df["Close"].pct_change()
                    df.loc[start_date, "Percent Change"] = (df.loc[start_date, "Close"] - (1 + fee_rate) * df.loc[start_date, "Open"]) / df.loc[start_date, "Open"]

                    # Calculate the cumulative return of the stock
                    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

                    # Increment stocks_num for successful calculation
                    stocks_num += 1

                    # Include the results into index_df
                    index_df.loc[start_date : end_date, f"Stock {str(j + 1)}"] = stock
                    index_df.loc[start_date : end_date, f"Stock {str(j + 1)} Percent Change"] = df["Percent Change"]
                    index_df.loc[start_date : end_date, f"Stock {str(j + 1)} Cumulative Return"] = df["Cumulative Return"]
                except Exception as e:
                    print(f"Error calculating cumulative return for {stock}: {e}\n")
                    pass

            # Calculate the percent change using stocks_num
            for j in range(min(top, len(stocks))):
                column = f"Stock {str(j + 1)} Percent Change"
                if column in index_df.columns:
                    index_df.loc[start_date : end_date, column] = factor * index_df.loc[start_date : end_date, column] / stocks_num
            
    # Initialize a new column to store the stock returns
    index_df["Stock Percent Change"] = 0

    # Calculate the cumulative stock return
    for i in range(top):
        index_df[f"Stock {i + 1} Percent Change"].fillna(0, inplace=True)
        index_df["Stock Percent Change"] += leverage * index_df[f"Stock {i + 1} Percent Change"]
    index_df["Cumulative Stock Return"] = (index_df["Stock Percent Change"] + 1).cumprod()

    # Calculate the cumulative stock returns of the KNN model if parameters are provided
    if knn_params is not None:
        # Initialize two new columns to store the stock returns of the KNN model
        index_df["KNN Stock Percent Change"] = 0
        index_df["LKNN Stock Percent Change"] = 0
        for i in range(top):
            index_df["KNN Stock Percent Change"] += leverage * index_df[f"Stock {str(i + 1)} Percent Change"] * index_df["Index KNN Signal"].shift(1)
            index_df["LKNN Stock Percent Change"] += leverage * index_df[f"Stock {str(i + 1)} Percent Change"] * index_df["Index LKNN Signal"].shift(1)
        index_df["Cumulative KNN Stock Return"] = (index_df["KNN Stock Percent Change"] + 1).cumprod()
        index_df["Cumulative LKNN Stock Return"] = (index_df["LKNN Stock Percent Change"] + 1).cumprod()

    # Return results
    if knn_params is not None:
        return index_df, cm_test_knn_index, cm_test_lknn_index
    else:
        return index_df

# Create index_df_dict
def create_index_df_dict(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors_group, top, period_short=50, period_long=200, SMA_crossover=True, factor_bear=1, leverage=1, fee_rate=0.0003):
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Initialize an empty dictionary to store the dataframes
    index_df_dict = {}

    # Define the result folder
    result_folder = "Backtest"

    # Define the filename
    filename = os.path.join(result_folder, f"{infix}index_df_dicttop{top}.pkl")

    # Iterate over all factors
    for factors in tqdm(factors_group):
        # Get the equity curve of stocks
        index_df = stocks_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, top, period_short=period_short, period_long=period_long, SMA_crossover=SMA_crossover, factor_bear=factor_bear, leverage=leverage, fee_rate=fee_rate)

        # Convert the list of factors to a tuple
        factors_tuple = tuple(factors)

        # Store the equity curve
        index_df_dict[factors_tuple] = index_df.loc[:, ["Close", "Stock Percent Change", "Cumulative Stock Return"]]

    # Save index_df_dict as a file
    with open(filename, "wb") as file:
        pickle.dump(index_df_dict, file)

# Plot the equity curve of stocks     
def plot_stocks_equity_curve(index_name, index_dict, NASDAQ_all, factors, factors_group, top, group=False, save=False):
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest"

    # Define the filename
    filename = os.path.join(result_folder, f"{infix}index_df_dicttop{top}.pkl")

    # Open the file if it exists
    if os.path.isfile(filename):
        with open(filename, "rb") as file:
            # Retrieve the content of index_df_dict as a dictionary
            index_df_dict = pickle.load(file)
    else:
        print("Error: index_df_dict not found.")

        return None
    
    # Convert the list of factors to a tuple
    factors_tuple = tuple(factors)

    # Get the equity curve of stocks
    index_df = index_df_dict[factors_tuple]

    # Create a figure
    plt.figure(figsize=(10, 6))
    
    # Calculate the percent change of the index
    index_df["Index Percent Change"] = index_df["Close"].pct_change()

    # Calculate the cumulative return of the index
    index_df["Cumulative Index Return"] = (index_df["Index Percent Change"] + 1).cumprod()

    # Plot the cumulative index return and cumulative stock return
    plt.plot(index_df["Cumulative Index Return"], label="S&P 500")
    plt.plot(index_df["Cumulative Stock Return"], label=f"Stocks {factors}")

    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Cumulative return")

    # Set the x limit
    plt.xlim(index_df.index[0], index_df.index[-1])

    # Set the title
    plt.title("Equity curve")

    # Set the legend
    plt.legend(loc="upper left")

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/{infix}equitycurve{factors}top{top}.png", dpi=300)
    else:
        pass
    
    # Show the plot
    plt.show()
    
    # Plot the equity curves of all factors
    if group:
        # Create a figure
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return
        plt.plot(index_df["Cumulative Index Return"], label=index_dict[index_name])

        # Iterate over all factors
        for factors in tqdm(factors_group):
            # Convert the list of factors to a tuple
            factors_tuple = tuple(factors)

            # Retrieve the saved index_df of factors
            index_df = index_df_dict[factors_tuple]

            # Plot the cumulative stock return
            plt.plot(index_df["Cumulative Stock Return"], alpha=0.7)

        # Set the labels
        plt.xlabel("Date")
        plt.ylabel("Cumulative return")

        # Set the x limit
        plt.xlim(index_df.index[0], index_df.index[-1])

        # Set the title
        plt.title("Equity curve")

        # Set the legend
        plt.legend(loc="upper left")

        # Save the plot
        if save:
            plt.savefig(f"Result/Figure/{infix}equitycurvealltop{top}.png", dpi=300)
        else:
            pass

        # Show the plot   
        plt.show()

# Plot the comparison between index and stocks as a 3D graph
def plot_comparison(index_name, index_dict, NASDAQ_all, top, x_values, y_values, z_values, z_index, z_label, save=False):
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Create a figure
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    # Scatter the data points
    scatter = ax.scatter3D(x_values, y_values, z_values, c=z_values, cmap="Blues", alpha=1)

    # Set the labels
    ax.set_xlabel(r"$\mu$ (MVP)")
    ax.set_ylabel(r"$\nu$ (EPS this Y)")

    # Create a cooridnate grid
    xx, yy = np.meshgrid(np.linspace(min(x_values), max(x_values), 10), np.linspace(min(y_values), max(y_values), 10))

    # Define the label
    label = f"{index_dict[index_name]}: {round(z_index, 2)}"

    # Get the maximum x and y values corresponding to max z values
    max_x = x_values[np.argmax(z_values)]
    max_y = y_values[np.argmax(z_values)]
    max_z = np.max(z_values)

    # modify the labels
    max_z_label = f"{round(max_z, 2)}"
    if z_label == "CAGR":
        label += "%"
        max_z_label += "%"

    # Plot the 3D surface
    ax.plot_surface(xx, yy, z_index.reshape(1, -1), color="r", alpha=0.5, label=label)

    # Split the data into train and test data
    x_train, x_test, y_train, y_test, z_train, z_test = train_test_split(x_values, y_values, z_values, test_size=0.2, random_state=42)

    # Fit the random forest regression model on the train data
    reg = RandomForestRegressor()
    reg.fit(np.column_stack((x_train, y_train)), z_train)

    # Predict the values for the test data
    z_pred = reg.predict(np.column_stack((x_test, y_test)))

    # Calculate the R-squared score
    score = r2_score(z_test, z_pred)

    # Fit the regression model on the entire data
    reg.fit(np.column_stack((x_values, y_values)), z_values)

    # Predict the values for the plane
    plane_z = reg.predict(np.column_stack((xx.ravel(), yy.ravel())))

    # Plot the best-fit plane
    ax.plot_surface(xx, yy, plane_z.reshape(xx.shape), color="g", alpha=0.5, label="Best-fit Plane")
    
    # Put a text on the plot
    text = fr"$\mu={max_x}$, $\nu={max_y}$, max {z_label}: {max_z_label}" + "\n" + fr"$R^2$ score: {round(score, 2)}"
    ax.text(0.15, 0.85, max_z, text, color="black")
    
    # Set the title
    plt.title(f"{z_label} comparison with {index_dict[index_name]}")

    # Set the legend
    plt.legend(loc="best")
    
    # Add colour bar
    plt.colorbar(scatter, shrink=0.7).set_label(z_label)

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/{infix}{z_label.replace(' ', '')}comparisontop{top}.png", dpi=300)
    else:
        pass

    # Show the plot
    plt.show()

# Store the statistics of all factors
def save_stats(index_name, index_dict, NASDAQ_all, factors_group, top, reanalyse=False):
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Check if there are pre-existing data
    result_folder = "Backtest"
    filename = os.path.join(result_folder, f"{infix}factors_statstop{top}.npy")

    # Save the data to a file if pre-existing data do not exist or reanalyse is true
    if not os.path.isfile(filename) or reanalyse:
        # Create an empty array to store the data
        factors_stats = np.empty((len(factors_group), 2), dtype=object)

        # Define the filename for index_df_dict
        index_df_dict_filename = f"Backtest/{infix}index_df_dicttop{top}.pkl"

        # Read the file
        with open(index_df_dict_filename, "rb") as file:
            index_df_dict = pickle.load(file)

        # Iterate over all factors
        for i, factors in enumerate(tqdm(factors_group)):
            # Convert the list of factors to a tuple
            factors_tuple = tuple(factors)

            # Get the equity curve
            index_df = index_df_dict[factors_tuple]
            stats = calculate_stats(index_df, len(index_df) / 252, "stock")
            
            # Store the data in the array
            factors_stats[i, 0] = np.array(factors)
            factors_stats[i, 1] = stats

        # Save the data
        np.save(filename, factors_stats)

    print("Statistics saving completed.")

# Compare the statistics between index and stocks
def compare_index_stocks(index_df, index_name, index_dict, NASDAQ_all, factors_stats, top, save=False):
    # Create empty lists to store the data
    x_values = []
    y_values = []
    CAGR_values = []
    sharpe_ratio_values = []
    sortino_ratio_values = []
    stats_index = calculate_stats(index_df, len(index_df) / 252, "index")[1]
    CAGR_index = stats_index[2]
    sharpe_ratio_index = stats_index[4]
    sortino_ratio_index = stats_index[5]
    
    # Iterate over the statistics of all factors
    for factor_stats in factors_stats:
        x, y, _ = factor_stats[0]
        CAGR = factor_stats[1][1][2] * 100
        sharpe_ratio = factor_stats[1][1][4]
        sortino_ratio = factor_stats[1][1][5]
        x_values.append(x)
        y_values.append(y)
        CAGR_values.append(CAGR)
        sharpe_ratio_values.append(sharpe_ratio)
        sortino_ratio_values.append(sortino_ratio)

    # Calculate the proportion of CAGRs higher than CAGR_index
    CAGR_mean = np.mean(CAGR_values)
    CAGR_higher = sum(CAGR > CAGR_index * 100 for CAGR in CAGR_values) / len(CAGR_values)

    # Calculate the proportion of Sharpe ratios higher than sharpe_ratio_index
    sharpe_ratio_mean = np.mean(sharpe_ratio_values)
    sharpe_higher = sum(sharpe_ratio > sharpe_ratio_index for sharpe_ratio in sharpe_ratio_values) / len(sharpe_ratio_values)

    # Calculate the proportion of Sortino ratios higher than sortino_ratio_index
    sortino_ratio_mean = np.mean(sortino_ratio_values)
    sortino_higher = sum(sortino_ratio > sortino_ratio_index for sortino_ratio in sortino_ratio_values) / len(sortino_ratio_values)

    # Print the statistics
    print(f"Mean of screened stocks' CAGR: {round(CAGR_mean, 2)}%.")
    print(f"Mean of screened stocks' Sharpe ratio: {round(sharpe_ratio_mean, 2)}.")
    print(f"Mean of screened stocks' Sortino ratio: {round(sortino_ratio_mean, 2)}.")
    print(f"CAGR of {index_dict[index_name]}: {round(CAGR_index * 100, 2)}%.")
    print(f"Sharpe ratio of {index_dict[index_name]}: {round(sharpe_ratio_index, 2)}.")
    print(f"Sortino ratio of {index_dict[index_name]}: {round(sortino_ratio_index, 2)}.")
    print(f"Proportion of screened stocks' CAGR higher than {index_dict[index_name]}: {round(CAGR_higher * 100, 2)}%.")
    print(f"Proportion of screened stocks' Sharpe ratio higher than {index_dict[index_name]}: {round(sharpe_higher * 100, 2)}%.")
    print(f"Proportion of screened stocks' Sortino ratio higher than {index_dict[index_name]}: {round(sortino_higher * 100, 2)}%.")
    
    # CAGR comparison
    plot_comparison(index_name, index_dict, NASDAQ_all, top, x_values, y_values, CAGR_values, CAGR_index * 100, "CAGR", save=save)

    # Sharpe ratio comparison
    plot_comparison(index_name, index_dict, NASDAQ_all, top, x_values, y_values, sharpe_ratio_values, sharpe_ratio_index, "Sharpe ratio", save=save)

    # Sortino ratio comparison
    plot_comparison(index_name, index_dict, NASDAQ_all, top, x_values, y_values, sortino_ratio_values, sortino_ratio_index, "Sortino ratio", save=save)

# Calculate the equity
def get_equity(month_inv, years, returns, initial=10000, inflation=0.03):
    # Extract the returns
    returns = returns[- years:]
    length = len(returns)

    # Initialize an empty np array to store the equity
    equity_arr = np.zeros(length + 1)

    # Set the initial equity
    equity_arr[0] = initial

    # Iterate over all years
    for i in range(1, length + 1):
        equity = equity_arr[i - 1]
        for j in range(12):
            equity += month_inv
            equity *= (1 + returns[i - 1]) ** (1 / 12)
            equity *= (1 - inflation) ** (1 / 12)
        equity_arr[i] = equity

    return equity_arr
    
# Plot the equity curve of the index
def plot_index_equity_curve(index_name, index_dict, month_inv, years, returns_arr):
    # Get the equity curve
    equity = get_equity(month_inv, years, returns_arr[0])
    final_equity = equity[-1]

    # Calculate the maximum drawdown
    max_drawdown = np.max((np.maximum.accumulate(equity) - equity) / np.maximum.accumulate(equity))

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the equity curve
    plt.plot(np.arange(len(equity)), equity, label="Equity curve", color="black")
    
    # Plot the simulated equity curves
    for i in range(10):
        returns_sim = randomize_array(returns_arr[0])
        equity_sim = get_equity(10000, years, returns_sim)
        plt.plot(equity_sim, linestyle="--", alpha=0.7)
    
    # Put a text on the plot
    plt.text(0.02, 0.7, f"Mean: {returns_arr[1][8] * 100:.2f}%\n"
             f"SD: {returns_arr[1][9] * 100:.2f}%\n"
             f"Skewness: {returns_arr[1][10]:.2f}\n"
             f"Kurtosis: {returns_arr[1][11]:.2f}\n"
             f"Final value: {int(round(final_equity, -3))}\n"
             f"Max drawdown: {max_drawdown * 100:.2f}%", 
             transform=plt.gca().transAxes, fontsize=11)
        
    # Set the labels
    plt.xlabel("Number of years")
    plt.ylabel("Equity")

    # Set the limits
    plt.xlim(xmin=0)
    plt.ylim(ymin=0)

    # Set the title
    plt.title(f"Equity curve for {index_dict[index_name]}")

    # Set the legend
    plt.legend(loc="upper left")

    # Show the plot
    plt.show()

# Record the asset after buy/sell
def record_asset(df):
    df["Asset Buy"] = np.nan
    df["Asset Sell"] = np.nan
    df["Asset Buy"].loc[df["Buy"]] = 1
    df["Asset Buy"].loc[df["Sell"]] = 0
    df["Asset Sell"].loc[df["Sell"]] = 1
    df["Asset Sell"].loc[df["Buy"]] = 0
    df["Asset Buy"] = df["Asset Buy"].ffill().fillna(0)
    df["Asset Sell"] = df["Asset Sell"].ffill().fillna(0)
    df["Asset Buy"] = df["Asset Buy"].shift(1)
    df["Asset Sell"] = df["Asset Sell"].shift(1)

# Extract position
def extract_position(s):
    if s.iloc[0] == 1:
        start_index = [s.index[0], *s.loc[(s == 1) & (s.shift(1) == 0)].index]
    else:
        start_index = [*s.loc[(s == 1) & (s.shift(1) == 0)].index]
    if s.iloc[-1] == 1:
        end_index = [*s.loc[(s.shift(-1) == 0) & (s == 1)].index, s.index[-1]]
    else:
        end_index = [*s.loc[(s.shift(-1) == 0) & (s == 1)].index]
        
    return np.array(start_index), np.array(end_index)

# Calculate the statistics
def calculate_stats(df, years, name):
    # Capitalize the name
    if name[0].islower():
        name = name.capitalize()

    # Calculate the percent change of the index
    df["Index Percent Change"] = df["Close"].pct_change()

    # Calculate the cumulative return of the index
    df["Cumulative Index Return"] = (df["Index Percent Change"] + 1).cumprod()

    # Calculate the total return, peak of return, and compound annual growth rate (CAGR)
    if name == "Strategy":
        df[f"{name} Percent Change"] = (((df["Index Percent Change"] - df["Fee"]) * df["Asset Buy"])).fillna(0)
        df[f"Cumulative {name} Return"] = (df[f"{name} Percent Change"] + 1).cumprod()
    total_return = df[f"Cumulative {name} Return"].iloc[-1]
    return_peak = df[f"Cumulative {name} Return"].max()
    CAGR = total_return ** (1 / years) - 1

    # Calculate the Sharpe ratio
    risk_free_rate = 0
    volatility = df[f"{name} Percent Change"].std() * (252 ** 0.5)
    sharpe_ratio = (df[f"{name} Percent Change"].mean() * 252 - risk_free_rate) / volatility

    # Calculate the Sortino ratio
    downside_deviation = df[f"{name} Percent Change"].where(df[f"{name} Percent Change"] < 0).std()
    sortino_ratio = (df[f"{name} Percent Change"].mean() * 252 - risk_free_rate) / (downside_deviation * (252 ** 0.5))

    # Calculate the Calmar ratio
    max_drawdown = (df[f"Cumulative {name} Return"] / df[f"Cumulative {name} Return"].cummax() - 1).min()
    calmar_ratio = (CAGR / abs(max_drawdown)) if max_drawdown != 0 else np.nan

    # Retrieve the trading dates at 1-year intervals
    dates = [df.index[df.index.searchsorted(date, side="right") - 1] for date in [df.index[-1] - relativedelta(years=i) for i in range(0, round(years))]][::-1]

    # Retrieve the corresponding closing prices
    closes = np.array(df.loc[dates, f"Cumulative {name} Return"].values)
    returns = np.diff(closes) / closes[:-1]

    # Calculate the statistics of yearly return
    returns_mean = np.mean(returns)
    returns_sd = np.std(returns)
    returns_skew = skew(returns)
    returns_kurt = kurtosis(returns)

    # Organize the statistics
    stats = np.array([total_return, return_peak, CAGR, volatility, sharpe_ratio, sortino_ratio, 
                      max_drawdown, calmar_ratio, returns_mean, returns_sd, returns_skew, returns_kurt])
    
    return returns, stats

# Plot the equity curve of strategy
def plot_strategy_equity_curve(index_name, index_dict, df, column="Cumulative Strategy Return"):
    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the cumulative strategy return
    plt.plot(df[column])

    # Plot the buy signals
    plt.scatter(df.index[df["Buy"]], df[column][df["Buy"]], marker="^", color="green", label="Buy")
    
    # Plot the sell signals
    plt.scatter(df.index[df["Sell"]], df[column][df["Sell"]], marker="v", color="red", label="Sell")

    # Set the title
    plt.title(f"Equity curve for {index_dict[index_name]}")
    
    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Equity")

    # Set the x limit
    plt.xlim(df.index[0], df.index[-1])

    # Set the legend
    plt.legend([column] + ["Buy", "Sell"])

    # Show the plot
    plt.show()

# Hang Seng Index (HSI) reaches 40000 by the end of 2024
def HSIstrong(current_date, column=["Close"], show=252*5):
    # Get the price data of HSI
    df = get_df("^HSI", current_date)

    # Retrieve the trading dates until the end of 2024
    dates = pd.date_range(start=df.index[-1], end="2024-12-31", freq="B")

    # Generate the closing prices with random fluctuations
    closes = np.array([df["Close"].iloc[-1] + (40000 - df["Close"].iloc[-1]) / len(dates) * i + np.random.uniform(-1000, 1000) for i in range(len(dates))])

    # Create a dataframe to store the closing prices
    closes_df = pd.DataFrame({"Close": closes}, index=dates)

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the data
    plt.plot(pd.concat([df[column][- show:], closes_df]))

    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Price")

    # Set the x limit
    plt.xlim(df.index[- show], dt.datetime(2024, 12, 31))

    # Set the title
    plt.title("Closing price for Hang Seng Index")

    # Set the legend
    plt.legend(column)

    # Show the plot
    plt.show()

# RSI strategy
def RSI_strategy(df, period=14, column="Close", oversold=30, overbought=70):
    # Calculate the RSI
    RSI(df, period=period, column=column)

    # Extract the buy/sell indices
    buy_conditions = (df["RSI"] <= oversold) & (df["RSI"].shift(1) > oversold)
    sell_conditions = (df["RSI"] >= overbought) & (df["RSI"].shift(1) < overbought)
    buy_indices = df[buy_conditions].index
    sell_indices = df[sell_conditions].index
    buy_indices_int, sell_indices_int = [], []

    # Get the buy/sell signals
    if len(buy_indices) > 0 and len(sell_indices) > 0:
        next_index = "buy" if buy_indices[0] < sell_indices[0] else "sell"
        while len(buy_indices) > 0 and len(sell_indices) > 0:
            if next_index == "buy":
                buy_indices_int.append(buy_indices[0])
                buy_indices = buy_indices[1:]
                sell_indices = sell_indices[sell_indices > buy_indices_int[-1]]
                next_index = "sell"
            else:
                sell_indices_int.append(sell_indices[0])
                sell_indices = sell_indices[1:]
                buy_indices = buy_indices[buy_indices > sell_indices_int[-1]]
                next_index = "buy"
    else:
        print("No buy/sell signal generated.")

    # Get the buy and sell indices
    buy_indices, sell_indices = buy_indices_int, sell_indices_int

    # Delete the intermedate buy and sell indices
    del buy_indices_int, sell_indices_int
    
    # Add the buy/sell signals to the dataframe
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices, "Buy"] = True
    df.loc[sell_indices, "Sell"] = True

    return df

# Test a strategy
def test_strategy(end_date, index_df, index_name, index_dict, years, fee_rate=0.0003):
    # RSI strategy
    index_df = RSI_strategy(index_df)

    # Get the start date
    start_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(years=years)).strftime("%Y-%m-%d")

    # Filter the data
    index_df = index_df[start_date : end_date]

    # Count the number of buy and sell signals
    print("Number of Buy signals:", index_df["Buy"].sum())
    print("Number of Sell signals:", index_df["Sell"].sum())
    record_asset(index_df)
    
    # Set the commission fee
    index_df["Fee"] = float(0)
    buy_start, buy_end = extract_position(index_df["Asset Buy"])
    sell_start, sell_end = extract_position(index_df["Asset Sell"])
    index_df["Fee"].loc[buy_start] = fee_rate
    index_df["Fee"].loc[buy_end] = fee_rate
    index_df["Fee"].loc[sell_start] = fee_rate
    index_df["Fee"].loc[sell_end] = fee_rate

    # Print the statistics
    if years == 1:
        print(f"\nStatistics of the strategy over the past {years} year:")
    else:
        print(f"\nStatistics of the strategy over the past {years} year:")
    print(calculate_stats(index_df, years, "strategy")[1])

    # Plot the equity curve of strategy
    plot_strategy_equity_curve(index_name, index_dict, index_df)

# Main function
def main():
    # Start of the program
    start = dt.datetime.now()

    # Define the paths for the folders
    folders = ["Backtest/Stock dict"]

    # Check if the folders exist, create them if they do not
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)

    # Variables
    HKEX_all = False
    NASDAQ_all = True
    factors = [0.05, 0.95, 0.0]

    # Index
    index_name = "^GSPC"
    index_dict = {"^GSPC": "S&P 500", "QQQ": "QQQ"}

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Get the current date
    current_date = get_current_date(start, index_name)

    # Create the end dates
    end_dates = generate_end_dates(5, current_date)
    end_dates.append(current_date)

    # Create a group of factors
    factors_group = []
    for i, j, k in itertools.product(range(20 + 1), repeat=3):
        if i + j + k == 20:
            factors_group.append([i / 20, j / 20, k / 20])

    # # Create stock_dict for all factors
    # for factors in tqdm(factors_group):
    #     create_stock_dict(end_dates, index_name, index_dict, NASDAQ_all, factors)

    # Create index_df_dict
    top = 5
    # create_index_df_dict(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors_group, top)

    # Plot the equity curve of stocks
    plot_stocks_equity_curve(index_name, index_dict, NASDAQ_all, factors, factors_group, top, group=True, save=True)

    # Save the statistics
    save_stats(index_name, index_dict, NASDAQ_all, factors_group, top, reanalyse=True)

    # Load the statistics of all factors
    factors_stats = np.load(f"Backtest/{infix}factors_statstop{top}.npy", allow_pickle=True)

    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    # Filter the data
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Compare the statistics between index and stocks
    compare_index_stocks(index_df, index_name, index_dict, NASDAQ_all, factors_stats, top, save=True)
    
    # # Get the price data of the index
    # index_df = get_df(index_name, current_date)

    # # Add technical indicators to the data
    # index_df = add_indicator(index_df)

    # # Plot the correlation matrix of technical indicators
    # plot_corr_ta(index_name, index_df)

    # # Plot the equity curve of the index
    # years = 25
    # returns_arr = calculate_stats(index_df, years, "index")
    # plot_index_equity_curve(index_name, index_dict, 10000, years, returns_arr)

    # # HSI reaches 40000 by the end of 2024
    # HSIstrong(current_date)

    # # Test a strategy
    # test_strategy(current_date, index_df, index_name, index_dict, years)

    # # Plot the correlation matrix of stocks
    # stocks = ["^HSI", "3988.HK", "9988.HK", "^GSPC", "QQQ", "META", "NVDA"]
    # plot_corr_stocks(stocks, current_date, 1)

    # # Plot the autocorrelation of stocks
    # stocks = ["^HSI", "0939.HK", "1288.HK", "1398.HK", "3988.HK"]
    # for stock in stocks:
    #     plot_autocorr(stock, current_date, 5)

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()