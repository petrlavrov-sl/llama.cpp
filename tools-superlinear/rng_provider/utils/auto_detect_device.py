from loguru import logger
from .list_devices import list_devices
from .check_fpga_conn import check_fpga_conn, DataAlreadyStreamingError, send_stop_signal

def auto_detect_device():
    logger.info("🔍 Auto-detecting FPGA device...")
    devices = list_devices()
    logger.info(f"📋 Found {len(devices)} potential device(s): {devices}")

    if not devices:
        logger.error("❌ No USB/serial devices found at all!")
        logger.info("💡 Try running: ls -la /dev/tty* | grep -E '(USB|usb|serial)'")

    for device in devices:
        logger.info(f"🔍 Checking device: {device}")
        try:
            if check_fpga_conn(device):
                logger.success(f"✅ Found working FPGA at: {device}")
                return device
        except DataAlreadyStreamingError as e:
            logger.warning(f"⚠️  Device {device} is found, but is already streaming data!")
            logger.info(f"🔧 Attempting to stop streaming on {device}...")
            send_stop_signal(device)
            logger.success(f"✅ Stopped streaming, using device: {device}")
            return device
        except Exception as e:
            logger.warning(f"❌ Could not connect to {device}: {type(e).__name__}: {e}")
            continue

    logger.error("❌ No working FPGA device found after checking all devices")
    raise RuntimeError("No working FPGA device found")
