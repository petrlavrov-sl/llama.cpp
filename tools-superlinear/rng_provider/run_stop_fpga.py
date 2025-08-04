#!/usr/bin/env python3
"""
A simple wrapper script to send the stop signal to the FPGA.
Takes the device port as a command-line argument.
"""
import sys
import argparse
from loguru import logger

# Add the project root to the path to allow relative imports
sys.path.append('.')

from utils.send_signal import send_stop_signal
from utils.auto_detect_device import auto_detect_device, read_data

# Configure logger to be minimal for scripting purposes
logger.remove()
logger.add(sys.stderr, level="INFO")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send stop signal to FPGA.")
    parser.add_argument("device", type=str, nargs='?', default=None, help="The serial device path (e.g., /dev/tty.usbserial-...). Auto-detects if not provided.")
    args = parser.parse_args()

    device = args.device
    if not device:
        logger.info("No device specified, attempting auto-detection...")
        device = auto_detect_device(already_streaming_ok=True, auto_stop_if_streaming=False)

    if not device:
        logger.error("Could not find FPGA device.")
        sys.exit(1)

    try:
        logger.info(f"Sending STOP signal to {device}...")
        send_stop_signal(device=device)
        data = read_data(device)
        if data:
            raise RuntimeError(f"Failed to stop device {device}- still streaming data")
        logger.success(f"Signal sent to {device}.")
    except Exception as e:
        logger.error(f"Failed to send signal to {device}: {e}")
        sys.exit(1)
