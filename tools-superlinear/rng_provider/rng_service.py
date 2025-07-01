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
total_requests = 0
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
    # parser.add_argument("--no-access-logs", action="store_true", help="Disable FastAPI access logs")
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
    else:
        # Disable access logs completely
        logger.info("Access logging disabled")
        uvicorn_config["access_log"] = False
    
    # Start the server
    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    main()