#!/usr/bin/env python3
"""
FPGA Raw Distribution Checker

This script connects directly to the FPGA, reads a sample of raw random bytes,
and performs a statistical analysis to check the uniformity of the distribution.
This helps verify the health of the hardware random number generator itself.
"""

import argparse
import time
import statistics
import serial
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track

# Import the auto-detection logic from the rng_service
from rng_service import find_serial_port

console = Console()

def run_analysis(port: str, baudrate: int, num_bytes: int):
    """Connects to FPGA, collects data, and runs analysis."""
    console.print(f"🔬 Starting analysis on [cyan]{port}[/cyan] at [yellow]{baudrate}[/yellow] baud.")

    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            # Send a toggle command to start the stream, just in case it's off
            console.print("▶️ Sending toggle command to start data stream...")
            ser.write(b't')
            time.sleep(0.1) # Give the FPGA a moment to respond
            ser.flushInput() # Clear any old data in the buffer

            # Collect the random bytes
            console.print(f"📦 Collecting [bold green]{num_bytes:,}[/bold green] random bytes from FPGA...")

            random_bytes = []
            for _ in track(range(num_bytes), description="Reading bytes..."):
                byte = ser.read(1)
                if not byte:
                    console.print("\n[bold red]Error:[/bold red] Timed out waiting for data from FPGA.")
                    console.print("Please ensure the FPGA is programmed and streaming data.")
                    return
                random_bytes.append(byte[0])

            # Send a toggle command to stop the stream
            console.print("⏹️ Sending toggle command to stop data stream...")
            ser.write(b't')

    except serial.SerialException as e:
        console.print(f"[bold red]Serial Error:[/bold red] {e}")
        console.print("Please check the port and ensure no other process is using it.")
        return
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
        return

    console.print("\n\n[bold green]✅ Data collection complete.[/bold green] Analyzing distribution...")
    time.sleep(1)

    # --- Analysis ---

    # 1. Basic Statistics
    stats_table = Table(title="📊 Raw Byte Value Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="yellow")

    mean = statistics.mean(random_bytes)
    stdev = statistics.stdev(random_bytes)

    stats_table.add_row("Total Samples", f"{len(random_bytes):,}")
    stats_table.add_row("Mean", f"{mean:.4f}")
    stats_table.add_row("Median", f"{statistics.median(random_bytes):.4f}")
    stats_table.add_row("Standard Deviation", f"{stdev:.4f}")
    stats_table.add_row("Min Value", str(min(random_bytes)))
    stats_table.add_row("Max Value", str(max(random_bytes)))

    # Theoretical values for a perfect uniform distribution of bytes
    theoretical_mean = 255 / 2
    theoretical_stdev = (((255**2) - 1) / 12)**0.5

    stats_table.add_row("Theoretical Mean", f"{theoretical_mean:.4f}")
    stats_table.add_row("Theoretical Std Dev", f"{theoretical_stdev:.4f}")

    console.print(stats_table)

    # 2. Distribution Histogram
    num_bins = 16
    bin_size = 256 / num_bins
    bins = [0] * num_bins

    for byte_val in random_bytes:
        bin_index = min(int(byte_val / bin_size), num_bins - 1)
        bins[bin_index] += 1

    max_count = max(bins) if bins else 1

    hist_str = ""
    for i, count in enumerate(bins):
        bar_width = int((count / max_count) * 60) if max_count > 0 else 0
        bar = '█' * bar_width
        percentage = (count / num_bytes) * 100
        range_start = int(i * bin_size)
        range_end = int((i + 1) * bin_size) - 1
        hist_str += f"{range_start:3d}-{range_end:3d} | {bar:<60} | {count:>{len(str(num_bytes))},} ({percentage:.2f}%)\n"

    console.print(Panel(hist_str, title="📈 Raw Byte Distribution (16 Bins)", border_style="green"))

    # 3. Final Verdict
    mean_deviation = abs(mean - theoretical_mean) / theoretical_mean
    stdev_deviation = abs(stdev - theoretical_stdev) / theoretical_stdev

    if mean_deviation > 0.05 or stdev_deviation > 0.05:
        console.print("[bold yellow]Verdict:[/bold yellow] The distribution appears to be [bold red]NON-UNIFORM[/bold red].")
        console.print("The mean and/or standard deviation are more than 5% off from the theoretical values for a uniform distribution.")
    else:
        console.print("[bold green]Verdict:[/bold green] The distribution appears to be reasonably [bold cyan]UNIFORM[/bold cyan].")


def main():
    parser = argparse.ArgumentParser(
        description="Check the raw output distribution of the FPGA RNG.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--port",
        default=None,
        help="The serial port of the FPGA. If not provided, will attempt auto-detection."
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=921600,
        help="Baud rate for the serial connection."
    )
    parser.add_argument(
        "-n", "--num-bytes",
        type=int,
        default=100000,
        help="Number of random bytes to sample for the analysis."
    )
    args = parser.parse_args()

    port_to_use = args.port
    if not port_to_use:
        console.print("🔌 No port specified, attempting to auto-detect FPGA...")
        port_to_use = find_serial_port()

    if port_to_use:
        run_analysis(port_to_use, args.baudrate, args.num_bytes)
    else:
        console.print("[bold red]Error:[/bold red] Could not find FPGA serial port. Please specify it with the --port option.")

if __name__ == "__main__":
    main()
