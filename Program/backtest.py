# Imports
import ast
import datetime as dt
from dateutil.relativedelta import relativedelta
from functools import partial
from helper_functions import get_current_date, generate_end_dates, get_df, get_infix, randomize_array
import itertools
import matplotlib.pyplot as plt
import multiprocessing
import numpy as np
import os
import pandas as pd
pd.options.mode.chained_assignment = None
import pickle
from plot import *
from scipy.stats import skew, kurtosis
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from stock_screener import create_stock_dict
from technicals import *
from tqdm import tqdm

# Get the labels of the momentum strategy
def get_momentum_labels(momentum_params, knn_params):
    # Extract parameters from the momentum strategy
    sma_crossover = momentum_params["sma_crossover"]
    period_short = momentum_params["period_short"]
    period_long = momentum_params["period_long"]
    cap_threshold = momentum_params["cap_threshold"]
    stoploss_threshold = momentum_params["stoploss_threshold"]

    # Extract KNN parameters
    if knn_params is not None:
        k = knn_params["k"]
        lookback = knn_params["lookback"]

    # Construct the labels
    sma_label = f"sma{period_short}_{period_long}" if sma_crossover else ""
    knn_label = f"k{k}lb{lookback}" if knn_params is not None else ""
    cap_label = f"cap{cap_threshold}" if cap_threshold else ""
    sl_label = f"sl{stoploss_threshold}" if stoploss_threshold else ""

    return sma_label, knn_label, cap_label, sl_label

# Calculate the equity curve of a momentum strategy
def momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params=None, save=False):
    """
    Inputs:
    - end_dates (list): List of end dates for backtesting.
    - current_date (str): The current date.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors (list): Factor combination of the strategy.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Default to None.
    - save (bool): Whether to save the equity curve as a file. Default to False.

    Returns:
    - index_df (dataframe): Contains the equity curve.
    - Optional: Confusion matrices for KNN model if "knn_params" is provided.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]
    sma_crossover = momentum_params["sma_crossover"]
    period_short = momentum_params["period_short"]
    period_long = momentum_params["period_long"]
    stoploss_threshold = momentum_params["stoploss_threshold"]
    fee_rate = momentum_params["fee_rate"]
    leverage = momentum_params["leverage"]

    if factors is not None:
        # Get the infix
        infix = get_infix(index_name, index_dict, NASDAQ_all)

        # Define the result folder
        result_folder = "Backtest/Stock dict"

        # Get the labels of the momentum strategy
        sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

        # Define the filename
        filename = os.path.join(result_folder, f"{infix}stock_dict{factors}{cap_label}.txt")
        
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
    if sma_crossover:
        for i in [period_short, period_long]:
            index_df.loc[:, f"SMA {str(i)}"] = SMA(index_df, i)
            index_df.loc[:, f"EMA {str(i)}"] = EMA(index_df, i)

    # Apply KNN model if parameters are provided
    if knn_params is not None:
        # Import KNN-related functions
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

        # Store KNN signals in the index dataframe
        index_df.loc[end_dates[0] : end_dates[-1], f"Index KNN Signal"] = X_test_knn_index
        index_df.loc[end_dates[0] : end_dates[-1], f"Index LKNN Signal"] = X_test_lknn_index

    # Filter index data to the backtesting period
    index_df = index_df[end_dates[0] : end_dates[-1]]

    # Calculate percent change and cumulative return for the index
    index_df["Percent Change"] = index_df["Close"].pct_change()
    index_df.fillna({"Percent Change": 0}, inplace=True)
    index_df["Cumulative Return"] = (index_df["Percent Change"] + 1).cumprod()

    if factors is not None:
        # Extract the list of stocks for each backtesting period
        stocks_list = [stock_dict[end_date] for end_date in end_dates[:-1]]

        # Iterate over all backtesting periods
        for i in tqdm(range(len(end_dates) - 1)):
            start_date, end_date = end_dates[i], end_dates[i + 1]
            stocks = stocks_list[i]

            # Determine if short SMA is above long SMA or if SMA crossover is disabled
            if sma_crossover:
                sma_cond = index_df.loc[start_date, f"SMA {period_short}"] > index_df.loc[start_date, f"SMA {period_long}"]
            else:
                sma_cond = True
            factor = 1 if sma_cond else 0

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
                        df.loc[start_date, "Percent Change"] = (df.loc[start_date, "Close"] - (1 + fee_rate) * df.loc[start_date, "Open"]) / ((1 + fee_rate) * df.loc[start_date, "Open"])

                        # Calculate the cumulative return of the stock
                        df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

                        # Consider stop loss 
                        sell_date = None
                        stoploss_active = False

                        # If cumulative return drops below the stop loss threshold, exit position
                        if stoploss_threshold is not None:
                            df["Stopped Out"] = df["Cumulative Return"].shift(1) < (1 - stoploss_threshold)

                            # Iterate through the price data to handle stop loss
                            for idx in df.index:
                                if stoploss_active:
                                    # After stopped out, set the percent change to 0
                                    df.loc[idx, "Percent Change"] = 0
                                elif df.loc[idx, "Stopped Out"]:
                                    # Apply stop loss and record the sell date
                                    stoploss_active = True
                                    sell_date = idx
                                    df.loc[idx, "Percent Change"] = ((1 - fee_rate) * df.loc[idx, "Open"] - df["Close"].shift(1).loc[idx]) / df["Close"].shift(1).loc[idx]
                            
                            # If no stop loss, assign the end_date as sell_date
                            if sell_date is None:
                                sell_date = end_date
                                df.loc[sell_date, "Percent Change"] = ((1 - fee_rate) * df.loc[sell_date, "Open"] - df["Close"].shift(1).loc[sell_date]) / df["Close"].shift(1).loc[sell_date]

                            # Calculate the cumulative return of the stock again
                            df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()
                        
                        else:
                            sell_date = end_date
                            df.loc[sell_date, "Percent Change"] = ((1 - fee_rate) * df.loc[sell_date, "Open"] - df["Close"].shift(1).loc[sell_date]) / df["Close"].shift(1).loc[sell_date]

                        # Store results in the index dataframe
                        index_df.loc[start_date : end_date, f"Stock {str(j + 1)}"] = stock
                        index_df.loc[start_date : sell_date, f"Buy Stock {str(j + 1)} Percent Change"] = df["Percent Change"]
                        index_df.loc[sell_date, f"Buy Stock {str(j + 1)} Percent Change"] = 0
                        index_df.loc[sell_date, f"Sell Stock {str(j + 1)} Percent Change"] = df.loc[sell_date, "Percent Change"]
                        index_df.loc[start_date : end_date, f"Stock {str(j + 1)} Cumulative Return"] = df["Cumulative Return"]

                    except Exception as e:
                        print(f"Error calculating returns for {stock}: {e}.")
                        pass

                # Adjust percent change columns by the number of stocks
                for j in range(min(top, len(stocks))):
                    col_buy = f"Buy Stock {j + 1} Percent Change"
                    col_sell = f"Sell Stock {j + 1} Percent Change"
                    for col in [col_buy, col_sell]:
                        if col in index_df.columns:
                            index_df.loc[start_date : end_date, col] *= factor / top
                
        # Calculate overall stock percent change and cumulative return
        index_df["Stock Percent Change"] = 0
        for i in range(top):
            index_df.fillna({f"Buy Stock {i + 1} Percent Change": 0}, inplace=True)
            index_df.fillna({f"Sell Stock {i + 1} Percent Change": 0}, inplace=True)
            index_df["Stock Percent Change"] += leverage * (index_df[f"Buy Stock {i + 1} Percent Change"] + index_df[f"Sell Stock {i + 1} Percent Change"])
        index_df["Cumulative Stock Return"] = (index_df["Stock Percent Change"] + 1).cumprod()

        # Calculate cumulative returns for KNN signals
        if knn_params is not None:
            index_df["KNN Stock Percent Change"] = 0
            index_df["LKNN Stock Percent Change"] = 0

            for i in range(top):
                index_df["KNN Stock Percent Change"] += leverage * (index_df[f"Buy Stock {i + 1} Percent Change"] + index_df[f"Sell Stock {i + 1} Percent Change"]) * index_df["Index KNN Signal"].shift(1)
                index_df["LKNN Stock Percent Change"] += leverage * (index_df[f"Buy Stock {i + 1} Percent Change"] + index_df[f"Sell Stock {i + 1} Percent Change"]) * index_df["Index LKNN Signal"].shift(1)
            index_df["Cumulative KNN Stock Return"] = (index_df["KNN Stock Percent Change"] + 1).cumprod()
            index_df["Cumulative LKNN Stock Return"] = (index_df["LKNN Stock Percent Change"] + 1).cumprod()

    # Define the result folder
    result_folder = "Backtest/Equity curve"

    # Define the filename for saving the index dataframe
    filename = os.path.join(result_folder, f"{infix}eqcurve{factors}years{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.csv")

    # Save the index dataframe
    if not os.path.isfile(filename) or save:
        index_df.to_csv(filename)

    # Return results
    if knn_params is not None:
        return index_df, cm_test_knn_index, cm_test_lknn_index
    return index_df

# Same as momentum_equity_curve, but with inputs other than factors fixed for parallel processing
def partial_momentum_equity_curve(args):
    """
    Inputs:
    - args (tuple): A tuple containing the following elements:
        - end_dates (list): List of end dates for backtesting.
        - current_date (str): The current date.
        - index_name (str): Name of the index being analysed.
        - index_dict (dict): Dictionary mapping index symbols to their respective names.
        - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
        - factors (list): Factors to consider in the strategy.
        - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
        - knn_params (dict, optional): Parameters for the KNN model. Default to None.

    Returns:
    - tuple: A tuple containing:
        - factors (tuple): Factor combination of the strategy.
        - index_df (dataframe): Dataframe with columns ["Close", "Stock Percent Change", "Cumulative Stock Return"].
    """

    end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params = args

    # Calculate the equity curve
    index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params=knn_params)
    
    return tuple(factors), index_df.loc[:, ["Close", "Stock Percent Change", "Cumulative Stock Return"]]

# Create a dictionary to store the returns of all factor combinations for the momentum strategy
def create_momentum_dict(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors_group, momentum_params, knn_params=None, speedup=True):
    """
    Inputs:
    - end_dates (list): List of end dates for backtesting.
    - current_date (str): The current date.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks in NASDAQ.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Default to None.
    - speedup (bool, optional): Whether to use multiprocessing to speed up the process. Default to True.

    Returns:
    - None: This function saves a dictionary of equity curves.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

    # Define the filename for saving the momentum dictionary
    filename = os.path.join(result_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.pkl")

    if speedup:
        # Prepare arguments for processing each factor combination in parallel
        args_list = [(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params) for factors in factors_group]

        # Create a pool of worker processes to fetch the equity curves
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = list(tqdm(pool.imap(partial_momentum_equity_curve, args_list), total=len(args_list)))

        # Create a dictionary to map each factor combination to its equity curve
        momentum_dict = dict(results)

    else:
        # Initialise an empty dictionary to store the equity curves for each combination of factors
        momentum_dict = {}

        # Iterate over all factor combinations
        for factors in tqdm(factors_group):
            # Get the equity curve for the current combination of factors
            index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params=knn_params)

            # Convert the list of factors to a tuple for the dictionary key
            factors_tuple = tuple(factors)

            # Store the equity curve in the dictionary
            momentum_dict[factors_tuple] = index_df.loc[:, ["Close", "Stock Percent Change", "Cumulative Stock Return"]]

    # Save the momentum dictionary to a file
    with open(filename, "wb") as file:
        pickle.dump(momentum_dict, file)

# Plot the equity curve of stocks of the momentum strategy
def plot_momentum_equity_curve(index_df, index_name, index_dict, NASDAQ_all, factors, factors_group, momentum_params, knn_params=None, plot_group=False, save=False):
    """
    Inputs:
    - index_df (dataframe): Contains the equity curve and performance metrics.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks in NASDAQ.
    - factors (list): Factor combination of the strategy.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Default to None.
    - plot_group (bool): Whether to plot equity curves for all factor combinations. Default to False.
    - save (bool): Whether to save the plot as a file. Default to False.

    Returns:
    - None: This function generates and displays a plot of the equity curve.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest"

    # Calculate percent change and cumulative return for the index
    index_df["Percent Change"] = index_df["Close"].pct_change()
    index_df.fillna({"Percent Change": 0}, inplace=True)
    index_df["Cumulative Return"] = (index_df["Percent Change"] + 1).cumprod()

    # Get the labels of the momentum strategy
    sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

    if not plot_group:
        # Create a figure for the single plot
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return and cumulative stock return
        plt.plot(index_df["Cumulative Return"], label=index_dict[index_name])
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
            filename = os.path.join(result_folder, f"Figure/{infix}eqcurve{factors}{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png")
            plt.savefig(filename, dpi=300)
        
        # Show the plot
        plt.show()
        
    else:
        # Load the momentum dictionary if it exists
        momentum_dict_filename = os.path.join(result_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}.pkl")
        if os.path.isfile(momentum_dict_filename):
            with open(momentum_dict_filename, "rb") as file:
                momentum_dict = pickle.load(file)
        else:
            print("Error: momentum_dict not found.")
            return None
    
        # Create a figure for plotting all factor combinations
        plt.figure(figsize=(10, 6))

        # Plot the cumulative index return
        plt.plot(index_df["Cumulative Return"], label=index_dict[index_name])

        # Iterate over all factor combinations
        for factors in tqdm(factors_group):
            # Convert the factors to a tuple for dictionary access
            factors_tuple = tuple(factors)

            # Retrieve the equity curve for the current factor combination
            index_df = momentum_dict[factors_tuple]

            # Plot the cumulative stock return for the current factor combination
            plt.plot(index_df["Cumulative Stock Return"], alpha=0.5)

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
            filename = os.path.join(result_folder, f"Figure/{infix}eqcurveallyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}.png")
            plt.savefig(filename, dpi=300)

        # Show the plot   
        plt.show()

# Plot the comparison between an index and stocks
def plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, x_values, y_values, z_values, z_index, z_label, knn_params=None, regression_model="RandomForest", save=False):
    """
    Inputs:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - x_values (array-like): Values for the x-axis.
    - y_values (array-like): Values for the y-axis.
    - z_values (array-like): Values for the z-axis.
    - z_index (array-like): Index values for the z-axis.
    - z_label (str): Label for the z-axis.
    - knn_params (dict, optional): Parameters for the KNN model. Default to None.
    - regression_model (str): The regression model to use ("LinearRegression", "RandomForest", "SVM"). Default to "RandomForest".
    - save (bool): Whether to save the plot as a file. Default to False.

    Returns:
    - None: This function creates a 3D plot.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

    # Create a 3D figure
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    # Scatter the data points
    scatter = ax.scatter3D(x_values, y_values, z_values, c=z_values, cmap="Blues", alpha=1)

    # Set the labels
    ax.set_xlabel(r"$\mu$ (MVP)")
    ax.set_ylabel(r"$\nu$ (EPS YoY)")

    # Create a coordinate grid for the surface plot
    xx, yy = np.meshgrid(np.linspace(min(x_values), max(x_values), 10), np.linspace(min(y_values), max(y_values), 10))

    # Define the label for the surface
    label = f"{index_dict[index_name]}: {round(z_index, 2)}"

    # Get the maximum x and y values corresponding to the maximum z values
    max_x = x_values[np.argmax(z_values)]
    max_y = y_values[np.argmax(z_values)]
    max_z = np.max(z_values)

    # Update the labels based on the z_label
    max_z_label = f"{round(max_z, 2)}"
    if z_label == "CAGR":
        label += "%"
        max_z_label += "%"

    # Plot a surface at the z_index
    ax.plot_surface(xx, yy, z_index.reshape(1, -1), color="r", alpha=0.5, label=label)

    # Split the data into training and testing sets
    x_train, x_test, y_train, y_test, z_train, z_test = train_test_split(x_values, y_values, z_values, test_size=0.2, random_state=42)

    # Select and fit the regression model based on the input parameter
    if regression_model == "LinearRegression":
        reg = LinearRegression()
    elif regression_model == "RandomForest":
        reg = RandomForestRegressor()
    elif regression_model == "SVM":
        reg = SVR()
    else:
        raise ValueError("Unsupported regression model. Choose 'SVM', 'LinearRegression', or 'RandomForest'.")

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

    # Add a label for the regression model being used
    model_label = {"LinearRegression": "Linear regression", "RandomForest": "Random forest", "SVM": "SVM"}[regression_model]

    # Add text annotations for maximum values and R-squared score
    text = fr"$\mu={max_x}$, $\nu={max_y}$, max {z_label}: {max_z_label}" + "\n" + fr"$R^2$ score: {round(score, 2)} ({model_label})"
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
        filename = os.path.join(result_folder, f"Figure/{infix}{z_label.replace(' ', '')}cfyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.png")
        plt.savefig(filename, dpi=300)

    # Show the plot
    plt.show()

# Save the statistics of all factor combinations of the momentum strategy
def save_momentum_stats(index_name, index_dict, NASDAQ_all, factors_group, momentum_params, knn_params=None, reanalyse=False):
    """
    Inputs:
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors_group (list): List of factor combinations to evaluate.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Default to None.
    - reanalyse (bool): If True, reanalyze and overwrite existing data. Default to False.

    Returns:
    - None: This function saves the statistics as a .npy file.
    """

    # Extract parameters from the momentum strategy
    years = momentum_params["years"]
    interval = momentum_params["interval"]
    top = momentum_params["top"]

    # Get the infix
    infix = get_infix(index_name, index_dict, NASDAQ_all)

    # Define the result folder
    result_folder = "Backtest"

    # Get the labels of the momentum strategy
    sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

    # Define the filename for saving the statistics
    filename = os.path.join(result_folder, f"{infix}factors_statsyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.npy")

    # Check if pre-existing data exists or if reanalysis is required
    if not os.path.isfile(filename) or reanalyse:
        # Initialise an empty array to store statistics for each factor combination
        factors_stats = np.empty((len(factors_group), 2), dtype=object)

        # Define the filename for the momentum dictionary
        momentum_dict_filename = os.path.join(result_folder, f"{infix}momentum_dictyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.pkl")

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
def compare_index_momentum(index_df, index_name, index_dict, NASDAQ_all, factors_stats, momentum_params, knn_params=None, regression_model="RandomForest", save=False):
    """
    Inputs:
    - index_df (dataframe): Dataframe containing index data for analysis.
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - NASDAQ_all (bool): Whether to include all stocks of NASDAQ.
    - factors_stats (list): Statistics of the momentum strategy.
    - momentum_params (dict): Parameters for the backtesting of the momentum strategy.
    - knn_params (dict, optional): Parameters for the KNN model. Default to None.
    - regression_model (str): The regression model to use ("LinearRegression", "RandomForest", "SVM"). Default to "RandomForest".
    - save (bool): If True, save the comparison plots.
    
    Returns:
    - None: This function prints comparison statistics and generates plots.
    """

    # Initialise lists to store various statistics
    xs = []
    ys = []
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
        CAGR = stats[1][1][2] * 100 # Extract and convert CAGR to percentage
        sharpe_ratio = stats[1][1][4]
        sortino_ratio = stats[1][1][5]
        xs.append(mvp_factor)
        ys.append(eps_yoy_factor)
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
    plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, xs, ys, CAGR_values, CAGR_index * 100, "CAGR", knn_params=knn_params, regression_model=regression_model, save=save)
    plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, xs, ys, sharpe_ratio_values, sharpe_ratio_index, "Sharpe ratio", knn_params=knn_params, regression_model=regression_model, save=save)
    plot_comparison(index_name, index_dict, NASDAQ_all, momentum_params, xs, ys, sortino_ratio_values, sortino_ratio_index, "Sortino ratio", knn_params=knn_params, regression_model=regression_model, save=save)

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
    - index_name (str): Name of the index being analysed.
    - index_dict (dict): Dictionary mapping index symbols to their respective names.
    - month_inv (float): Monthly investment amount.
    - years (int): Number of years to calculate equity for.
    - returns_arr (array-like): Array of returns and statistics.

    Returns:
    - None: This function creates a plot for equity curves.
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
    - df (dataframe): Dataframe containing "Buy" and "Sell" signals.

    Returns:
    - df (dataframe): The modified dataframe with "Asset Buy" and "Asset Sell" columns.
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

    # Determine start indices where a position is taken
    if s.iloc[0] == 1:
        start_index = [s.index[0], *s.loc[(s == 1) & (s.shift(1) == 0)].index]
    else:
        start_index = [*s.loc[(s == 1) & (s.shift(1) == 0)].index]
    
    # Determine end indices where a position is closed
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

    # Capitalise name for consistency
    name = name.capitalize() if name and name[0].islower() else name

    # Calculate the percent change and cumulative return of the original dataframe
    df["Percent Change"] = df["Close"].pct_change()
    df["Cumulative Return"] = (df["Percent Change"] + 1).cumprod()

    # Calculate the percent change and cumulative return of the strategy
    if name == "Strategy":
        # Calculate percent change for the strategy, taking fees into account
        df[f"{name} Percent Change"] = ((df["Percent Change"] - df["Fee"]) * df["Asset Buy"]).fillna(0)
        df[f"Cumulative {name} Return"] = (df[f"{name} Percent Change"] + 1).cumprod()
        # Calculate the total return for the strategy
        total_return = df[f"Cumulative {name} Return"].iloc[-1]
    elif name is not None:
        # If a name is provided (but not "Strategy"), use the corresponding cumulative return
        total_return = df[f"Cumulative {name} Return"].iloc[-1]
    else:
        # If no name is provided, use the total return from the original dataframe
        total_return = df["Cumulative Return"].iloc[-1]

    # Calculate the peak return and CAGR
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

    # Organise the statistics into an array
    stats = np.array([total_return, return_peak, CAGR, volatility, sharpe_ratio, sortino_ratio, 
                      max_drawdown, calmar_ratio, returns_mean, returns_sd, returns_skew, returns_kurt])
    
    return returns, stats

# Plot the equity curve of a given strategy
def plot_strategy_equity_curve(stock, df, col="Cumulative Strategy Return"):
    """
    Inputs:
    - stock (str): Name of the stock being analysed.
    - df (dataframe): Dataframe containing strategy returns and buy/sell signals.
    - col (str): Column name of the cumulative strategy return. Default to "Cumulative Strategy Return".

    Returns:
    - None: This function plots an equity curve.
    """

    # Create a figure
    plt.figure(figsize=(10, 6))

    # Plot the cumulative strategy return
    plt.plot(df[col])

    # Plot the buy signals
    plt.scatter(df.index[df["Buy"]], df[col][df["Buy"]], marker="^", color="green", label="Buy")
    
    # Plot the sell signals
    plt.scatter(df.index[df["Sell"]], df[col][df["Sell"]], marker="v", color="red", label="Sell")

    # Set the title
    plt.title(f"Equity curve for {stock}")
    
    # Set the labels
    plt.xlabel("Date")
    plt.ylabel("Equity")

    # Set the x limit
    plt.xlim(df.index[0], df.index[-1])

    # Set the legend
    plt.legend([col] + ["Buy", "Sell"])

    # Adjust the spacing
    plt.tight_layout()

    # Show the plot
    plt.show()

# SMA strategy implementation
def SMA_strategy(df, period_buy=200, period_sell=200, col="Close"):
    """
    Inputs:
    - df (dataframe): Dataframe containing price data.
    - period_buy (int): Period for SMA calculation used to generate buy signals. Default to 200.
    - period_sell (int): Period for SMA calculation used to generate sell signals. Default to 200.
    - col (str): Column name for price data. Default to "Close".

    Returns:
    - df (dataframe): Modified dataframe with "Buy" and "Sell" signals.
    """

    # Calculate the SMA
    df[f"SMA {period_buy}"] = SMA(df, period_buy, column=col)
    df[f"SMA {period_sell}"] = SMA(df, period_sell, column=col)

    # Identify buy and sell conditions based on the price crossing the SMA
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

    # Assign the buy/sell signals to the DataFrame
    df["Buy"] = False
    df["Sell"] = False
    df.loc[buy_indices_int, "Buy"] = True
    df.loc[sell_indices_int, "Sell"] = True

    return df

# RSI strategy implementation
def RSI_strategy(df, period=14, col="Close", oversold=30, overbought=70):
    """
    Inputs:
    - df (dataframe): Dataframe containing price data.
    - period (int): Look-back period for RSI calculation. Default to 14.
    - col (str): Column name for price data. Default to "Close".
    - oversold (float): RSI level indicating oversold conditions. Default to 30.
    - overbought (float): RSI level indicating overbought conditions. Default to 70.

    Returns:
    - df (dataframe): Modified dataframe with "Buy" and "Sell" signals.
    """

    # Calculate the RSI
    df = RSI(df, period=period, column=col)

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
    - end_date (str): The end date for strategy testing in "YYYY-MM-DD" format.
    - years (int): Number of years to test the strategy.
    - fee_rate (float): Transaction fee rate. Default to 0.001.

    Returns:
    - None: This function performs calculations and plots an equity curve.
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

    # Print statistics of buy and hold strategy
    print(f"\nStatistics of buy and hold over the past {years} year{'s' if years > 1 else ''}:")
    print(calculate_stats(df, years)[1])

    # Plot the equity curve of the strategy
    plot_strategy_equity_curve(stock, df)

# Main function
def main():
    # Start of the program
    start = dt.datetime.now()

    # Define the paths for the folders
    folders = ["Backtest", "Backtest/Equity curve", "Backtest/Figure", "Backtest/Stock dict"]

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
    current_date = "2024-12-27"

    # Parameters for backtesting the momentum strategy
    years = 7
    interval = "1w"
    top = 5
    cap_threshold = 1
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
    
    # Parameters of the KNN model
    knn_params = None

    # Get the labels of the momentum strategy
    sma_label, knn_label, cap_label, sl_label = get_momentum_labels(momentum_params, knn_params)

    # Create the end dates
    end_dates = generate_end_dates(7, current_date, interval=interval)
    if years == 5:
        end_dates = [end_date for end_date in end_dates if end_date >= generate_end_dates(5, current_date, interval=interval)[0]]

    # Create a group of factors
    factors_group = [[i / 20, j / 20, k / 20] 
                     for i, j, k in itertools.product(range(21), repeat=3)
                     if i + j + k == 20]

    # Create the stock dictionary for all factor comnbinations
    recreate_stock_dict = False
    for factors in tqdm(factors_group):
        if recreate_stock_dict:
            create_stock_dict(end_dates, index_name, index_dict, NASDAQ_all, factors, cap_threshold=cap_threshold, backtest=backtest)
        else:
            stock_dict_filename = f"Backtest/Stock dict/{infix}stock_dict{factors}{cap_label}.txt"
            if not os.path.isfile(stock_dict_filename):
                create_stock_dict(end_dates, index_name, index_dict, NASDAQ_all, factors, cap_threshold=cap_threshold, backtest=backtest)

    evaluate_momentum = False
    if evaluate_momentum:
        # Create a dictionary to store the returns of all factor combinations for the momentum strategy
        create_momentum_dict(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors_group, momentum_params, knn_params=knn_params)

    # Save the statistics of all factor combinations of the momentum strategy
    save_momentum_stats(index_name, index_dict, NASDAQ_all, factors_group, momentum_params, knn_params=knn_params, reanalyse=True)

    plot_momentum_equity_curve_single = False
    if plot_momentum_equity_curve_single:
        # Plot the equity curve of stocks of the momentum strategy for one factor combination
        factors = [0.05, 0.8, 0.15]
        index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, factors, momentum_params, knn_params=knn_params)
        plot_momentum_equity_curve(index_df, index_name, index_dict, NASDAQ_all, factors, factors_group, momentum_params, knn_params=knn_params)

    plot_momentum_equity_curve_all = True
    if plot_momentum_equity_curve_all:
        # Plot the equity curve of stocks of the momentum strategy for all factor combinations
        index_df = momentum_equity_curve(end_dates, current_date, index_name, index_dict, NASDAQ_all, None, momentum_params, knn_params=knn_params)
        plot_momentum_equity_curve(index_df, index_name, index_dict, NASDAQ_all, None, factors_group, momentum_params, knn_params=knn_params, plot_group=True, save=True)

    show_momentum_stats = True
    if show_momentum_stats:
        # Load the statistics of all factor combinations
        factors_stats = np.load(f"Backtest/{infix}factors_statsyears{years}itv{interval}top{top}{sma_label}{knn_label}{cap_label}{sl_label}.npy", allow_pickle=True)

        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Filter the data
        index_df = index_df[end_dates[0] : end_dates[-1]]

        # Compare the statistics between the index and stocks selected by the momentum strategy
        compare_index_momentum(index_df, index_name, index_dict, NASDAQ_all, factors_stats, momentum_params, knn_params=knn_params, save=True)
    
    index_corr_ta = False
    if index_corr_ta:
        # Get the price data of the index
        index_df = get_df(index_name, current_date)

        # Add technical indicators to the data
        index_df = add_indicator(index_df)

        # Plot the correlation matrix of technical indicators
        plot_corr_ta(index_name, index_df)

    index_equity_curve = False
    if index_equity_curve:
        # Plot the equity curve of the index
        years = 25
        returns_arr = calculate_stats(index_df, years)
        plot_index_equity_curve(index_name, index_dict, 10000, years, returns_arr)

    # Print the end time and total runtime
    end = dt.datetime.now()
    print(end, "\n")
    print("The program used", end - start)

# Run the main function
if __name__ == "__main__":
    main()