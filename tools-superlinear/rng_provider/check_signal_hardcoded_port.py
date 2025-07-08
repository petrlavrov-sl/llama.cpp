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

import argparse
from loguru import logger
from utils import check_fpga_conn





def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Simple USB Device Data Checker")
    parser.add_argument("--device", type=str, required=True,
                       help="USB device path (e.g., /dev/cu.usbserial-XXXX)")
    parser.add_argument("--baudrate", type=int, default=921600,
                       help="Serial baud rate (default: 921600)")
    parser.add_argument("--timeout", type=float, default=0.1,
                       help="Serial read timeout in seconds (default: 0.1)")
    parser.add_argument("--duration", type=float, default=0.1,
                       help="How long to check for data in seconds (default: 0.1)")

    args = parser.parse_args()

    logger.info("🚨 USB Device Data Checker")
    logger.info("=" * 40)

    # Run the check
    check_fpga_conn(args.device, args.baudrate, args.timeout, args.duration)


if __name__ == "__main__":
    main()
