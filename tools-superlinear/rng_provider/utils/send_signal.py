import serial
from loguru import logger
# import time

def send_start_signal(port: str, baudrate: int = 115200):
    """
    Sends a start signal to the RNG provider.
    """
    # PORT = "/dev/cu.usbserial-ib2aDeUr1"


    # BAUD = 115200  # Hardcoded as required

    with serial.Serial(port, baudrate, timeout=1) as ser:
        logger.debug(f"Sending start signal (0x42) to {port}...")
        ser.write(bytes([0x42]))
        ser.flush()
        logger.debug("Start signal sent successfully.")
