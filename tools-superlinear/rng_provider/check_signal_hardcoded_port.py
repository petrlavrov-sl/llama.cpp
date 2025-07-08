#!/usr/bin/env python3
"""
Simple USB Device Data Checker

This script reads data from a specified USB device and crashes with an error
if ANY data is detected. Based on the rng_service.py implementation.

Usage:
    python simple_data_checker.py --device /dev/cu.usbserial-XXXX
    python simple_data_checker.py --device /dev/cu.usbserial-XXXX --timeout 10

This script checks fpga workings with hardcoded port

Plan:
1) try reading fpga signal - make sure there's nothing.
2) send start signal to fpga
3) try reading fpga signal - make sure it works.
"""

# FPGA_PORT = "/dev/cu.usbserial-ib2aDeUr1"

import argparse
import sys
import time
from loguru import logger
from utils import send_start_signal

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("❌ ERROR: PySerial not available. Install with: pip install pyserial")
    sys.exit(1)

def read_data(device_path: str, baudrate: int = 921600, timeout: float = 1.0, check_duration: float = 1.0):

    # try:
    with serial.Serial(device_path, baudrate, timeout=timeout) as ser:
        logger.debug("✅ Connection successful")

        start_time = time.time()

        while (time.time() - start_time) < check_duration:
            # Read data in chunks (same as rng_service.py)
            data = ser.read(1024)

            if data:
                return data

            # Small delay to prevent excessive CPU usage
            time.sleep(0.01)

    return None


def check_fpga_conn(device_path: str, baudrate: int = 921600, timeout: float = 1.0, check_duration: float = 1.0):
    """
    Check if device is sending ANY data and crash if it is.

    Args:
        device_path: Path to the USB device (e.g., /dev/cu.usbserial-XXXX)
        baudrate: Serial connection baud rate
        timeout: Serial read timeout in seconds
        check_duration: How long to check for data in seconds
    """
    logger.info(f"🔍 Checking device: {device_path}")
    logger.info(f"📡 Baud rate: {baudrate}")
    logger.info(f"⏱️  Check duration: {check_duration} seconds")
    logger.info(f"🔍 Looking for ANY data...")

    # step 1: read data first, make sure there's nothing there
    data = read_data(device_path, baudrate, timeout, check_duration)
    if data:
        logger.error("❌ ERROR: Data detected before sending start signal!")
        raise RuntimeError("Data detected before sending start signal!")

    # step 2: send start signal
    send_start_signal(device_path)

    # step 3: read data again - make sure it's there
    data = read_data(device_path, baudrate, timeout, check_duration)
    if data:
        logger.debug("✅ Data received after sending start signal.")
    else:
        logger.error("❌ ERROR: No data received after sending start signal!")
        raise RuntimeError("No data received after sending start signal!")





def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Simple USB Device Data Checker")
    parser.add_argument("--device", type=str, required=True,
                       help="USB device path (e.g., /dev/cu.usbserial-XXXX)")
    parser.add_argument("--baudrate", type=int, default=921600,
                       help="Serial baud rate (default: 921600)")
    parser.add_argument("--timeout", type=float, default=1.0,
                       help="Serial read timeout in seconds (default: 1.0)")
    parser.add_argument("--duration", type=float, default=2.0,
                       help="How long to check for data in seconds (default: 2.0)")

    args = parser.parse_args()

    if not SERIAL_AVAILABLE:
        print("❌ PySerial is required but not available")
        sys.exit(1)

    print("🚨 USB Device Data Checker")
    print("=" * 40)

    # Run the check
    check_fpga_conn(args.device, args.baudrate, args.timeout, args.duration)


if __name__ == "__main__":
    main()
