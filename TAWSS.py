def calculate_TAWSS(WSS_vector, time_period):
    """
    Calculate the Time-Averaged Wall Shear Stress (TAWSS).

    Parameters:
    - WSS_vector: List of instantaneous Wall Shear Stress values over time.
    - time_period: Total time period over which the WSS data is collected (in seconds).

    Returns:
    - TAWSS: The calculated Time-Averaged Wall Shear Stress (TAWSS) in Pa.
    """
    # Calculate the absolute value of WSS over time
    absolute_WSS = [abs(wss) for wss in WSS_vector]

    # Calculate the integral of absolute WSS over time
    integral_absolute_WSS = sum(absolute_WSS)

    # Calculate TAWSS
    TAWSS = integral_absolute_WSS / time_period
 
    return TAWSS

# Example usage:
WSS_vector = [0.1, -0.2, 0.3, -0.4, 0.5]  # Replace with your WSS data
time_period = 10  # Replace with the total time period in seconds
TAWSS = calculate_TAWSS(WSS_vector, time_period)
print(f"TAWSS: {TAWSS} Pa")
