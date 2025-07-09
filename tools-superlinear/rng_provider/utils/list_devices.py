import glob
import os

def list_devices():
    """
    List devices - candidates for FPGA usb port

    :return: List[str] - list of device paths
    """

    # Common patterns for USB-to-serial devices
    patterns = [ "/dev/cu.usbserial*", "/dev/tty.usbserial*", "/dev/ttyUSB*","/dev/cu.usbmodem*"]

    devices = []
    for pattern in patterns:
        devices.extend(glob.glob(pattern))

    # Filter out non-existent paths
    devices = [d for d in devices if os.path.exists(d)]

    return devices
