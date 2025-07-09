from loguru import logger
from .list_devices import list_devices
from .check_fpga_conn import check_fpga_conn, DataAlreadyStreamingError, send_stop_signal

def auto_detect_device():
    logger.debug("Auto-detecting device...")
    devices = list_devices()
    logger.debug(f"Found {len(devices)} devices: {devices}")
    for device in devices:
        try:
            if check_fpga_conn(device):
                return device
        except DataAlreadyStreamingError as e:
            logger.warning(f"Device {device} is found, but is already streaming data! You may need to disable the rng generator before starting the job to avoid errors.")
            logger.info(f"Stopping device {device}...")
            send_stop_signal(device)
            return device
        except Exception as e:
            logger.debug(f"Could not test device {device}: {e}")
            continue
    raise RuntimeError("No working FPGA device found")
