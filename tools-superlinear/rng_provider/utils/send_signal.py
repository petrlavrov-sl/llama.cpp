import serial
from loguru import logger
# import time

def send_signal(port: str, baudrate: int = 115200, signal: int = 0x42):
    """
    Sends a start signal to the RNG provider.
    for some reason, only 0x42 and only with 115200 baudrate works.
    """
    with serial.Serial(port, baudrate, timeout=1) as ser:
        logger.debug(f"Sending signal ({signal}) to {port}...")
        ser.write(bytes([signal]))
        ser.flush()
        logger.debug("FPGA signal sent successfully.")

def send_start_signal(port: str, baudrate: int = 115200):
    send_signal(port, baudrate, 0x42)

def send_stop_signal(port: str, baudrate: int = 115200):
    send_signal(port, baudrate, 0x42)