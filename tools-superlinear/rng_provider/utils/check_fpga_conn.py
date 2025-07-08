
import time
from loguru import logger
from .send_signal import send_start_signal, send_stop_signal
import serial

class DataAlreadyStreamingError(RuntimeError):
    pass

def read_data(device_path: str, baudrate: int = 921600, timeout: float = 0.1, check_duration: float = 0.1):

    # try:
    with serial.Serial(device_path, baudrate, timeout=timeout) as ser:
        logger.debug(f"Opened connection to {device_path}")

        start_time = time.time()

        while (time.time() - start_time) < check_duration:
            # Read data in chunks (same as rng_service.py)
            data = ser.read(1024)

            if data:
                return data

            # Small delay to prevent excessive CPU usage
            time.sleep(0.01)
    logger.debug(f"No data received after {check_duration} seconds. Closing connection to {device_path}")
    return None


def check_fpga_conn(device_path: str, baudrate: int = 921600, timeout: float = 0.1, check_duration: float = 0.1) -> bool:
    """
    Check if device is sending ANY data and crash if it is.

    Args:
        device_path: Path to the USB device (e.g., /dev/cu.usbserial-XXXX)
        baudrate: Serial connection baud rate
        timeout: Serial read timeout in seconds
        check_duration: How long to check for data in seconds
    """
    logger.info(f"🔍 Checking device: {device_path}")
    logger.debug(f"📡 Baud rate: {baudrate}")
    logger.debug(f"⏱️  Check duration: {check_duration} seconds")
    logger.debug(f"🔍 Looking for ANY data...")

    # step 1: read data first, make sure there's nothing there
    data = read_data(device_path, baudrate, timeout, check_duration)
    if data:
        logger.warning(f"{device_path} is sending data before we sent the start signal!")
        raise DataAlreadyStreamingError("{device_path} is sending data before we sent the start signal! "
                                        "Please disable the signal before running your script.")

    # step 2: send start signal
    send_start_signal(device_path)

    # step 3: read data again - make sure it's there
    data = read_data(device_path, baudrate, timeout, check_duration)
    if data:
        logger.success("Data received after sending start signal.")
    else:
        logger.error("No data received after sending start signal!")
        return False


    # step 4: send stop signal
    send_start_signal(device_path)

    return True
