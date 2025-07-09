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

from loguru import logger
from utils import auto_detect_device


def main():
    """Main entry point"""
    # Run the check
    device = auto_detect_device()
    logger.success(f"Successfully detected a working and configured FPGA device at: {device}")


if __name__ == "__main__":
    main()
