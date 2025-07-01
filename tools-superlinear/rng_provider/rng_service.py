#!/usr/bin/env python3
"""
Random Number Generator Service for llama.cpp

This service provides random numbers either from a file or generated on the fly.
It's intended to be used with the llama-rng-provider-api in llama.cpp.
"""

import argparse
import os
import logging
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, HTTPException
import random
import time
import threading
from collections import deque
import struct
import glob

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("⚠️  PySerial not available. Install with: pip install pyserial")

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  Rich not available. Install with: pip install rich")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("rng_service")

app = FastAPI(title="RNG Service")

# Global variables
random_numbers: List[float] = []
current_index: int = 0
use_file = False
use_fpga = False

# FPGA variables
fpga_serial: Optional[serial.Serial] = None
fpga_buffer = deque(maxlen=10000)  # Buffer for FPGA data
fpga_bytes_received = 0
fpga_start_time = time.time()
fpga_throughput_history = deque(maxlen=60)  # FPGA throughput history for plotting

# Speed tracking
request_times = deque(maxlen=100)  # Keep last 100 request timestamps
rps_history = deque(maxlen=60)  # Keep 60 seconds of RPS data for plotting
total_requests = 0
peak_rps = 0.0
start_time = time.time()
console = Console() if RICH_AVAILABLE else None


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {"message": "RNG Service is running"}


@app.get("/random")
async def get_random() -> Dict[str, float]:
    """Get a random number between 0 and 1"""
    global current_index, total_requests
    
    # Track request timing
    current_time = time.time()
    request_times.append(current_time)
    total_requests += 1
    
    if use_fpga:
        # Use FPGA data if available
        if fpga_buffer:
            value = fpga_buffer.popleft()
        else:
            # Fallback to software random if FPGA buffer empty
            value = random.random()
    elif use_file:
        if not random_numbers:
            raise HTTPException(status_code=500, detail="No random numbers available")
        
        if current_index >= len(random_numbers):
            logger.warning("Reached end of random number list, wrapping around")
            current_index = 0
        
        value = random_numbers[current_index]
        current_index += 1
    else:
        # Generate random number on the fly
        value = random.random()
    
    # Only log to file, not console (console shows speed stats instead)
    return {"random": value}


@app.get("/status")
async def status() -> Dict[str, Any]:
    """Get service status"""
    if use_fpga:
        fpga_stats = get_fpga_stats()
        return {
            "mode": "fpga",
            "fpga_connected": fpga_stats["connected"],
            "fpga_throughput_kbps": fpga_stats["throughput_kbps"],
            "fpga_buffer_size": fpga_stats["buffer_size"],
            "fpga_total_data_mb": fpga_stats["total_data_mb"],
            "message": "Using FPGA quantum random number generator"
        }
    elif use_file:
        return {
            "mode": "file",
            "total_numbers": len(random_numbers),
            "current_index": current_index,
            "remaining": len(random_numbers) - current_index if random_numbers else 0,
            "message": "Using pre-generated random numbers from file"
        }
    else:
        return {
            "mode": "software",
            "message": "Generating random numbers on the fly with software PRNG"
        }


def get_speed_stats() -> Dict[str, Any]:
    """Calculate current speed statistics"""
    global peak_rps
    current_time = time.time()
    
    # Calculate requests per second (last 1 second)
    very_recent = [t for t in request_times if current_time - t <= 1.0]
    rps_1s = len(very_recent)
    
    # Calculate requests per second (last 10 seconds)
    recent_requests = [t for t in request_times if current_time - t <= 10.0]
    rps_10s = len(recent_requests) / min(10.0, current_time - start_time)
    
    # Moving average (last 5 seconds)
    very_recent_5s = [t for t in request_times if current_time - t <= 5.0]
    rps_moving_avg = len(very_recent_5s) / min(5.0, current_time - start_time)
    
    # Update peak
    if rps_1s > peak_rps:
        peak_rps = rps_1s
    
    # Add to history for plotting
    rps_history.append(rps_1s)
    
    # Overall average
    total_time = current_time - start_time
    avg_rps = total_requests / total_time if total_time > 0 else 0
    
    # Estimate data rate (assuming ~50 bytes per response)
    bytes_per_request = 50  # JSON response size estimate
    bps_current = rps_1s * bytes_per_request
    bps_avg = avg_rps * bytes_per_request
    
    return {
        "rps_current": rps_1s,
        "rps_10s": rps_10s,
        "rps_moving_avg": rps_moving_avg,
        "rps_avg": avg_rps,
        "rps_peak": peak_rps,
        "bps_current": bps_current,
        "bps_avg": bps_avg,
        "total_requests": total_requests,
        "uptime": total_time
    }


def create_ascii_plot(height: int = 8, width: int = 60) -> str:
    """Create an ASCII plot of request rate over time (like htop)"""
    if len(rps_history) < 2:
        return "📊 [dim]Gathering data...[/dim]"
    
    # Get max value for scaling
    max_val = max(rps_history) if rps_history else 1
    if max_val == 0:
        max_val = 1
    
    # Create the plot
    plot_lines = []
    
    # Scale data to fit height
    scaled_data = []
    for val in list(rps_history)[-width:]:  # Take last `width` data points
        scaled_height = int((val / max_val) * (height - 1))
        scaled_data.append(scaled_height)
    
    # Build the plot from top to bottom
    for row in range(height - 1, -1, -1):
        line = ""
        for col, val in enumerate(scaled_data):
            if val >= row:
                # Use different characters for different intensity
                if val == height - 1:
                    line += "█"  # Full block for peak
                elif val >= height * 0.75:
                    line += "▊"  # High
                elif val >= height * 0.5:
                    line += "▌"  # Medium
                elif val >= height * 0.25:
                    line += "▍"  # Low
                else:
                    line += "▏"  # Very low
            else:
                line += " "
        
        # Add Y-axis labels
        if row == height - 1:
            line += f" {max_val:.0f} req/s"
        elif row == height // 2:
            line += f" {max_val/2:.0f}"
        elif row == 0:
            line += " 0"
        
        plot_lines.append(line)
    
    # Add time axis
    time_axis = "└" + "─" * len(scaled_data) + "┘"
    plot_lines.append(time_axis)
    plot_lines.append(f"📊 Request Rate (last {len(scaled_data)}s)")
    
    return "\n".join(plot_lines)


def create_stats_table() -> Table:
    """Create a rich table with current statistics"""
    stats = get_speed_stats()
    
    # Determine source type for title
    if use_fpga:
        fpga_stats = get_fpga_stats()
        connection_status = "Connected" if fpga_stats["connected"] else "Disconnected"
        title = f"🎲 RNG Service Stats - ⚡ FPGA Source ({connection_status})"
        source_emoji = "⚡"
    elif use_file:
        title = "🎲 RNG Service Stats - 📁 File Source"
        source_emoji = "📁"
    else:
        title = "🎲 RNG Service Stats - 🖥️ Software Source (Fallback)"
        source_emoji = "🖥️"
    
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Current", style="green")
    table.add_column("Peak", style="red")
    table.add_column("Average", style="yellow")
    
    table.add_row("Requests/sec", f"{stats['rps_current']:.1f}", f"{stats['rps_peak']:.1f}", f"{stats['rps_avg']:.1f}")
    table.add_row("Bytes/sec", f"{stats['bps_current']:.0f}", "", f"{stats['bps_avg']:.0f}")
    table.add_row("Total Requests", f"{stats['total_requests']}", "", "")
    table.add_row("Uptime", f"{stats['uptime']:.1f}s", "", "")
    
    # Show FPGA-specific stats
    if use_fpga:
        fpga_stats = get_fpga_stats()
        table.add_row("", "", "", "")  # Separator
        table.add_row("FPGA Source", f"{source_emoji} {'Connected' if fpga_stats['connected'] else 'Disconnected'}", "", "")
        table.add_row("FPGA Throughput", f"{fpga_stats['throughput_kbps']:.1f} kbps", "", f"{fpga_stats['throughput_kibps']:.1f} Kibps")
        table.add_row("FPGA Data Total", f"{fpga_stats['total_data_mb']:.2f} MiB", "", "")
        table.add_row("Buffer Size", f"{fpga_stats['buffer_size']}", "", "")
        table.add_row("Bytes Received", f"{fpga_stats['bytes_received']}", "", "")  # Debug info
    
    # Only show file progress if actually using a file
    elif use_file and random_numbers:
        table.add_row("File Progress", f"{current_index}/{len(random_numbers)}", "", f"{(current_index/len(random_numbers)*100):.1f}%")
    
    return table


def create_fpga_throughput_plot(height: int = 6, width: int = 50) -> str:
    """Create ASCII plot of FPGA throughput over time"""
    if not use_fpga or len(fpga_throughput_history) < 2:
        return "📊 [dim]FPGA not active or gathering data...[/dim]"
    
    # Get max value for scaling
    max_val = max(fpga_throughput_history) if fpga_throughput_history else 1
    if max_val == 0:
        max_val = 1
    
    # Create the plot
    plot_lines = []
    
    # Scale data to fit height
    scaled_data = []
    for val in list(fpga_throughput_history)[-width:]:  # Take last `width` data points
        scaled_height = int((val / max_val) * (height - 1))
        scaled_data.append(scaled_height)
    
    # Build the plot from top to bottom
    for row in range(height - 1, -1, -1):
        line = ""
        for col, val in enumerate(scaled_data):
            if val >= row:
                # Use different characters for different intensity
                if val == height - 1:
                    line += "█"  # Full block for peak
                elif val >= height * 0.75:
                    line += "▊"  # High
                elif val >= height * 0.5:
                    line += "▌"  # Medium
                elif val >= height * 0.25:
                    line += "▍"  # Low
                else:
                    line += "▏"  # Very low
            else:
                line += " "
        
        # Add Y-axis labels
        if row == height - 1:
            line += f" {max_val:.0f} kbps"
        elif row == height // 2:
            line += f" {max_val/2:.0f}"
        elif row == 0:
            line += " 0"
        
        plot_lines.append(line)
    
    # Add time axis
    time_axis = "└" + "─" * len(scaled_data) + "┘"
    plot_lines.append(time_axis)
    plot_lines.append(f"⚡ FPGA Throughput (last {len(scaled_data)}s)")
    
    return "\n".join(plot_lines)


def create_combined_display():
    """Create combined stats table and plot display"""
    from rich.console import Group
    from rich.panel import Panel
    
    # Create stats table
    stats_table = create_stats_table()
    
    # Create plots
    plots = []
    
    # Request rate plot
    request_plot = create_ascii_plot(height=6, width=50)
    plots.append(Panel(request_plot, title="📈 Live Request Rate", border_style="blue"))
    
    # FPGA throughput plot if using FPGA
    if use_fpga:
        fpga_plot = create_fpga_throughput_plot(height=6, width=50)
        plots.append(Panel(fpga_plot, title="⚡ FPGA Source Throughput", border_style="yellow"))
    
    # Combine them
    return Group(stats_table, *plots)


def stats_display_thread():
    """Background thread to display live statistics"""
    if not RICH_AVAILABLE:
        return
        
    # Much faster refresh rate - like the FPGA consumer example
    with Live(create_combined_display(), refresh_per_second=10, console=console) as live:
        while True:
            time.sleep(0.1)  # Update every 100ms instead of 500ms
            live.update(create_combined_display())


def test_fpga_device(device_path: str, baudrate: int = 921600) -> bool:
    """Test if a device is actually an FPGA by trying to read data"""
    try:
        with serial.Serial(device_path, baudrate, timeout=1) as ser:
            # Try to read data for 2 seconds to see if it's an active FPGA
            start_time = time.time()
            read_bytes = 0
            
            while (time.time() - start_time) < 2.0:  # Test for 2 seconds
                data = ser.read(1024)
                if data:
                    read_bytes += len(data)
                    if read_bytes > 100:  # If we get substantial data, it's likely the FPGA
                        return True
                time.sleep(0.1)
            
            return read_bytes > 0  # Any data means it's likely the FPGA
    except Exception:
        return False


def find_serial_port() -> Optional[str]:
    """Find the most likely FPGA serial port"""
    if not SERIAL_AVAILABLE:
        return None
    
    # Expanded patterns including macOS /dev/cu.* variants
    patterns = ["/dev/cu.usbserial*", "/dev/tty.usbserial*", "/dev/ttyUSB*", "/dev/ttyACM*"]
    
    all_devices = []
    for pattern in patterns:
        ports = glob.glob(pattern)
        all_devices.extend(ports)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_devices = []
    for device in all_devices:
        if device not in seen:
            seen.add(device)
            unique_devices.append(device)
    
    if not unique_devices:
        logger.info("🔍 No serial devices found")
        return None
    
    logger.info(f"🔍 Found {len(unique_devices)} serial devices: {unique_devices}")
    
    # First, try to find a device that's currently streaming (button pressed)
    for device in unique_devices:
        logger.info(f"🧪 Quick test: {device} for active FPGA stream...")
        if test_fpga_device(device):
            logger.info(f"🎯 Found actively streaming FPGA: {device}")
            return device
        else:
            logger.info(f"⏸️  No active stream from {device}")
    
    # If no device is actively streaming, use device identification to pick best candidate
    logger.info("💡 No devices actively streaming, using device identification...")
    
    # Use serial.tools.list_ports to get device info for smarter selection
    try:
        import serial.tools.list_ports
        ports_info = serial.tools.list_ports.comports()
        
        # Look for devices that match FPGA characteristics
        for port_info in ports_info:
            if port_info.device in unique_devices:
                # Prioritize devices with FPGA-like characteristics
                if (port_info.description and 
                    ('icebreaker' in port_info.description.lower() or 
                     'fpga' in port_info.description.lower() or
                     port_info.manufacturer and '1bitsquared' in port_info.manufacturer.lower())):
                    logger.info(f"🎯 Selected FPGA device by identification: {port_info.device}")
                    logger.info(f"   Description: {port_info.description}")
                    logger.info(f"   Manufacturer: {port_info.manufacturer}")
                    return port_info.device
    except ImportError:
        pass
    
    # Fallback: prefer /dev/cu.* devices on macOS, then take first available
    cu_devices = [d for d in unique_devices if d.startswith('/dev/cu.')]
    if cu_devices:
        logger.info(f"🎯 Selected first /dev/cu.* device: {cu_devices[0]}")
        return cu_devices[0]
    
    logger.info(f"🎯 Selected first available device: {unique_devices[0]}")
    return unique_devices[0]


def fpga_reader_thread(port: str, baudrate: int = 921600):
    """Background thread to read data from FPGA"""
    global fpga_serial, fpga_bytes_received, fpga_start_time
    
    logger.info(f"🧵 Starting FPGA reader thread for {port}")
    
    try:
        fpga_serial = serial.Serial(port, baudrate, timeout=1)
        logger.info(f"✅ Connected to FPGA on {port} at {baudrate} baud")
        logger.info("🔘 Press the button on the FPGA board to start sending data")
        logger.info("⏳ Waiting for FPGA data stream...")
        
        data_flowing = False
        last_data_time = time.time()
        loop_count = 0
        total_idle_time = 0
        
        while True:
            loop_count += 1
            # Log every 100 loops (about 1 second) to show thread is alive
            if loop_count % 100 == 0:
                logger.info(f"🔄 FPGA reader thread alive (loop {loop_count}), bytes_received: {fpga_bytes_received}")
            data = fpga_serial.read(1024)  # Same chunk size as your consumer
            current_time = time.time()
            
            if data:
                if not data_flowing:
                    logger.info("🚀 FPGA data stream started!")
                    data_flowing = True
                
                fpga_bytes_received += len(data)
                last_data_time = current_time
                
                # Convert bytes to random numbers (0-1 range)
                for byte in data:
                    # Convert byte (0-255) to float (0-1)
                    random_value = byte / 255.0
                    fpga_buffer.append(random_value)
                
                # Update throughput history with current rate
                elapsed = current_time - fpga_start_time
                if elapsed > 0:
                    throughput_kbps = (fpga_bytes_received * 8) / elapsed / 1000
                    fpga_throughput_history.append(throughput_kbps)
            else:
                # No data received - check if stream stopped (like your consumer)
                if data_flowing and (current_time - last_data_time) > 2.0:  # 2 second timeout
                    logger.info("⏸️  FPGA data stream stopped - press button to restart")
                    data_flowing = False
                    # Reset stats when stream stops (like your consumer)
                    fpga_bytes_received = 0
                    fpga_start_time = current_time
                
                # Add 0 to throughput history when no data
                fpga_throughput_history.append(0)
            
            time.sleep(0.01)  # Small delay to prevent excessive CPU usage
                
    except serial.SerialException as e:
        logger.error(f"❌ FPGA serial error: {e}")
        fpga_serial = None
    except Exception as e:
        logger.error(f"❌ FPGA reader error: {e}")
        fpga_serial = None


def get_fpga_stats() -> Dict[str, Any]:
    """Get FPGA throughput statistics"""
    elapsed = time.time() - fpga_start_time
    
    if elapsed > 0 and fpga_bytes_received > 0:
        throughput_kbps = (fpga_bytes_received * 8) / elapsed / 1000
        throughput_kibps = (fpga_bytes_received * 8) / elapsed / 1024
        total_data_mb = fpga_bytes_received / (1024 * 1024)
    else:
        throughput_kbps = 0
        throughput_kibps = 0
        total_data_mb = fpga_bytes_received / (1024 * 1024) if fpga_bytes_received > 0 else 0
    
    # Get recent throughput (last few readings for more responsive display)
    recent_throughput = 0
    if len(fpga_throughput_history) > 0:
        recent_readings = list(fpga_throughput_history)[-5:]  # Last 5 readings
        recent_throughput = sum(recent_readings) / len(recent_readings)
    
    return {
        "throughput_kbps": recent_throughput,  # Use recent throughput for responsiveness
        "throughput_kibps": recent_throughput / 1.024,  # Convert to Kibps
        "total_data_mb": total_data_mb,
        "buffer_size": len(fpga_buffer),
        "connected": fpga_serial is not None and fpga_serial.is_open if fpga_serial else False,
        "bytes_received": fpga_bytes_received
    }


def test_fpga_connection(port: str, baudrate: int = 921600):
    """Test FPGA connection standalone (like your consumer)"""
    print(f"🧪 Testing FPGA connection on {port} at {baudrate} baud")
    
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            print("✅ Connection successful. Waiting for data...")
            print("🔘 Press the button on the FPGA board to start sending data")
            
            read_bytes = 0
            start_time = time.time()
            
            for i in range(300):  # Test for 30 seconds (300 * 0.1s)
                data = ser.read(1024)
                if data:
                    read_bytes += len(data)
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 0:
                        throughput_kbps = (read_bytes * 8) / elapsed_time / 1000
                        throughput_kibps = (read_bytes * 8) / elapsed_time / 1024
                        total_data_mb = read_bytes / (1024 * 1024)
                        
                        print(
                            f"Throughput: {throughput_kbps:.2f} kbps ({throughput_kibps:.2f} Kibps) | "
                            f"Total: {total_data_mb:.2f} MiB | Bytes: {read_bytes}   ",
                            end="\r",
                        )
                else:
                    if read_bytes > 0:
                        print(f"\n⏸️  Data stream stopped. Total received: {read_bytes} bytes")
                        read_bytes = 0
                    start_time = time.time()
                
                time.sleep(0.1)
            
            print(f"\n🏁 Test completed. Final total: {read_bytes} bytes")
                
    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")


def load_random_numbers(file_path: str) -> List[float]:
    """Load random numbers from a file, one per line"""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return []
    
    numbers = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                value = float(line)
                if 0.0 <= value <= 1.0:
                    numbers.append(value)
                else:
                    logger.warning(f"Skipping out-of-range value: {value}")
            except ValueError:
                logger.warning(f"Skipping invalid line: {line}")
    
    logger.info(f"Loaded {len(numbers)} random numbers from {file_path}")
    return numbers


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="RNG Service")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--file", type=str, help="Path to random numbers file (optional)")
    parser.add_argument("--fpga-port", type=str, help="Serial port for FPGA connection (e.g., /dev/tty.usbserial-XXXX)")
    parser.add_argument("--fpga-baudrate", type=int, default=921600, help="Baud rate for FPGA serial connection")
    parser.add_argument("--test-fpga", action="store_true", help="Test FPGA connection only (don't start web server)")
    parser.add_argument("--log-file", type=str, help="Path to save request logs (optional)")
    parser.add_argument("--no-access-logs", action="store_true", help="Disable FastAPI access logs")
    args = parser.parse_args()
    
    global random_numbers
    global current_index
    global use_file
    global use_fpga
    
    # Always try FPGA auto-discovery first (highest priority)
    fpga_port = args.fpga_port
    if fpga_port:
        logger.info(f"🎯 Using forced FPGA port: {fpga_port}")
    elif SERIAL_AVAILABLE:
        logger.info("🔍 Auto-detecting FPGA device...")
        fpga_port = find_serial_port()
    
    if fpga_port and SERIAL_AVAILABLE:
        try:
            use_fpga = True
            logger.info(f"⚡ Setting up FPGA connection at {args.fpga_baudrate} baud")
            
            # Start FPGA reader thread
            fpga_thread = threading.Thread(
                target=fpga_reader_thread, 
                args=(fpga_port, args.fpga_baudrate), 
                daemon=True
            )
            fpga_thread.start()
            logger.info("✅ FPGA reader thread started - using FPGA as RNG source")
            
            # Give the thread a moment to start and connect
            time.sleep(0.5)
            
            # Check if thread is actually running
            if fpga_thread.is_alive():
                logger.info("🔄 FPGA thread is running")
            else:
                logger.error("❌ FPGA thread failed to start")
                use_fpga = False
            
        except Exception as e:
            logger.error(f"❌ Failed to setup FPGA: {e}")
            use_fpga = False
    else:
        if not SERIAL_AVAILABLE:
            logger.warning("⚠️  PySerial not available - cannot use FPGA")
        else:
            logger.info("🔍 No FPGA device found")
    
    # If not using FPGA, try file
    if not use_fpga and args.file:
        logger.info("📁 FPGA not available, trying file source")
        random_numbers = load_random_numbers(args.file)
        if random_numbers:
            use_file = True
            current_index = 0
            logger.info("✅ Using random numbers from file")
        else:
            logger.warning("❌ No valid numbers in file, falling back to software generation")
    
    # Final fallback
    if not use_fpga and not use_file:
        logger.info("🖥️  Using software random number generation (fallback)")
    
    # If testing FPGA only, run simple test and exit
    if args.test_fpga:
        if fpga_port:
            logger.info("🧪 Running FPGA test mode...")
            test_fpga_connection(fpga_port, args.fpga_baudrate)
        else:
            logger.error("❌ No FPGA port found for testing")
        return
    
    # Configure logging
    uvicorn_config = {
        "app": app,
        "host": args.host,
        "port": args.port
    }
    
    if args.log_file:
        # Enable access logs and save to file
        logger.info(f"Request logs will be saved to: {args.log_file}")
        uvicorn_config["access_log"] = True
        uvicorn_config["log_config"] = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "access": {
                    "format": "%(asctime)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "access_file": {
                    "formatter": "access",
                    "class": "logging.FileHandler",
                    "filename": args.log_file,
                },
            },
            "loggers": {
                "uvicorn.access": {
                    "handlers": ["access_file"],
                    "level": "INFO",
                },
            },
        }
    elif args.no_access_logs:
        # Disable access logs completely
        logger.info("Access logging disabled")
        uvicorn_config["access_log"] = False
    
    # Start stats display thread if rich is available
    if RICH_AVAILABLE:
        stats_thread = threading.Thread(target=stats_display_thread, daemon=True)
        stats_thread.start()
        logger.info("Live stats display started")
    
    # Start the server
    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    main()