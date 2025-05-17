# Imports
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import argrelextrema

# Constants
m = 1 # Mass
mu = 1 # Constant acceleration
A = 1 # Activation constant

# Initial conditions
x0 = 0
xdot0 = 0
x_r = 10 # Resistance
dt = 0.001
ts = np.arange(0, int(5 * np.sqrt(2 * x_r / mu)), dt)

# Initialise displacement and velocity arrays
xs = np.zeros(len(ts))
xdots = np.zeros(len(ts))
xddots = np.zeros(len(ts))
xs[0] = x0
xdots[0] = xdot0
xddots[0] = mu

def get_xddot(x, xdot, x_r, gamma, k):
    """
    Calculate the acceleration based on the current position and velocity.

    Parameters:
    - x (float): The current position.
    - xdot (float): The current velocity.
    - x_r (float): The reference position.
    - gamma (float): Damping coefficient.
    - k (float): Spring constant.

    Returns:
    - float: The acceleration at the current position and velocity.
    """

    activate = 1 / 2 * (1 + np.tanh(A * (x - x_r)))
    return 1 / m * (m * mu - activate  * (gamma * xdot + k * (x - x_r)))

def find_extrema(arr):
    """
    Find the local maxima and minima of a given array.

    Parameters:
    - arr (array-like): The input array to find extrema from.

    Returns:
    - tuple: A tuple containing:
        - local_max (ndarray): Local maxima values.
        - local_min (ndarray): Local minima values.
        - max_indices (ndarray): Indices of local maxima.
        - min_indices (ndarray): Indices of local minima.
    """

    max_indices = argrelextrema(xs, np.greater)[0]
    min_indices = argrelextrema(xs, np.less)[0]
    local_max = arr[max_indices]
    local_min = arr[min_indices]

    return local_max, local_min, max_indices, min_indices

def motion_rk4(gamma, k, threshold=0.05):
    """
    Compute the displacement and velocity using the 4th order Runge-Kutta method.

    Parameters:
    - gamma (float): Damping coefficient.
    - k (float): Spring constant.
    - threshold (float): Threshold for determining motion change.

    Returns:
    - tuple: A tuple containing:
        - xs (ndarray): Updated displacement values.
        - xdots (ndarray): Updated velocity values.
        - xddots (ndarray): Updated acceleration values.
    """

    # Calculate displacement and velocity for each time step
    for i in range(1, len(ts)):
        x = xs[i-1]
        xdot = xdots[i-1]

        # Runge-Kutta calculations
        k1 = dt * xdot
        k1_dot = dt * get_xddot(x, xdot, x_r, gamma, k)
        k2 = dt * (xdot + 0.5 * k1_dot)
        k2_dot = dt * get_xddot(x + 0.5 * k1, xdot + 0.5 * k1_dot, x_r, gamma, k)
        k3 = dt * (xdot + 0.5 * k2_dot)
        k3_dot = dt * get_xddot(x + 0.5 * k2, xdot + 0.5 * k2_dot, x_r, gamma, k)
        k4 = dt * (xdot + k3_dot)
        k4_dot = dt * get_xddot(x + k3, xdot + k3_dot, x_r, gamma, k)

        # Update displacement and velocity
        xs[i] = (x + (1 / 6) * (k1 + 2 * k2 + 2 * k3 + k4))
        xdots[i] = (xdot + (1 / 6) * (k1_dot + 2 * k2_dot + 2 * k3_dot + k4_dot))
        xddots[i] = get_xddot(x, xdot, x_r, gamma, k)

    xmax, xmin, xmax_indices, xmin_indices = find_extrema(xs)
    # xdotmax, xdotmin, xdotmax_indices, xdotmin_indices = find_extrema(xdots)
    # index = 0
    
    # for i in range(len(xmin_indices)):
    #     if 1 - abs(xdotmin[i] / xdotmax[i]) <= threshold:
    #         index = xmin_indices[i]
    #         break

    # # Change the displacement and velocity for indices after index
    # for i in range(index, len(ts)):
    #     x = xs[i-1]
    #     xdot = xdots[i-1]
    #     k1 = dt * xdot
    #     k1_dot = dt * get_xddot(x, xdot, x_r, 0, 0)
    #     k2 = dt * (xdot + 0.5 * k1_dot)
    #     k2_dot = dt * get_xddot(x + 0.5 * k1, xdot + 0.5 * k1_dot, x_r, 0, 0)
    #     k3 = dt * (xdot + 0.5 * k2_dot)
    #     k3_dot = dt * get_xddot(x + 0.5 * k2, xdot + 0.5 * k2_dot, x_r, 0, 0)
    #     k4 = dt * (xdot + k3_dot)
    #     k4_dot = dt * get_xddot(x + k3, xdot + k3_dot, x_r, 0, 0)
    #     xs[i] = (x + (1 / 6) * (k1 + 2 * k2 + 2 * k3 + k4))
    #     xdots[i] = (xdot + (1 / 6) * (k1_dot + 2 * k2_dot + 2 * k3_dot + k4_dot))
    #     xddots[i] = get_xddot(x, xdot, x_r, 0, 0)

    return xs, xdots, xddots

xs, xdots, xddots = motion_rk4(1, 10)

# Print the first local maximum and first local minimum
xmax, xmin, xmax_indices, xmin_indices = find_extrema(xs)
xmax1 = xmax[0]
xmin1 = xmin[0]
pullback = (xmax1 - xmin1) / xmax1
print(f"First local maximum: {xmax1}")
print(f"First local minimum: {xmin1}")
print(f"Pull back: {- pullback * 100}%")

# Create a figure with two subplots, one for the displacement and one for the velocity/acceleration
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), gridspec_kw={"height_ratios": [5, 1]}, sharex=True)

# Plot the displacement on the top subplot
ax1.plot(ts, xs, label=r"$x$")

# Set the y label of the top subplot
ax1.set_ylabel(r"$x$")

# Set the limits of the top subplot
ax1.set_xlim(xmin=0)
ax1.set_ylim(ymin=0)

# Plot the velocity and acceleration on the bottom subplot
ax2.plot(ts, xdots, label=r"$\dot{x}$")
ax2.plot(ts, xddots, label=r"$\ddot{x}$")

# Set the labels of the bottom suplot
ax2.set_xlabel(r"$t$")
ax2.set_ylabel(r"$\dot{x}$, $\ddot{x}$")

# Set the title
plt.suptitle(r"Motion graph")

# Set the legend
ax1.legend()
ax2.legend()

# Adjust the spacing between subplots
plt.tight_layout()

# Save the plot
plt.savefig("Result/Figure/vcpA1gamma1k10.png", dpi=300)

# Show the plot
plt.show()