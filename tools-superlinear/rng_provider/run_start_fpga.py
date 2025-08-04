#!/usr/bin/env python3
"""
A simple wrapper script to send the start signal to the FPGA.
Takes the device port as a command-line argument.
"""
import sys
import argparse
from loguru import logger

# Add the project root to the path to allow relative imports
sys.path.append('.')

from utils.send_signal import send_start_signal
from utils.auto_detect_device import auto_detect_device

# Configure logger to be minimal for scripting purposes
logger.remove()
logger.add(sys.stderr, level="INFO")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send start signal to FPGA.")
    parser.add_argument("device", type=str, nargs='?', default=None, help="The serial device path (e.g., /dev/tty.usbserial-...). Auto-detects if not provided.")
    args = parser.parse_args()

    device_port = args.device
    if not device_port:
        logger.info("No device specified, attempting auto-detection...")
        device_port = auto_detect_device()

    if not device_port:
        logger.error("Could not find FPGA device.")
        sys.exit(1)

    try:
        logger.info(f"Sending START signal to {device_port}...")
        send_start_signal(device=device_port)
        logger.success(f"Signal sent to {device_port}.")
    except Exception as e:
        logger.error(f"Failed to send signal to {device_port}: {e}")
        sys.exit(1)
