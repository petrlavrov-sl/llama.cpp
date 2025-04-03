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
    n_predict: int = typer.Option(128, "--n-predict", help="Maximum number of tokens to predict"),
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
    
    logger.info(f"Processing {prompt_count} prompts with {n_parallel} parallel clients")
    
    # Construct the command
    cmd = [
        executable_path,
        "--model", model_path,
        "--file", prompts_path,
        "--parallel", str(n_parallel),
        "--n-predict", str(n_predict),
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
        
        # Run the command and capture output
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            bufsize=1
        )
        
        # Setup progress bar
        progress = tqdm(total=prompt_count, desc="Processing prompts")
        completed_prompts = 0
        
        # Process output in real-time
        for line in process.stdout:
            if verbose:
                logger.info(line.strip())
            
            # Update progress based on output
            if "prompt" in line.lower() and "processed" in line.lower():
                completed_prompts += 1
                progress.update(1)
            # Add more patterns to catch progress indicators
            elif "seq" in line.lower() and "client" in line.lower():
                # Example: "Client   0, seq   0/  12, prompt    6 t, response   17 t, time  0.02 s..."
                completed_prompts += 1
                progress.update(1)
            elif "input:" in line.lower() and "response:" in line.lower():
                # Another potential indicator that a prompt was processed
                completed_prompts += 1
                progress.update(1)
        
        # If we didn't catch any progress updates but the process completed successfully,
        # update the progress bar to completion
        if completed_prompts == 0 and process.returncode == 0:
            progress.update(prompt_count)
        
        # Wait for the process to complete
        process.wait()
        end_time = time.time()
        progress.close()
        
        # Check for errors
        if process.returncode != 0:
            stderr_output = process.stderr.read()
            logger.error(f"Process failed with return code {process.returncode}")
            logger.error(f"Error output: {stderr_output}")
            raise typer.Exit(process.returncode)
        
        # Calculate statistics
        execution_time = end_time - start_time
        prompts_per_second = prompt_count / execution_time
        
        logger.info(f"Execution completed in {execution_time:.2f} seconds")
        logger.info(f"Average processing speed: {prompts_per_second:.2f} prompts/second")
        
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
        
        # Save results to JSON if requested
        if results_json:
            result = RunResult(
                command=cmd_str,
                total_time=execution_time,
                prompts_processed=prompt_count,
                prompts_path=prompts_path,
                total_prompt_tokens=0,
                total_gen_tokens=0,
                total_tokens=0,
                token_speed=prompts_per_second,
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
            result = RunResult(
                command=cmd_str if 'cmd_str' in locals() else "",
                total_time=time.time() - start_time if 'start_time' in locals() else 0,
                prompts_processed=prompt_count if 'prompt_count' in locals() else 0,
                prompts_path=prompts_path,
                total_prompt_tokens=0,
                total_gen_tokens=0,
                total_tokens=0,
                token_speed=0,
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
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    app()