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

# Get script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

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
        print(f"Warning: Visualization script not found at {visualize_script}")
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
    
    # Run the visualization script
    try:
        cmd = ["python", visualize_script, input_file, "-o", output_file]
        subprocess.run(cmd, check=True)
        print(f"Visualization saved to {output_file}")
        
        # Clean up temporary file if we created one
        if isinstance(values, np.ndarray) and os.path.exists(temp_file):
            os.remove(temp_file)
            
        return True
    except Exception as e:
        print(f"Warning: Failed to generate plot: {e}")
        return False

def run_model(config, config_path):
    """Run the model with the specified configuration"""
    try:
        # Resolve model path
        model_path = resolve_model_path(config['model'])
        
        # Check if model path exists
        if not os.path.exists(model_path):
            print(f"Error: Model path '{model_path}' does not exist")
            print(f"Available model shortcuts: {', '.join(MODEL_PATHS.keys())}")
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
            print(f"Error: llama-run not found at '{llama_run_path}'")
            print("Make sure you have built the LLaMA.cpp project")
            return False
        
        # Set environment variable for RNG provider
        env = os.environ.copy()
        env["LLAMA_RNG_PROVIDER"] = config['rng_provider']
        env["LLAMA_RNG_OUTPUT"] = rng_file  # Save RNG values directly to run dir
        
        # Run the command
        cmd = [llama_run_path, model_path, config['prompt']]
        print(f"Running command: {' '.join(cmd)}")
        print(f"RNG Provider: {config['rng_provider']}")
        print(f"Output will be saved to: {run_dir}")
        
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
            print(f"Error running command: {e}")
            print(f"Check the log file for details: {log_file}")
            return False
        
        # Generate plot if RNG values file exists
        if os.path.exists(rng_file):
            # Generate plot using the visualize_rng.py script
            if visualize_distribution(rng_file, plot_file, config['rng_provider']):
                print(f"RNG distribution plot: {plot_file}")
            else:
                print(f"Warning: Failed to generate RNG distribution plot")
        else:
            print(f"Warning: RNG values file {rng_file} not found")
        
        print(f"Run completed successfully!")
        print(f"Output: {output_file}")
        print(f"Log: {log_file}")
        if os.path.exists(rng_file):
            print(f"RNG values: {rng_file}")
        
        return True
    except Exception as e:
        print(f"Error in run_model: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run llama.cpp with configurable RNG provider")
    default_config = os.path.join(SCRIPT_DIR, "config.yaml")
    parser.add_argument("-c", "--config", default=default_config, help="Path to config file")
    parser.add_argument("-m", "--model", help="Override model from config")
    parser.add_argument("-p", "--prompt", help="Override prompt from config")
    parser.add_argument("-r", "--rng", help="Override RNG provider from config")
    parser.add_argument("-d", "--dir", help="Override run directory from config")
    
    args = parser.parse_args()
    
    # Load config
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        return 1
    
    # Check required config values
    required_keys = ['model', 'prompt', 'rng_provider']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        print(f"Error: Missing required config values: {', '.join(missing_keys)}")
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
    
    # Validate RNG provider
    valid_providers = ['uniform', 'normal']
    if config['rng_provider'] not in valid_providers:
        print(f"Error: Invalid RNG provider '{config['rng_provider']}'")
        print(f"Valid providers: {', '.join(valid_providers)}")
        return 1
    
    # Run the model
    success = run_model(config, args.config)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 