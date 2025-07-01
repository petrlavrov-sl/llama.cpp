#!/usr/bin/env python3
"""
Random Number Generator Service for llama.cpp

This service provides random numbers either from a file or generated on the fly.
It's intended to be used with the llama-rng-provider-api in llama.cpp.
"""

import argparse
import os
import logging
from typing import List, Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException
import random
import time
import threading
from collections import deque

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
    
    if use_file:
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
    if use_file:
        return {
            "mode": "file",
            "total_numbers": len(random_numbers),
            "current_index": current_index,
            "remaining": len(random_numbers) - current_index if random_numbers else 0
        }
    else:
        return {
            "mode": "runtime",
            "message": "Generating random numbers on the fly"
        }


def get_speed_stats() -> Dict[str, Any]:
    """Calculate current speed statistics"""
    current_time = time.time()
    
    # Calculate requests per second (last 10 seconds)
    recent_requests = [t for t in request_times if current_time - t <= 10.0]
    rps_10s = len(recent_requests) / min(10.0, current_time - start_time)
    
    # Calculate requests per second (last 1 second)
    very_recent = [t for t in request_times if current_time - t <= 1.0]
    rps_1s = len(very_recent)
    
    # Overall average
    total_time = current_time - start_time
    avg_rps = total_requests / total_time if total_time > 0 else 0
    
    # Estimate data rate (assuming ~50 bytes per response)
    bytes_per_request = 50  # JSON response size estimate
    bps_current = rps_1s * bytes_per_request
    bps_avg = avg_rps * bytes_per_request
    
    return {
        "rps_1s": rps_1s,
        "rps_10s": rps_10s,
        "rps_avg": avg_rps,
        "bps_current": bps_current,
        "bps_avg": bps_avg,
        "total_requests": total_requests,
        "uptime": total_time
    }


def create_stats_table() -> Table:
    """Create a rich table with current statistics"""
    stats = get_speed_stats()
    
    table = Table(title="🎲 RNG Service Stats", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Current", style="green")
    table.add_column("Average", style="yellow")
    
    table.add_row("Requests/sec", f"{stats['rps_1s']:.1f}", f"{stats['rps_avg']:.1f}")
    table.add_row("Requests/sec (10s)", f"{stats['rps_10s']:.1f}", "")
    table.add_row("Bytes/sec", f"{stats['bps_current']:.0f}", f"{stats['bps_avg']:.0f}")
    table.add_row("Total Requests", f"{stats['total_requests']}", "")
    table.add_row("Uptime", f"{stats['uptime']:.1f}s", "")
    
    if use_file:
        table.add_row("File Progress", f"{current_index}/{len(random_numbers)}", f"{(current_index/len(random_numbers)*100):.1f}%" if random_numbers else "N/A")
    
    return table


def stats_display_thread():
    """Background thread to display live statistics"""
    if not RICH_AVAILABLE:
        return
        
    with Live(create_stats_table(), refresh_per_second=2, console=console) as live:
        while True:
            time.sleep(0.5)
            live.update(create_stats_table())


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
    parser.add_argument("--log-file", type=str, help="Path to save request logs (optional)")
    parser.add_argument("--no-access-logs", action="store_true", help="Disable FastAPI access logs")
    args = parser.parse_args()
    
    global random_numbers
    global current_index
    global use_file
    
    if args.file:
        # Load random numbers from file
        random_numbers = load_random_numbers(args.file)
        if random_numbers:
            use_file = True
            current_index = 0
            logger.info("Using random numbers from file")
        else:
            logger.warning("No valid numbers in file, falling back to runtime generation")
    else:
        logger.info("No file provided, generating random numbers on the fly")
    
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