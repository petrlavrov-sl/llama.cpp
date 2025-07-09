#!/usr/bin/env python3
"""
A simple wrapper script to run the auto_detect_device function and
print the result to standard output. This is intended to be called
from shell scripts.
"""
import sys
from loguru import logger

# Add the parent directory to the path to allow relative imports
sys.path.append('.')

from utils.auto_detect_device import auto_detect_device

# Configure logger to be minimal for scripting purposes
logger.remove()
logger.add(sys.stderr, level="WARNING")

if __name__ == "__main__":
    try:
        device = auto_detect_device()
        if device:
            # Print the device path to stdout on success
            print(device)
            sys.exit(0)
        else:
            # Print an error to stderr if no device is found
            logger.error("Auto-detection failed: No responsive FPGA device found.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during device detection: {e}")
        sys.exit(1) 