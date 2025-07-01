#!/usr/bin/env python3
"""
Debug script to find and test all serial devices
"""
import glob
import sys
import time

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("❌ PySerial not available")

def list_all_serial_devices():
    """List all available serial devices using multiple methods"""
    print("🔍 Discovering all serial devices...\n")
    
    devices = []
    
    # Method 1: Using serial.tools.list_ports
    if SERIAL_AVAILABLE:
        print("📋 Method 1: Using serial.tools.list_ports")
        ports = serial.tools.list_ports.comports()
        for port in ports:
            print(f"  Device: {port.device}")
            print(f"  Description: {port.description}")
            print(f"  Manufacturer: {port.manufacturer}")
            print(f"  VID:PID: {port.vid}:{port.pid}")
            print(f"  Serial Number: {port.serial_number}")
            print()
            devices.append(port.device)
    
    # Method 2: Using glob patterns (like our current code)
    print("📋 Method 2: Using glob patterns")
    patterns = [
        "/dev/tty.usbserial*",
        "/dev/ttyUSB*", 
        "/dev/ttyACM*",
        "/dev/cu.usbserial*",  # macOS alternative
        "/dev/cu.SLAB_USBtoUART*",  # Silicon Labs
        "/dev/cu.usbmodem*"  # Common on macOS
    ]
    
    for pattern in patterns:
        found = glob.glob(pattern)
        if found:
            print(f"  Pattern {pattern}: {found}")
            devices.extend(found)
        else:
            print(f"  Pattern {pattern}: None")
    
    # Remove duplicates
    devices = list(set(devices))
    print(f"\n🎯 Found {len(devices)} unique serial devices: {devices}")
    return devices


def test_device(device_path, baudrate=921600, test_duration=5):
    """Test a specific device for FPGA data"""
    print(f"\n🧪 Testing device: {device_path}")
    
    try:
        with serial.Serial(device_path, baudrate, timeout=1) as ser:
            print(f"  ✅ Connected successfully at {baudrate} baud")
            print(f"  🔘 Press FPGA button now! Testing for {test_duration} seconds...")
            
            read_bytes = 0
            start_time = time.time()
            
            while (time.time() - start_time) < test_duration:
                data = ser.read(1024)
                if data:
                    read_bytes += len(data)
                    elapsed = time.time() - start_time
                    kbps = (read_bytes * 8) / elapsed / 1000
                    print(f"  📡 Receiving data! Bytes: {read_bytes}, Rate: {kbps:.1f} kbps", end="\r")
                time.sleep(0.1)
            
            if read_bytes > 0:
                print(f"\n  ✅ SUCCESS! Received {read_bytes} bytes from {device_path}")
                return True
            else:
                print(f"\n  ❌ No data received from {device_path}")
                return False
                
    except Exception as e:
        print(f"  ❌ Error testing {device_path}: {e}")
        return False


def main():
    print("🔧 FPGA Serial Device Debug Tool\n")
    
    if not SERIAL_AVAILABLE:
        print("❌ PySerial not installed. Install with: pip install pyserial")
        return
    
    # List all devices
    devices = list_all_serial_devices()
    
    if not devices:
        print("❌ No serial devices found!")
        return
    
    print("\n" + "="*50)
    print("🧪 Testing each device for FPGA data...")
    print("🔘 Make sure to press the FPGA button when prompted!")
    print("="*50)
    
    working_devices = []
    for device in devices:
        if test_device(device):
            working_devices.append(device)
    
    print(f"\n🎯 SUMMARY:")
    print(f"  Total devices found: {len(devices)}")
    print(f"  Working FPGA devices: {len(working_devices)}")
    
    if working_devices:
        print(f"  ✅ FPGA device(s): {working_devices}")
        print(f"\n💡 Use this device with: make run-rng-service FPGA_PORT={working_devices[0]}")
    else:
        print(f"  ❌ No FPGA devices responded")
        print(f"  💡 Try:")
        print(f"     - Check FPGA is powered and programmed")
        print(f"     - Press button when testing")
        print(f"     - Check USB cable connection")


if __name__ == "__main__":
    main() 