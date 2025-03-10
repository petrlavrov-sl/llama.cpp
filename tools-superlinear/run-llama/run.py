#!/usr/bin/env python3
"""
Run script for llama.cpp with configurable RNG provider
"""

import os
import sys
import yaml
import argparse
import subprocess
import shutil
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime
from loguru import logger

# Get script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Configure loguru logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, format="<level>{level: <8}</level> | <green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level>")

# Model path shortcuts
MODEL_PATHS = {
    "gemma-2-2b": os.path.join(PROJECT_ROOT, "models-superlinear/gemma-2-2b.gguf"),
    "gemma-2-2b-it": os.path.join(PROJECT_ROOT, "models-superlinear/gemma-2-2b-it.gguf"),
    "llama-3.1-8b": os.path.join(PROJECT_ROOT, "models-superlinear/llama-3.1-8b.gguf"),
    "llama-3.1-8b-instruct": os.path.join(PROJECT_ROOT, "models-superlinear/llama-3.1-8b-instruct.gguf"),
    "llama-3.2-1b-instruct": os.path.join(PROJECT_ROOT, "models-superlinear/llama-3.2-1b-instruct.gguf"),
}

def resolve_model_path(model_name):
    """Resolve model name to full path"""
    if model_name in MODEL_PATHS:
        return MODEL_PATHS[model_name]
    return model_name  # Assume it's already a path

def ensure_dir(directory):
    """Ensure directory exists"""
    Path(directory).mkdir(parents=True, exist_ok=True)
    return directory

def read_rng_values(filename):
    """Read RNG values from a file"""
    values = []
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            
            try:
                value = float(line)
                values.append(value)
            except ValueError:
                continue
    
    return np.array(values)

def visualize_distribution(values, output_file, rng_provider):
    """Visualize the distribution of RNG values using visualize_rng.py"""
    # Use the visualize_rng.py script from tools directory
    visualize_script = os.path.join(PROJECT_ROOT, "tools/visualize_rng.py")
    
    if not os.path.exists(visualize_script):
        logger.warning(f"Visualization script not found at {visualize_script}")
        logger.warning(f"No RNG distribution plot will be generated.")
        return False
    
    # Save values to a temporary file if they're not already in a file
    if isinstance(values, np.ndarray):
        temp_file = os.path.join(SCRIPT_DIR, f"temp_rng_values.txt")
        with open(temp_file, 'w') as f:
            for value in values:
                f.write(f"{value}\n")
        input_file = temp_file
    else:
        # Assume values is a path to a file
        input_file = values
        
        # Check if the file exists and has content
        if not os.path.exists(input_file):
            logger.warning(f"RNG values file not found at {input_file}")
            logger.warning(f"No RNG distribution plot will be generated.")
            return False
            
        if os.path.getsize(input_file) == 0:
            logger.warning(f"RNG values file is empty: {input_file}")
            logger.warning(f"No RNG distribution plot will be generated.")
            return False
    
    # Run the visualization script
    try:
        cmd = ["python", visualize_script, input_file, "-o", output_file]
        logger.info(f"Running visualization command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.success(f"Visualization saved to {output_file}")
        
        # Clean up temporary file if we created one
        if isinstance(values, np.ndarray) and os.path.exists(temp_file):
            os.remove(temp_file)
            
        # Verify the output file was created
        if not os.path.exists(output_file):
            logger.warning(f"Visualization command completed but output file not found: {output_file}")
            return False
            
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to generate plot: {e}")
        logger.debug(f"Command output: {e.stdout}")
        logger.debug(f"Command error: {e.stderr}")
        return False
    except Exception as e:
        logger.warning(f"Failed to generate plot: {e}")
        return False

def run_model(config, config_path):
    """Run the model with the specified configuration"""
    try:
        # Resolve model path
        model_path = resolve_model_path(config['model'])
        
        # Check if model path exists
        if not os.path.exists(model_path):
            logger.error(f"Error: Model path '{model_path}' does not exist")
            logger.info(f"Available model shortcuts: {', '.join(MODEL_PATHS.keys())}")
            return False
        
        # Extract a clean model name for the directory
        model_name = config['model']
        if '/' in model_name:
            model_name = model_name.split('/')[-1]
        # Remove file extensions if present
        if model_name.endswith('.gguf'):
            model_name = model_name.rsplit('.', 1)[0]
        # Replace any dots with underscores for cleaner directory names
        model_name = model_name.replace('.', '_')
        
        # Set up run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # If user provided a run_dir, use it; otherwise generate one
        if 'run_dir' in config and config['run_dir']:
            # User specified a run directory
            run_dir = os.path.join(PROJECT_ROOT, config['run_dir'])
        else:
            # Generate a descriptive run directory
            run_dir = os.path.join(PROJECT_ROOT, f"runs/{model_name}_{config['rng_provider']}_{timestamp}")
        
        # Make sure run_dir exists
        run_dir = ensure_dir(run_dir)
        
        # Set up output files
        output_file = os.path.join(run_dir, "output.txt")
        log_file = os.path.join(run_dir, "log.txt")
        rng_file = os.path.join(run_dir, "rng_values.txt")
        plot_file = os.path.join(run_dir, "rng_distribution.png")
        
        # Save config to run directory
        with open(os.path.join(run_dir, "config.yaml"), 'w') as f:
            yaml.dump(config, f)
        
        # Build the command - use path to llama-run
        llama_run_path = os.path.join(PROJECT_ROOT, "build/bin/llama-run")
        
        # Check if llama-run exists
        if not os.path.exists(llama_run_path):
            logger.error(f"Error: llama-run not found at '{llama_run_path}'")
            logger.info("Make sure you have built the LLaMA.cpp project")
            return False
        
        # Set environment variable for RNG provider
        env = os.environ.copy()
        
        # Set different environment variables based on the RNG provider
        if config['rng_provider'] == 'external-api':
            # When using external API, we need to set the API URL environment variable
            env["LLAMA_RNG_PROVIDER"] = "external-api"
            env["LLAMA_RNG_API_URL"] = config['api_url']
            logger.info(f"Using external API RNG provider with URL: {config['api_url']}")
        else:
            # For built-in providers (uniform, normal), use the regular environment variable
            env["LLAMA_RNG_PROVIDER"] = config['rng_provider']
            
        env["LLAMA_RNG_OUTPUT"] = rng_file  # Save RNG values directly to run dir
        
        # Build the command
        cmd = [llama_run_path]
        
        # Add number of tokens parameter if specified
        if 'num_tokens' in config:
            cmd.extend(['-n', str(config['num_tokens'])])
            
        # Add model path and prompt
        cmd.extend([model_path, config['prompt']])
        
        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"RNG Provider: {config['rng_provider']}")
        logger.info(f"Output will be saved to: {run_dir}")
        
        try:
            with open(output_file, 'w') as out_f, open(log_file, 'w') as log_f:
                process = subprocess.run(
                    cmd,
                    stdout=out_f,
                    stderr=log_f,
                    env=env,
                    check=True
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running command: {e}")
            logger.info(f"Check the log file for details: {log_file}")
            
            # Even if the command failed, try to generate the plot if RNG values were collected
            if os.path.exists(rng_file) and os.path.getsize(rng_file) > 0:
                if visualize_distribution(rng_file, plot_file, config['rng_provider']):
                    logger.success(f"RNG distribution plot: {plot_file}")
                else:
                    logger.warning(f"Failed to generate RNG distribution plot")
            else:
                logger.warning(f"No RNG values were collected. RNG file not found or empty: {rng_file}")
            
            return False
        
        # Generate plot if RNG values file exists
        if os.path.exists(rng_file) and os.path.getsize(rng_file) > 0:
            if visualize_distribution(rng_file, plot_file, config['rng_provider']):
                logger.success(f"RNG distribution plot: {plot_file}")
            else:
                logger.warning(f"Failed to generate RNG distribution plot")
        else:
            logger.warning(f"No RNG values were collected. RNG file not found or empty: {rng_file}")
        
        logger.success(f"Run completed successfully!")
        logger.info(f"Output: {output_file}")
        logger.info(f"Log: {log_file}")
        if os.path.exists(rng_file):
            logger.info(f"RNG values: {rng_file}")
        
        return True
    except Exception as e:
        logger.error(f"Error in run_model: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run llama.cpp with configurable RNG provider")
    default_config = os.path.join(SCRIPT_DIR, "config.yaml")
    parser.add_argument("-c", "--config", default=default_config, help="Path to config file")
    parser.add_argument("-m", "--model", help="Override model from config")
    parser.add_argument("-p", "--prompt", help="Override prompt from config")
    parser.add_argument("-r", "--rng", help="Override RNG provider from config")
    parser.add_argument("-d", "--dir", help="Override run directory from config")
    parser.add_argument("-n", "--num-tokens", type=int, help="Override number of tokens to generate")
    parser.add_argument("-a", "--api-url", help="API URL for external-api RNG provider")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG", format="<level>{level: <8}</level> | <green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{message}</level>")
    
    # Load config
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config file: {e}")
        return 1
    
    # Check required config values
    required_keys = ['model', 'prompt', 'rng_provider']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        logger.error(f"Error: Missing required config values: {', '.join(missing_keys)}")
        return 1
    
    # Override config with command line arguments
    if args.model:
        config['model'] = args.model
    if args.prompt:
        config['prompt'] = args.prompt
    if args.rng:
        config['rng_provider'] = args.rng
    if args.dir:
        config['run_dir'] = args.dir
    if args.num_tokens:
        config['num_tokens'] = args.num_tokens
    if args.api_url:
        config['api_url'] = args.api_url
    
    # Validate RNG provider
    valid_providers = ['uniform', 'normal', 'external-api']
    if config['rng_provider'] not in valid_providers:
        logger.error(f"Error: Invalid RNG provider '{config['rng_provider']}'")
        logger.info(f"Valid providers: {', '.join(valid_providers)}")
        return 1
        
    # Check if external API URL is provided when using external-api provider
    if config['rng_provider'] == 'external-api' and ('api_url' not in config or not config['api_url']):
        logger.error(f"Error: api_url must be specified when using external-api RNG provider")
        return 1
    
    # Run the model
    success = run_model(config, args.config)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 