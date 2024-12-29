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
pd.options.mode.chained_assignment = None
import pickle
from plot import *
from scipy.stats import skew, kurtosis
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from stock_screener import create_stock_dict
from technicals import *
from tqdm import tqdm

# Calculate the equity curve for a momentum strategy
def momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params=None):
    """
    Inputs:
    - end_dates (list): List of end dates for backtesting.
    - current_date (str): The current date for the analysis.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors (list): Factors to consider in the strategy.
    - momentum_params (dict): Parameters for the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Defaults to None.

    Returns:
    - index_df (dataframe): Contains the equity curve and performance metrics.
    - Optional: Confusion matrices for KNN models if "knn_params" is provided.
    """

    # Extract the parameters of the momentum strategy
    SMA_crossover = momentum_params["SMA_crossover"]
    period_short = momentum_params["period_short"]
    period_long = momentum_params["period_long"]
    top = momentum_params["top"]
    fee_rate = momentum_params["fee_rate"]
    leverage = momentum_params["leverage"]
    
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest/Stock dict"

    # Define the filename
    filename = os.path.join(result_folder, f"{infix}stock_dict{factors}.txt")
    
    # Attempt to load the stock dictionary from file
    try:
        if os.path.isfile(filename):
            with open(filename, "r") as file:
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
    if SMA_crossover:
        for i in [period_short, period_long]:
            index_df.loc[:, f"SMA {str(i)}"] = SMA(index_df, i)
            index_df.loc[:, f"EMA {str(i)}"] = EMA(index_df, i)

    # Apply KNN model if parameters are provided
    if knn_params is not None:
        # Delayed import to avoid unnecessary dependencies
        from knn_model import knn_accuracy, preprocess_knn

        # Extract KNN parameters
        k = knn_params["k"]
        lookback = knn_params["lookback"]
        features = knn_params["features"]

        # Preprocess data for the KNN model
        X_train_index, Y_train_index, X_test_index, Y_test_index, df_test_index = preprocess_knn(index_df, end_dates[0], end_dates[-1], lookback, features)

        # Train and evaluate the KNN model
        accuracy_train_knn_index, accuracy_test_knn_index, cm_train_knn_index, cm_test_knn_index, X_train_knn_index, X_test_knn_index = knn_accuracy(X_train_index, Y_train_index, X_test_index, Y_test_index, k)
        accuracy_train_lknn_index, accuracy_test_lknn_index, cm_train_lknn_index, cm_test_lknn_index, X_train_lknn_index, X_test_lknn_index = knn_accuracy(X_train_index, Y_train_index, X_test_index, Y_test_index, k, lorentzian=True)

        # Store KNN signals in the index DataFrame
        index_df.loc[end_dates[0] : end_dates[-1], f"Index KNN Signal"] = X_test_knn_index
        index_df.loc[end_dates[0] : end_dates[-1], f"Index LKNN Signal"] = X_test_lknn_index

    # Filter index data to the backtesting period
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Calculate percent change and cumulative return for the index
    index_df["Percent Change"] = index_df["Close"].pct_change()
    index_df["Cumulative Return"] = (index_df["Percent Change"] + 1).cumprod()

    # Extract the list of stocks for each backtesting period
    stocks_list = [stock_dict[end_date] for end_date in end_dates[:-1]]

    # Iterate over all backtesting periods
    for i in tqdm(range(len(end_dates) - 1)):
        start_date, end_date = end_dates[i], end_dates[i + 1]
        stocks = stocks_list[i]

        # Determine if short SMA is above long SMA or if crossover check is disabled
        if SMA_crossover:
            sma_cond = index_df.loc[start_date, f"SMA {period_short}"] > index_df.loc[start_date, f"SMA {period_long}"]
        else:
            sma_cond = True
        factor = 1 if sma_cond else 0

        # Initialise stock count
        stocks_num = 0
        
        if stocks is not None:
            # Iterate over selected stocks
            for j, stock in enumerate(stocks[:min(top, len(stocks))]):

                # Get the price data of the stock
                df = get_df(stock, current_date)
                
                # Check if the dataframe is empty
                if df is None or df.empty:
                    continue
                    
                try:
                    # Filter the price data of the stock and calculate returns
                    df = df[start_date : end_date]

                    # Calculate the percentage change of the stock
                    df.loc[:, "Percent Change"] = df["Close"].pct_change()
                    df.loc[start_date, "Percent Change"] = (df.loc[start_date, "Close"] - (1 + fee_rate) * df.loc[start_date, "Open"]) / df.loc[start_date, "Open"]

                    # Calculate the cumulative return of the stock
                    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

                    # Update stock count and store results in index dataframe
                    stocks_num += 1
                    index_df.loc[start_date : end_date, f"Stock {str(j + 1)}"] = stock
                    index_df.loc[start_date : end_date, f"Stock {str(j + 1)} Percent Change"] = df["Percent Change"]
                    index_df.loc[start_date : end_date, f"Stock {str(j + 1)} Cumulative Return"] = df["Cumulative Return"]

                except Exception as e:
                    print(f"Error calculating returns for {stock}: {e}.")
                    pass

            # Adjust percent change columns by the number of stocks
            for j in range(min(top, len(stocks))):
                column = f"Stock {j + 1} Percent Change"
                if column in index_df.columns:
                    index_df.loc[start_date : end_date, column] *= factor / top
            
    # Initialise a new column to store the stock returns
    index_df["Stock Percent Change"] = 0

    # Calculate overall stock percent change and cumulative return
    index_df["Stock Percent Change"] = 0
    for i in range(top):
        index_df.fillna({f"Stock {i + 1} Percent Change": 0}, inplace=True)
        index_df["Stock Percent Change"] += leverage * index_df[f"Stock {i + 1} Percent Change"]
    index_df["Cumulative Stock Return"] = (index_df["Stock Percent Change"] + 1).cumprod()

    # Calculate cumulative returns for KNN signals if applicable
    if knn_params is not None:
        index_df["KNN Stock Percent Change"] = 0
        index_df["LKNN Stock Percent Change"] = 0

        for i in range(top):
            index_df["KNN Stock Percent Change"] += leverage * index_df[f"Stock {i + 1} Percent Change"] * index_df["Index KNN Signal"].shift(1)
            index_df["LKNN Stock Percent Change"] += leverage * index_df[f"Stock {i + 1} Percent Change"] * index_df["Index LKNN Signal"].shift(1)
        index_df["Cumulative KNN Stock Return"] = (index_df["KNN Stock Percent Change"] + 1).cumprod()
        index_df["Cumulative LKNN Stock Return"] = (index_df["LKNN Stock Percent Change"] + 1).cumprod()

    # Return results
    if knn_params is not None:
        return index_df, cm_test_knn_index, cm_test_lknn_index
    return index_df

# Create a dictionary to store the returns of all combinations of factors of the momentum strategy
def create_momentum_dict(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors_group, momentum_params, knn_params=None):
    """
    Inputs:
    - end_dates (list): List of end dates for backtesting.
    - current_date (str): The current date for the analysis.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Defaults to None.

    Returns:
    - None: It saves a dictionary.
    """

    # Extract the parameters of the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]
    
    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Initialise an empty dictionary to store the equity curves for each combination of factors
    momentum_dict = {}

    # Define the result folder
    result_folder = "Backtest"

    # Define the filename
    filename = os.path.join(result_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}.pkl")

    # Iterate over all factor combinations
    for factors in tqdm(factors_group):
        # Get the equity curve for the current combination of factors
        index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params=knn_params)

        # Convert the list of factors to a tuple for dictionary key
        factors_tuple = tuple(factors)

        # Store the equity curve in the dictionary
        momentum_dict[factors_tuple] = index_df.loc[:, ["Close", "Stock Percent Change", "Cumulative Stock Return"]]

    # Save the momentum dictionary to a file
    with open(filename, "wb") as file:
        pickle.dump(momentum_dict, file)

# Plot the equity curve of stocks of the momentum strategy
def plot_momentum_equity_curve(index_df, index_name, index_dict, NASDAQ_all, factors, factors_group, momentum_params, plot_group=False, save=False):
    """
    Inputs:
    - index_df (dataframe): Contains the equity curve and performance metrics.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors (list): Factors to consider in the strategy.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the momentum strategy.
    - plot_group (bool): Whether to plot equity curves for all factor combinations. Default to False.
    - save (bool): Whether to save the plot as a file. Default to False.

    Returns:
    - None: It plots an equity curve.
    """

    # Extract the parameters of the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest"

    # Create a figure
    plt.figure(figsize=(10, 6))
    
    # Calculate the percent change of the index
    index_df["Index Percent Change"] = index_df["Close"].pct_change()

    # Calculate the cumulative return of the index
    index_df["Cumulative Index Return"] = (index_df["Index Percent Change"] + 1).cumprod()

    # Plot the cumulative index return and cumulative stock return
    plt.plot(index_df["Cumulative Index Return"], label=index_dict[index_name])
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

    # Adjust the spacing
    plt.tight_layout()

    # Save the plot
    if save:
        plt.savefig(f"Result/Figure/{infix}eqcurve{factors}{years}itv{interval}top{top}.png", dpi=300)
    else:
        pass
    
    # Show the plot
    plt.show()
        
    # Plot equity curves for all factor combinations if requested
    if plot_group:
        # Load the momentum dictionary if it exists
        filename = os.path.join(result_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}.pkl")
        if os.path.isfile(filename):
            with open(filename, "rb") as file:
                momentum_dict = pickle.load(file)
        else:
            print("Error: momentum_dict not found.")
            return None
    
        # Create a figure
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return
        plt.plot(index_df["Cumulative Index Return"], label=index_dict[index_name])

        # Iterate over all factor combinations
        for factors in tqdm(factors_group):
            # Convert the factors to a tuple for dictionary access
            factors_tuple = tuple(factors)

            # Retrieve the equity curve for each factor combination
            index_df = momentum_dict[factors_tuple]

            # Plot the cumulative stock return for the current factor combination
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

        # Adjust the spacing
        plt.tight_layout()

        # Save the plot
        if save:
            plt.savefig(f"Result/Figure/{infix}eqcurveallyears{years}itv{interval}top{top}.png", dpi=300)
        else:
            pass

        # Show the plot   
        plt.show()

# Plot the comparison between an index and stocks as a 3D graph
def plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, x_values, y_values, z_values, z_index, z_label, save=False):
    """
    Inputs:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - momentum_params (dict): Parameters for the momentum strategy.
    - x_values (array-like): Values for the x-axis.
    - y_values (array-like): Values for the y-axis.
    - z_values (array-like): Values for the z-axis.
    - z_index (array-like): Index values for the z-axis.
    - z_label (str): Label for the z-axis.
    - save (bool): Whether to save the plot as a file. Default to False.

    Returns:
    - None: It creates a 3D plot.
    """

    # Extract the parameters of the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

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

    # Create a coordinate grid for the surface plot
    xx, yy = np.meshgrid(np.linspace(min(x_values), max(x_values), 10), np.linspace(min(y_values), max(y_values), 10))

    # Define the label
    label = f"{index_dict[index_name]}: {round(z_index, 2)}"

    # Get the maximum x and y values corresponding to the max z values
    max_x = x_values[np.argmax(z_values)]
    max_y = y_values[np.argmax(z_values)]
    max_z = np.max(z_values)

    # Update the labels based on the z_label
    max_z_label = f"{round(max_z, 2)}"
    if z_label == "CAGR":
        label += "%"
        max_z_label += "%"

    # Plot a surface at z_index
    ax.plot_surface(xx, yy, z_index.reshape(1, -1), color="r", alpha=0.5, label=label)

    # Split the data into training and testing sets
    x_train, x_test, y_train, y_test, z_train, z_test = train_test_split(x_values, y_values, z_values, test_size=0.2, random_state=42)

    # Fit a random forest regression model on the training data
    reg = RandomForestRegressor()
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
    
    # Add text annotations for maximum values and R-squared score
    text = fr"$\mu={max_x}$, $\nu={max_y}$, max {z_label}: {max_z_label}" + "\n" + fr"$R^2$ score: {round(score, 2)}"
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
        plt.savefig(f"Result/Figure/{infix}{z_label.replace(' ', '')}cfyears{years}itv{interval}top{top}.png", dpi=300)
    else:
        pass

    # Show the plot
    plt.show()

# Save the statistics of all factors of the momentum strategy
def save_momentum_stats(index_name, index_dict, NASDAQ_all, factors_group, momentum_params, reanalyse=False):
    """
    Inputs:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the momentum strategy.
    - reanalyse (bool): If True, reanalyze and overwrite existing data. Default to False.

    Returns:
    - None: It saves the statistics as a .pkl file.
    """

    # Extract the parameters of the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder and filename for saving statistics
    result_folder = "Backtest"
    filename = os.path.join(result_folder, f"{infix}factors_statsyears{years}itv{interval}top{top}.npy")

    # Check if pre-existing data exists or if reanalysis is required
    if not os.path.isfile(filename) or reanalyse:
        # Initialise an empty array to store statistics for each factor combination
        factors_stats = np.empty((len(factors_group), 2), dtype=object)

        # Define the filename for the momentum dictionary
        momentum_dict_filename = os.path.join(result_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}.pkl")

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

        # Save the calculated statistics to a file
        np.save(filename, factors_stats)

    print("Statistics of the momentum strategy saved.")

# Compare the statistics between the index and stocks selected by the momentum strategy
def compare_index_momentum(index_df, index_name, index_dict, NASDAQ_all, factors_stats, momentum_params, save=False):
    """
    Inputs:
    - index_df (dataframe): Dataframe containing index data for analysis.
    - index_name (str): Name of the index being analyzed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors_stats (list): Statistics of the momentum strategy.
    - momentum_params (dict): Parameters for the momentum strategy.
    - save (bool): If True, save the comparison plots.
    
    Returns:
    - None
    """

    # Initialise lists to store various statistics
    x_values = []
    y_values = []
    CAGR_values = []
    sharpe_ratio_values = []
    sortino_ratio_values = []

    # Calculate statistics for the index
    stats_index = calculate_stats(index_df, len(index_df) / 252)[1]
    CAGR_index = stats_index[2]
    sharpe_ratio_index = stats_index[4]
    sortino_ratio_index = stats_index[5]
    
    # Iterate over the statistics of all factors to extract values
    for stats in factors_stats:
        mvp_factor, eps_yoy_factor, eps_qoq_factor = stats[0]
        if mvp_factor < 0.5:
            CAGR = stats[1][1][2] * 100 # Extract and convert CAGR to percentage
            sharpe_ratio = stats[1][1][4]
            sortino_ratio = stats[1][1][5]
            x_values.append(mvp_factor)
            y_values.append(eps_yoy_factor)
            CAGR_values.append(CAGR)
            sharpe_ratio_values.append(sharpe_ratio)
            sortino_ratio_values.append(sortino_ratio)

    # Calculate the proportion of CAGRs higher than the index's CAGR
    CAGR_mean = np.mean(CAGR_values)
    CAGR_higher = sum(CAGR > CAGR_index * 100 for CAGR in CAGR_values) / len(CAGR_values)

    # Calculate the proportion of Sharpe ratios higher than the index's Sharpe ratio
    sharpe_ratio_mean = np.mean(sharpe_ratio_values)
    sharpe_higher = sum(sharpe_ratio > sharpe_ratio_index for sharpe_ratio in sharpe_ratio_values) / len(sharpe_ratio_values)

    # Calculate the proportion of Sortino ratios higher than the index's Sortino ratio
    sortino_ratio_mean = np.mean(sortino_ratio_values)
    sortino_higher = sum(sortino_ratio > sortino_ratio_index for sortino_ratio in sortino_ratio_values) / len(sortino_ratio_values)

    # Print the calculated statistics
    print(f"Mean of screened stocks' CAGR: {round(CAGR_mean, 2)}%.")
    print(f"Mean of screened stocks' Sharpe ratio: {round(sharpe_ratio_mean, 2)}.")
    print(f"Mean of screened stocks' Sortino ratio: {round(sortino_ratio_mean, 2)}.")
    print(f"CAGR of {index_dict[index_name]}: {round(CAGR_index * 100, 2)}%.")
    print(f"Sharpe ratio of {index_dict[index_name]}: {round(sharpe_ratio_index, 2)}.")
    print(f"Sortino ratio of {index_dict[index_name]}: {round(sortino_ratio_index, 2)}.")
    print(f"Proportion of screened stocks' CAGR higher than {index_dict[index_name]}: {round(CAGR_higher * 100, 2)}%.")
    print(f"Proportion of screened stocks' Sharpe ratio higher than {index_dict[index_name]}: {round(sharpe_higher * 100, 2)}%.")
    print(f"Proportion of screened stocks' Sortino ratio higher than {index_dict[index_name]}: {round(sortino_higher * 100, 2)}%.")
    
    # Generate and save plots for comparisons
    plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, x_values, y_values, CAGR_values, CAGR_index * 100, "CAGR", save=save)
    plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, x_values, y_values, sharpe_ratio_values, sharpe_ratio_index, "Sharpe ratio", save=save)
    plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, x_values, y_values, sortino_ratio_values, sortino_ratio_index, "Sortino ratio", save=save)

# Calculate the equity based on monthly investments and returns
def get_equity(month_inv, years, returns, initial=10000, inflation=0.03):
    """
    Inputs:
    - month_inv (float): Monthly investment amount.
    - years (int): Number of years to calculate equity for.
    - returns (array-like): Array of monthly returns.
    - initial (float): Initial equity amount. Default to 10000.
    - inflation (float): Annual inflation rate. Default to 0.03.

    Returns:
    - equity_arr (np.ndarray): Array of equity values over the specified period.
    """
    
    # Extract the relevant returns for the specified number of years
    returns = returns[- years:]
    length = len(returns)

    # Initialise an array to store the equity values
    equity_arr = np.zeros(length + 1)

    # Set the initial equity
    equity_arr[0] = initial

    # Calculate equity for each month over the years
    for i in range(1, length + 1):
        equity = equity_arr[i - 1]
        for j in range(12):
            equity += month_inv # Add monthly investment
            equity *= (1 + returns[i - 1]) ** (1 / 12) # Apply monthly return
            equity *= (1 - inflation) ** (1 / 12) # Adjust for inflation
        equity_arr[i] = equity # Store the calculated equity

    return equity_arr
    
# Plot the equity curve for a given index based on monthly investments and returns
def plot_index_equity_curve(index_name, index_dict, month_inv, years, returns_arr):
    """
    Inputs:
    - index_name (str): Name of the index being analyzed.
    - index_dict (dict): Dictionary mapping index names to their respective names.
    - month_inv (float): Monthly investment amount.
    - years (int): Number of years to calculate equity for.
    - returns_arr (array-like): Array of returns and statistics.

    Returns:
    - None: It plots an equity curve.
    """
    
    # Get the equity curve based on provided parameters
    equity = get_equity(month_inv, years, returns_arr[0])
    final_equity = equity[-1]

    # Calculate the maximum drawdown
    max_drawdown = np.max((np.maximum.accumulate(equity) - equity) / np.maximum.accumulate(equity))

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the main equity curve
    plt.plot(np.arange(len(equity)), equity, label="Equity curve", color="black")
    
    # Simulate and plot additional equity curves
    for i in range(10):
        returns_sim = randomize_array(returns_arr[0]) # Randomize the returns
        equity_sim = get_equity(month_inv, years, returns_sim)
        plt.plot(equity_sim, linestyle="--", alpha=0.7)
    
    # Annotate the plot with key statistics
    plt.text(0.02, 0.7, 
             f"Mean: {returns_arr[1][8] * 100:.2f}%\n"
             f"SD: {returns_arr[1][9] * 100:.2f}%\n"
             f"Skewness: {returns_arr[1][10]:.2f}\n"
             f"Kurtosis: {returns_arr[1][11]:.2f}\n"
             f"Final value: {int(round(final_equity, -3))}\n"
             f"Max drawdown: {max_drawdown * 100:.2f}%", 
             transform=plt.gca().transAxes, fontsize=11)
        
    # Set the labels
    plt.xlabel("Number of Years")
    plt.ylabel("Equity")

    # Set the limits
    plt.xlim(xmin=0)
    plt.ylim(ymin=0)

    # Set the title
    plt.title(f"Equity Curve for {index_dict[index_name]}")

    # Set the legend
    plt.legend(loc="upper left")

    # Adjust the spacing
    plt.tight_layout()

    # Show the plot
    plt.show()

# Record the asset after buy/sell signals
def record_asset(df):
    """
    Inputs:
    - df (dataframe): DataFrame containing "Buy" and "Sell" signals.

    Returns:
    - df (dataframe): The modified DataFrame with "Asset Buy" and "Asset Sell" columns.
    """
    
    # Initialise columns for asset buy and sell positions
    df["Asset Buy"] = np.nan
    df["Asset Sell"] = np.nan
    
    # Set buy and sell positions based on signals
    df.loc[df["Buy"], "Asset Buy"] = 1
    df.loc[df["Sell"], "Asset Buy"] = 0
    df.loc[df["Sell"], "Asset Sell"] = 1
    df.loc[df["Buy"], "Asset Sell"] = 0
    
    # Forward fill the asset positions and fill NaNs with 0
    df["Asset Buy"] = df["Asset Buy"].ffill().fillna(0)
    df["Asset Sell"] = df["Asset Sell"].ffill().fillna(0)
    
    # Shift the positions by one to reflect the previous day's position
    df["Asset Buy"] = df["Asset Buy"].shift(1)
    df["Asset Sell"] = df["Asset Sell"].shift(1)

    return df

# Extract positions from the asset signals
def extract_position(s):
    """
    Inputs:
    - s (Series): Series of asset signals (1 for position taken, 0 otherwise).

    Returns:
    - tuple: (start_indices, end_indices)
    """

    # Determine start indices where position is taken
    if s.iloc[0] == 1:
        start_index = [s.index[0], *s.loc[(s == 1) & (s.shift(1) == 0)].index]
    else:
        start_index = [*s.loc[(s == 1) & (s.shift(1) == 0)].index]
    
    # Determine end indices where position is closed
    if s.iloc[-1] == 1:
        end_index = [*s.loc[(s.shift(-1) == 0) & (s == 1)].index, s.index[-1]]
    else:
        end_index = [*s.loc[(s.shift(-1) == 0) & (s == 1)].index]
        
    return np.array(start_index), np.array(end_index)

# Calculate various financial statistics for a given dataframe
def calculate_stats(df, years, name=None):
    """
    Inputs:
    - df (dataframe): Dataframe with a "Close" column.
    - years (int): Number of years for CAGR and other metrics.
    - name (str): Name of the strategy. Default to None.

    Returns:
    - tuple: (yearly returns, stats array)
    """

    # Capitalize name for consistency
    name = name.capitalize() if name and name[0].islower() else name

    # Calculate the percent change and cumulative return
    df["Percent Change"] = df["Close"].pct_change()
    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

    # Strategy-specific calculations and calculate the total return
    if name == "Strategy":
        df[f"{name} Percent Change"] = ((df["Percent Change"] - df["Fee"]) * df["Asset Buy"]).fillna(0)
        df[f"Cumulative {name} Return"] = (df[f"{name} Percent Change"] + 1).cumprod()
        total_return = df[f"Cumulative {name} Return"].iloc[-1]
    else:
        total_return = df["Cumulative Return"].iloc[-1]

    # Calculate peak return and CAGR
    return_peak = df[f"Cumulative {name} Return"].max() if name else df["Cumulative Return"].max()
    CAGR = total_return ** (1 / years) - 1

    # Calculate the Sharpe ratio
    risk_free_rate = 0 # Assuming a risk-free rate of 0 for simplicity
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
    calmar_ratio = (CAGR / abs(max_drawdown)) if max_drawdown != 0 else np.nan

    # Calculate annual returns
    dates = [df.index[df.index.searchsorted(date, side="right") - 1] for date in 
            [df.index[-1] - relativedelta(years=i) for i in range(0, round(years))]][::-1]
    closes = df.loc[dates, f"Cumulative {name} Return" if name else "Cumulative Return"].values
    returns = np.diff(closes) / closes[:-1]

    # Calculate statistics of yearly returns
    returns_mean = np.mean(returns)
    returns_sd = np.std(returns)
    returns_skew = skew(returns)
    returns_kurt = kurtosis(returns)

    # Organize the statistics into an array
    stats = np.array([total_return, return_peak, CAGR, volatility, sharpe_ratio, sortino_ratio, 
                      max_drawdown, calmar_ratio, returns_mean, returns_sd, returns_skew, returns_kurt])
    
    return returns, stats

# Plot the equity curve of a given strategy
def plot_strategy_equity_curve(stock, df, column="Cumulative Strategy Return"):
    """
    Inputs:
    - stock (str): Name of the stock being analysed.
    - df (dataframe): Dataframe containing strategy returns and buy/sell signals.
    - column (str): Column name for cumulative strategy return. Default to "Cumulative Strategy Return").

    Returns:
    - None: It plots an equity curve.
    """

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the cumulative strategy return
    plt.plot(df[column])

    # Plot the buy signals
    plt.scatter(df.index[df["Buy"]], df[column][df["Buy"]], marker="^", color="green", label="Buy")
    
    # Plot the sell signals
    plt.scatter(df.index[df["Sell"]], df[column][df["Sell"]], marker="v", color="red", label="Sell")

    # Set the title
    plt.title(f"Equity curve for {stock}")
    
    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Equity")

    # Set the x limit
    plt.xlim(df.index[0], df.index[-1])

    # Set the legend
    plt.legend([column] + ["Buy", "Sell"])

    # Adjust the spacing
    plt.tight_layout()

    # Show the plot
    plt.show()

# SMA strategy implementation
def SMA_strategy(df, period_buy=200, period_sell=200, column="Close"):
    """
    Inputs:
    - df (dataframe): Dataframe containing price data.
    - period_buy (int): Period of SMA calculation for buy signal. Default to 80.
    - period_sell (int): Period of SMA calculation for sell signal. Default to 200.
    - column (str): Column name for price data. Default to "Close".

    Returns:
    - df (dataframe): Modified Dataframe with "Buy" and "Sell" signals.
    """

    # Calculate the SMA
    df[f"SMA {period_buy}"] = SMA(df, period_buy, column=column)
    df[f"SMA {period_sell}"] = SMA(df, period_sell, column=column)

    # Identify buy and sell conditions based on SMA crossover
    buy_conds = (df["Close"] >= df[f"SMA {period_buy}"]) & (df["Close"].shift(1) < df[f"SMA {period_buy}"].shift(1))
    sell_conds = (df["Close"] <= df[f"SMA {period_sell}"]) & (df["Close"].shift(1) > df[f"SMA {period_sell}"].shift(1))

    # Extract buy and sell indices
    buy_indices = df[buy_conds].index
    sell_indices = df[sell_conds].index
    buy_indices_int, sell_indices_int = [], []

    # Generate buy/sell signals
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

    # Assign the buy/sell signals to the dataframe
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

# RSI strategy implementation
def RSI_strategy(df, period=14, column="Close", oversold=30, overbought=70):
    """
    Inputs:
    - df (dataframe): Dataframe containing price data.
    - period (int): Look-back period for RSI calculation. Default to 14.
    - column (str): Column name for price data. Default to "Close".
    - oversold (float): RSI level indicating oversold conditions. Default to 30.
    - overbought (float): RSI level indicating overbought conditions. Default to 70.

    Returns:
    - df (dataframe): Modified Dataframe with "Buy" and "Sell" signals.
    """

    # Calculate the RSI
    df = RSI(df, period=period, column=column)

    # Identify buy and sell conditions based on RSI levels
    buy_conds = (df["RSI"] <= oversold) & (df["RSI"].shift(1) > oversold)
    sell_conds = (df["RSI"] >= overbought) & (df["RSI"].shift(1) < overbought)

    # Extract buy and sell indices
    buy_indices = df[buy_conds].index
    sell_indices = df[sell_conds].index
    buy_indices_int, sell_indices_int = [], []

    # Generate buy/sell signals
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

    # Assign the buy/sell signals to the dataframe
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

# Test the strategy
def test_strategy(stock, df, end_date, years, fee_rate=0.001):
    """
    Inputs:
    - stock (str): Name of the stock being analysed.
    - df (dataframe): Dataframe containing price data.
    - end_date (str): The end date for the strategy testing in "YYYY-MM-DD" format.
    - years (int): Number of years to test the strategy.
    - fee_rate (float): Transaction fee rate. Default to 0.001.

    Returns:
    - None: It performs calculations and plots an equity curve.
    """

    # Calculate the start date based on the end date and the number of years
    start_date = (dt.datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(years=years)).strftime("%Y-%m-%d")

    # Filter the data
    df = df[df.index >= start_date]

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

    # Print the statistics of the strategy
    print(f"\nStatistics of the strategy over the past {years} year{'s' if years > 1 else ''}:")
    print(calculate_stats(df, years, name="strategy")[1])

    # Print the statistics of Buy and Hold
    print(f"\nStatistics of Buy and Hold over the past {years} year{'s' if years > 1 else ''}:")
    print(calculate_stats(df, years)[1])

    # Plot the equity curve of the strategy
    plot_strategy_equity_curve(stock, df)

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
    HKEX_all = True
    NASDAQ_all = True
    period_hk = 60 # Period for HK stocks
    period_us = 252 # Period for US stocks
    RS = 90
    backtest = True

    # Index
    index_name = "^GSPC"
    index_dict = {"^HSI": "HKEX", "^GSPC": "S&P 500", "^IXIC": "NASDAQ Composite"}

    # Get the infix
    infix = get_infix("^GSPC", index_dict, True)

    # Get the current date
    current_date = get_current_date(start, index_name)

    # Create the end dates
    years = 5
    interval = "1m"
    end_dates = generate_end_dates(years, current_date, interval=interval)
    end_dates.append(current_date)

    # Create a group of factors
    factors_group = [[i / 20, j / 20, k / 20] 
                     for i, j, k in itertools.product(range(21), repeat=3) 
                     if i + j + k == 20]
    
    # Number of stocks to be selected
    top = 5

    # Parameters for backtesting the momentum strategy
    momentum_params = {"years": years, 
                       "interval": interval, 
                       "top": top, 
                       "period_short": 1, 
                       "period_long": 200, 
                       "SMA_crossover": False, 
                       "leverage": 1, 
                       "fee_rate": 0.001}

    # Create the stock dictionary for all factor comnbinations
    recreate_stock_dict = False
    if recreate_stock_dict:
        for factors in tqdm(factors_group):
            create_stock_dict(end_dates, index_name, index_dict, NASDAQ_all, factors, backtest=backtest)
    else:
        # Define the result folder
        result_folder = "Backtest/Stock dict"
        filename = os.path.join(result_folder, f"{infix}stock_dict{factors}.txt")
        if not os.path.exists(filename):
            create_stock_dict(end_dates, index_name, index_dict, NASDAQ_all, factors, backtest=backtest)

    plot_momentum_equity_curve_single = True
    if plot_momentum_equity_curve_single:
        # Calculate the equity curve of a single combination of factors
        factors = [0.15, 0.05, 0.8]
        index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params)
        plot_momentum_equity_curve(index_df, index_name, index_dict, NASDAQ_all, factors, factors_group, momentum_params)

    evaluate_momentum = False
    if evaluate_momentum:
        # Create a dictionary to store the returns of all combinations of factors of the momentum strategy
        create_momentum_dict(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors_group, momentum_params)

        # Plot the equity curve of stocks of the momentum strategy
        plot_momentum_equity_curve(index_df, index_name, index_dict, NASDAQ_all, factors, factors_group, momentum_params, plot_group=True, save=True)

        # Save the statistics of all factors of the momentum strategy
        save_momentum_stats(index_name, index_dict, NASDAQ_all, factors_group, momentum_params)

    show_momentum_stats = False
    if show_momentum_stats:
        # Load the statistics of all factor combinations
        factors_stats = np.load(f"Backtest/{infix}factors_statsyears{years}itv{interval}top{top}.npy", allow_pickle=True)

        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Filter the data
        index_df = index_df[end_dates[0] : end_dates[-1]]

        # Compare the statistics between the index and stocks selected by the momentum strategy
        compare_index_momentum(index_df, index_name, index_dict, NASDAQ_all, factors_stats, momentum_params, save=True)
    
    # Get the price data of the index
    index_df = get_df(index_name, current_date)

    # Add technical indicators to the data
    index_df = add_indicator(index_df)

    # Plot the correlation matrix of technical indicators
    plot_corr_ta(index_name, index_df)

    # Plot the equity curve of the index
    years = 25
    returns_arr = calculate_stats(index_df, years)
    plot_index_equity_curve(index_name, index_dict, 10000, years, returns_arr)

    # Get the price data of bitcoin
    btc_df = get_df("BTC-USD", current_date)
    btc_df = SMA_strategy(btc_df)

    # Test the strategy
    test_strategy("BTC-USD", btc_df, current_date, 10)

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()