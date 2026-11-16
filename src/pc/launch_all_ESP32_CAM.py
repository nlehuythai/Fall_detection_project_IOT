import subprocess  # Import the subprocess module to manage new processes
import sys  # Import the sys module to access system-specific parameters and functions
import time  # Import the time module to handle time-related tasks
import signal  # Import the signal module to handle asynchronous events
from pathlib import Path

# List of scripts related to different components of the fall detection system
SCRIPTS = [
    "pc_mqtt_mpu6050_subscriber.py",
    "ESP32_CAM_DETECTION_PUB.py",
    "central_processing.py"
]

processes = []  # Initialize an empty list to store the process objects

# Function to handle shutdown signals
def shutdown(signum, frame):
    print("\nShutting down all processes...")  # Notify that shutdown is initiating
    for p in processes:  # Iterate through the list of running processes
        p.terminate()  # Terminate each process safely
    sys.exit(0)  # Exit the script with a success status code

# Register the shutdown function to handle SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, shutdown)
# Register the shutdown function to handle SIGTERM (Termination signal)
signal.signal(signal.SIGTERM, shutdown)

print("Launching fall detection system...\n")  # Print a message indicating the system is starting

# Loop through each script in the SCRIPTS list to launch them
for script in SCRIPTS:
    print(f"Starting {script}")  # Print which script is being started
    p = subprocess.Popen(  # Start the script as a new subprocess
        [sys.executable, str(Path(__file__).parent / script)],  # Command to execute the script using the current Python executable
        stdout=sys.stdout,  # Direct standard output to the main script's stdout
        stderr=sys.stderr  # Direct standard error to the main script's stderr
    )
    processes.append(p)  # Add the process object to the list of processes
    time.sleep(0.5)  # Pause for 0.5 seconds between launches to avoid race conditions

print("\nAll nodes launched successfully.")  # Notify that all scripts launched successfully
print("Press Ctrl+C to stop.")  # Instruct the user on how to stop the system

# Infinite loop to keep the main script running
while True:
    time.sleep(1)  # Sleep for 1 second in each iteration to reduce CPU usage

