import os
import time
import subprocess
import argparse
from pathlib import Path
from loguru import logger
import typer
from typing import Optional, Dict, Any
from pydantic import BaseModel
import json
from datetime import datetime
import sys
from tqdm import tqdm

def setup_logger(verbose: bool = False):
    """Configure and setup logger with appropriate verbosity."""
    logger.remove()
    if verbose:
        logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="DEBUG")
    else:
        logger.add(sys.stderr, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")
    return logger

def find_llama_root():
    # Check current directory
    if os.path.exists("build"):
        return os.getcwd()
    
    # Check parent directory
    parent = os.path.dirname(os.getcwd())
    if os.path.exists(os.path.join(parent, "build")):
        return parent
    
    # Check grandparent directory
    grandparent = os.path.dirname(parent)
    if os.path.exists(os.path.join(grandparent, "build")):
        return grandparent
    
    # Check great-grandparent directory
    great_grandparent = os.path.dirname(grandparent)
    if os.path.exists(os.path.join(great_grandparent, "build")):
        return great_grandparent
    
    raise FileNotFoundError("Could not find llama root directory")

class RunResult(BaseModel):
    command: str
    total_time: float
    prompts_processed: int
    prompts_path: str
    total_prompt_tokens: int
    total_gen_tokens: int
    total_tokens: int
    token_speed: float
    parallel_clients: int
    model_path: str
    timestamp: str
    success: bool
    error_message: str = ""

app = typer.Typer()

@app.command()
def run(
    prompts_path: str = typer.Option(..., "--prompts", "-p", help="Path to the prompts file"),
    executable_path: Optional[str] = typer.Option(None, "--executable", "-e", help="Path to the parallel executable"),
    model_path: str = typer.Option(..., "--model", "-m", help="Path to the model file"),
    n_parallel: int = typer.Option(1, "--parallel", "-np", help="Number of parallel clients"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="Path to save the results"),
    results_json: Optional[str] = typer.Option(None, "--json", "-j", help="Path to save results statistics as JSON"),
    n_predict: int = typer.Option(256, "--n-predict", help="Maximum number of tokens to predict"),
    ctx_size: Optional[int] = typer.Option(None, "--ctx-size", "-c", help="Context size (KV cache size). If not provided, will be scaled with parallelism"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
) -> Dict[str, Any]:
    """
    Run the llama.cpp parallel processing tool with specified parameters.
    
    Note: The number of sequences is always set to the number of prompts in the file.
    Each prompt will be processed exactly once.
    """
    # Set up logger
    logger = setup_logger(verbose)
    
    if not os.path.exists(prompts_path):
        logger.error(f"Prompts file not found: {prompts_path}")
        raise typer.Exit(1)
    
    # Determine the executable path if not provided
    if executable_path is None:
        executable_path = os.path.join(os.getcwd(), "build", "bin", "llama-parallel")
    
    if not os.path.exists(executable_path):
        logger.error(f"Executable not found: {executable_path}")
        raise typer.Exit(1)
    
    if not os.path.exists(model_path):
        logger.error(f"Model file not found: {model_path}")
        raise typer.Exit(1)
    
    # Count the number of prompts
    with open(prompts_path, 'r') as f:
        prompt_count = sum(1 for _ in f)
    
    # Calculate appropriate context size if not provided
    if ctx_size is None:
        # Formula: context size should be at least (n_parallel * n_predict * safety_factor)
        safety_factor = 1.5  # Add 50% margin for safety
        min_ctx_size = int(n_parallel * n_predict * safety_factor)
        # Round up to nearest power of 2 for better efficiency
        ctx_size = 2048  # Default minimum
        while ctx_size < min_ctx_size:
            ctx_size *= 2
        logger.info(f"Auto-calculated context size: {ctx_size} (minimum needed: {min_ctx_size})")
    
    logger.info(f"Processing {prompt_count} prompts with {n_parallel} parallel clients")
    
    # Construct the command
    cmd = [
        executable_path,
        "--model", model_path,
        "--file", prompts_path,
        "--parallel", str(n_parallel),
        "--n-predict", str(n_predict),
        "--ctx-size", str(ctx_size),
    ]
    
    # Add output file if provided
    if output_path:
        cmd.extend(["-o", output_path])
    
    # Join command for display
    cmd_str = " ".join(cmd)
    logger.info(f"Running command: {cmd_str}")
    
    try:
        # Measure execution time
        start_time = time.time()
        start_datetime = datetime.now()
        logger.info(f"Process started at: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run the command and capture output
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            bufsize=1
        )
        
        # Setup progress bar - but simpler approach
        logger.info(f"Started processing {prompt_count} prompts...")
        
        # Track token statistics
        total_prompt_tokens = None
        total_gen_tokens = None
        token_speed = None
        
        # Process output in a simpler way - just log it and collect stats at the end
        if verbose:
            # In verbose mode, show all output
            for line in process.stdout:
                logger.info(line.strip())
        else:
            # In non-verbose mode, just wait for completion
            pass
                
        # Wait for the process to complete
        stdout, stderr = process.communicate()
        end_time = time.time()
        end_datetime = datetime.now()
        
        # Extract stats from the complete output
        if stdout:
            for line in stdout.splitlines():
                # Extract token statistics
                if "Total prompt tokens:" in line:
                    try:
                        parts = line.split()
                        total_prompt_tokens = int(parts[3].strip(','))
                    except (IndexError, ValueError):
                        pass
                
                elif "Total gen tokens:" in line:
                    try:
                        parts = line.split()
                        total_gen_tokens = int(parts[3].strip(','))
                    except (IndexError, ValueError):
                        pass
                
                elif "Total speed (AVG):" in line:
                    try:
                        parts = line.split()
                        token_speed = float(parts[6])
                    except (IndexError, ValueError):
                        pass
        
        # Check for errors
        if process.returncode != 0:
            logger.error(f"Process failed with return code {process.returncode}")
            if stderr:
                logger.error(f"Error output: {stderr}")
            raise typer.Exit(process.returncode)
        
        # Calculate statistics
        execution_time = end_time - start_time
        wall_clock_time = (end_datetime - start_datetime).total_seconds()
        prompts_per_second = prompt_count / execution_time
        
        # Print a simple, clear summary with a separator line
        logger.info("\n" + "-" * 40)
        logger.info(f"TOTAL TIME: {wall_clock_time:.2f} seconds")
        logger.info(f"Processing speed: {prompts_per_second:.2f} prompts/second")
        
        # Basic token statistics 
        if total_prompt_tokens is not None and total_gen_tokens is not None:
            total_tokens = total_prompt_tokens + total_gen_tokens
            logger.info(f"Total tokens: {total_tokens} (prompt: {total_prompt_tokens}, generated: {total_gen_tokens})")
        if token_speed is not None:
            logger.info(f"Token speed: {token_speed:.2f} tokens/second")
        logger.info("-" * 40)
        
        # Prepare results
        results = {
            "execution_time": execution_time,
            "prompt_count": prompt_count,
            "prompts_per_second": prompts_per_second,
            "n_parallel": n_parallel,
            "n_predict": n_predict,
            "model_path": model_path,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add token statistics to results
        if total_prompt_tokens is not None:
            results["total_prompt_tokens"] = total_prompt_tokens
        if total_gen_tokens is not None:
            results["total_gen_tokens"] = total_gen_tokens
        if total_prompt_tokens is not None and total_gen_tokens is not None:
            results["total_tokens"] = total_prompt_tokens + total_gen_tokens
        if token_speed is not None:
            results["token_speed"] = token_speed
        
        # Save results to JSON if requested
        if results_json:
            # Prepare token statistics with proper defaults
            prompt_tokens = total_prompt_tokens if total_prompt_tokens is not None else 0
            gen_tokens = total_gen_tokens if total_gen_tokens is not None else 0
            total_tokens = prompt_tokens + gen_tokens if prompt_tokens is not None and gen_tokens is not None else 0
            tok_speed = token_speed if token_speed is not None else 0
            
            result = RunResult(
                command=cmd_str,
                total_time=execution_time,
                prompts_processed=prompt_count,
                prompts_path=prompts_path,
                total_prompt_tokens=prompt_tokens,
                total_gen_tokens=gen_tokens,
                total_tokens=total_tokens,
                token_speed=tok_speed,
                parallel_clients=n_parallel,
                model_path=model_path,
                timestamp=datetime.now().isoformat(),
                success=True,
                error_message=""
            )
            
            try:
                with open(results_json, 'w') as f:
                    f.write(result.model_dump_json(indent=2))
                
                logger.info(f"Results saved to {results_json}")
            except Exception as e:
                logger.error(f"Failed to save results to {results_json}: {e}")
        
        return results
    
    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        
        # Save error to JSON if requested
        if results_json:
            # Prepare token statistics with proper defaults
            prompt_tokens = total_prompt_tokens if 'total_prompt_tokens' in locals() and total_prompt_tokens is not None else 0
            gen_tokens = total_gen_tokens if 'total_gen_tokens' in locals() and total_gen_tokens is not None else 0
            total_tokens = prompt_tokens + gen_tokens
            tok_speed = token_speed if 'token_speed' in locals() and token_speed is not None else 0
            
            result = RunResult(
                command=cmd_str if 'cmd_str' in locals() else "",
                total_time=time.time() - start_time if 'start_time' in locals() else 0,
                prompts_processed=prompt_count if 'prompt_count' in locals() else 0,
                prompts_path=prompts_path,
                total_prompt_tokens=prompt_tokens,
                total_gen_tokens=gen_tokens,
                total_tokens=total_tokens,
                token_speed=tok_speed,
                parallel_clients=n_parallel,
                model_path=model_path,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )
            
            try:
                with open(results_json, 'w') as f:
                    f.write(result.model_dump_json(indent=2))
            except:
                pass
        
        return {
            "execution_time": 0,
            "prompt_count": 0,
            "prompts_per_second": 0,
            "n_parallel": n_parallel,
            "n_predict": n_predict,
            "model_path": model_path,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "total_prompt_tokens": prompt_tokens if 'prompt_tokens' in locals() else 0,
            "total_gen_tokens": gen_tokens if 'gen_tokens' in locals() else 0,
            "total_tokens": total_tokens if 'total_tokens' in locals() else 0,
            "token_speed": tok_speed if 'tok_speed' in locals() else 0
        }

if __name__ == "__main__":
    app()