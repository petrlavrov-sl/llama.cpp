#!/usr/bin/env python3
"""
Random Number Generator Service for llama.cpp

This service provides random numbers from a file via a REST API either from a file or generated on the fly.

It's intended to be used with the llama-rng-provider-api in llama.cpp.
"""

import argparse
import os
import logging
from typing import List, Dict, Any
import uvicorn
from fastapi import FastAPI, HTTPException
import random

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


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {"message": "RNG Service is running"}


@app.get("/random")
async def get_random() -> Dict[str, float]:
    """Get a random number between 0 and 1"""
    global current_index
    
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
    
    logger.info(f"Serving random number: {value}")

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


def generate_random_numbers(count: int) -> List[float]:
    """Generate random numbers if no file is provided"""
    import random
    logger.info(f"Generating {count} random numbers")
    return [random.random() for _ in range(count)]


def save_random_numbers(file_path: str, numbers: List[float]) -> None:
    """Save random numbers to a file"""
    with open(file_path, "w") as f:
        for num in numbers:
            f.write(f"{num}\n")
    logger.info(f"Saved {len(numbers)} random numbers to {file_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="RNG Service")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")

    parser.add_argument("--file", type=str, help="Path to random numbers file (optional)")
    parser.add_argument("--generate", type=int, default=0, 
                        help="Generate N random numbers if file doesn't exist")
    args = parser.parse_args()
    
    global random_numbers
    global current_index
    global use_file
    
    if args.file:
        # If file doesn't exist and --generate is specified, generate random numbers
        if not os.path.exists(args.file) and args.generate > 0:
            random_numbers = generate_random_numbers(args.generate)
            save_random_numbers(args.file, random_numbers)
        else:
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
    
    # Start the server
    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()