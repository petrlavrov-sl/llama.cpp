#!/usr/bin/env python3
"""
Real-time RNG Visualizer from Log File

This script monitors a log file containing random numbers and provides
a live, interactive CLI dashboard with statistics and visualizations.
"""

import argparse
import os
import time
import threading
from collections import deque
from pathlib import Path
from loguru import logger

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    import statistics
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  Rich not available. Install with: pip install rich loguru")

# Setup loguru logging
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO"
)

class RNGVisualizer:
    def __init__(self, log_file: str, history_size: int = 2000):
        self.log_file = Path(log_file)
        self.history_size = history_size
        
        # Data storage
        self.values = deque(maxlen=history_size)
        self.timestamps = deque(maxlen=history_size)
        self.rates = deque(maxlen=600)  # For consumption rate plot
        
        # State
        self.running = True
        self.last_pos = 0
        self.total_values = 0
        self.start_time = time.time()
        
        if not RICH_AVAILABLE:
            raise RuntimeError("Rich library is required. Please run: pip install rich loguru")
        
        self.console = Console()

    def tail_file(self):
        """Continuously monitor the log file for new values"""
        logger.info(f"Tailing log file: {self.log_file}")
        
        while self.running:
            try:
                if not self.log_file.exists():
                    time.sleep(1)
                    continue

                # Correctly check for file truncation by comparing size
                current_size = self.log_file.stat().st_size
                if current_size < self.last_pos:
                    logger.info("Log file was truncated, restarting from beginning.")
                    self.last_pos = 0

                # Only read if the file has grown
                if current_size > self.last_pos:
                    with self.log_file.open('r') as f:
                        f.seek(self.last_pos)
                        lines = f.readlines()
                        self.last_pos = f.tell()
                        
                        for line in lines:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            
                            try:
                                parts = line.split(',')
                                if len(parts) == 2:
                                    timestamp, value_str = parts
                                    value = float(value_str)
                                    
                                    self.values.append(value)
                                    self.timestamps.append(int(timestamp))
                                    self.total_values += 1

                            except ValueError as e:
                                logger.warning(f"Skipping malformed line: '{line}' ({e})")
                                continue
                else:
                    # If no new data, wait a bit
                    time.sleep(0.1)

            except FileNotFoundError:
                logger.warning(f"Log file disappeared. Waiting for it to reappear at {self.log_file}")
                self.last_pos = 0
                time.sleep(2)
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
                time.sleep(2)

    def get_stats(self) -> dict:
        """Calculate statistics for the current window of values."""
        if not self.values:
            return {}

        values_list = list(self.values)
        
        # Calculate consumption rate
        rate = 0
        if len(self.timestamps) > 1:
            time_span_ms = self.timestamps[-1] - self.timestamps[0]
            if time_span_ms > 0:
                rate = len(self.timestamps) / (time_span_ms / 1000.0)
        self.rates.append(rate)

        return {
            'count': self.total_values,
            'mean': statistics.mean(values_list),
            'stdev': statistics.stdev(values_list) if len(values_list) > 1 else 0.0,
            'min': min(values_list),
            'max': max(values_list),
            'rate': rate,
            'uptime': time.time() - self.start_time,
            'peak_rate': max(self.rates) if self.rates else 0,
        }

    def create_stats_table(self, stats: dict) -> Table:
        """Create a rich table for statistics."""
        table = Table(title="📊 RNG Consumption Stats", show_header=False, border_style="blue")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        if not stats:
            table.add_row("Status", "Waiting for data...")
            return table
            
        table.add_row("Consumption Rate", f"{stats['rate']:.1f} values/sec (Peak: {stats['peak_rate']:.1f})")
        table.add_row("Total Values Consumed", f"{stats['count']:,}")
        table.add_row("Mean", f"{stats['mean']:.6f}")
        table.add_row("Std Dev", f"{stats['stdev']:.6f}")
        table.add_row("Range", f"{stats['min']:.6f} – {stats['max']:.6f}")
        table.add_row("Uptime", f"{stats['uptime']:.1f} s")
        
        # Quality check
        mean_diff = abs(stats['mean'] - 0.5)
        if mean_diff > 0.05:
            table.add_row("[yellow]Quality Warning[/yellow]", f"Mean deviates by {mean_diff:.4f} from 0.5")
        
        return table

    def create_distribution_plot(self, height: int = 8, width: int = 60) -> str:
        """Create an ASCII histogram of the value distribution."""
        if not self.values:
            return "[dim]Gathering data for distribution plot...[/dim]"
        
        bins = [0] * 10
        for value in self.values:
            bin_index = min(int(value * 10), 9)
            bins[bin_index] += 1
            
        max_count = max(bins) if bins else 1
        plot_lines = []
        
        for i, count in enumerate(bins):
            bar_width = int((count / max_count) * (width - 20)) if max_count > 0 else 0
            bar = '█' * bar_width
            percentage = (count / len(self.values)) * 100 if self.values else 0
            plot_lines.append(f"{i/10:.1f}-{(i+1)/10:.1f} | {bar} {count:,} ({percentage:.1f}%)")
            
        return "\n".join(plot_lines)

    def create_rate_plot(self, height: int = 6, width: int = 80) -> str:
        """Create an ASCII plot of consumption rate over time."""
        if len(self.rates) < 2:
            return "[dim]Gathering data for rate plot...[/dim]"
        
        full_data = [0.0] * self.rates.maxlen
        data_list = list(self.rates)
        start_idx = self.rates.maxlen - len(data_list)
        for i, val in enumerate(data_list):
            full_data[start_idx + i] = val
        
        sample_rate = max(1, len(full_data) // width)
        sampled_data = [full_data[i] for i in range(0, len(full_data), sample_rate)][:width]
        
        max_val = max(sampled_data) if sampled_data and max(sampled_data) > 0 else 1
        
        plot_lines = []
        scaled_data = [int((val / max_val) * (height - 1)) for val in sampled_data]
        
        for row in range(height - 1, -1, -1):
            line = ""
            for val in scaled_data:
                if val >= row:
                    line += "█"
                else:
                    line += " "
            
            if row == height - 1:
                line += f" {max_val:.0f} values/s"
            elif row == height // 2:
                line += f" {max_val/2:.0f}"
            elif row == 0:
                line += " 0"
            plot_lines.append(line)
        
        return "\n".join(plot_lines)

    def create_dashboard(self) -> Group:
        """Create the combined dashboard display."""
        stats = self.get_stats()
        
        stats_table = self.create_stats_table(stats)
        dist_plot = self.create_distribution_plot()
        rate_plot = self.create_rate_plot()

        dashboard_group = Group(
            stats_table,
            Panel(dist_plot, title="📈 Value Distribution", border_style="green"),
            Panel(rate_plot, title="📉 Consumption Rate (last 10m)", border_style="yellow")
        )
        return dashboard_group
    
    def run(self):
        """Start the visualizer main loop."""
        logger.info("Starting real-time RNG visualizer...")
        if not self.log_file.exists():
            logger.warning(f"Log file not found at '{self.log_file}'. Waiting for it to be created...")

        # Start the file monitoring thread
        monitor_thread = threading.Thread(target=self.tail_file, daemon=True)
        monitor_thread.start()
        
        try:
            with Live(self.create_dashboard(), refresh_per_second=10, console=self.console) as live:
                while self.running:
                    time.sleep(0.1)
                    live.update(self.create_dashboard())
        except KeyboardInterrupt:
            self.running = False
            logger.info("Shutting down visualizer.")
        except Exception as e:
            self.running = False
            logger.error(f"A display error occurred: {e}")
        
        monitor_thread.join(timeout=1)
        print("Goodbye!")

def main():
    parser = argparse.ArgumentParser(
        description="Real-time visualizer for RNG log files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--file",
        default="rng_values.txt",
        help="Path to the RNG log file to monitor."
    )
    parser.add_argument(
        "--history",
        type=int,
        default=2000,
        help="Number of recent values to use for statistics and plots."
    )
    args = parser.parse_args()

    try:
        visualizer = RNGVisualizer(log_file=args.file, history_size=args.history)
        visualizer.run()
    except Exception as e:
        logger.error(f"Failed to start visualizer: {e}")

if __name__ == "__main__":
    main() 