#!/bin/bash

# Script to run all models in models-superlinear directory with both uniform and normal distributions
# Usage: ./run_all_models.sh [num_tokens]

# Set default number of tokens if not provided
NUM_TOKENS=${1:-100}
echo "Using $NUM_TOKENS tokens for each run"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Directory containing models (relative to project root)
MODELS_DIR="$PROJECT_ROOT/models-superlinear"

# Prompt to use for all runs
PROMPT="Tell me about the history of artificial intelligence"

# Check if models directory exists
if [ ! -d "$MODELS_DIR" ]; then
    echo "Error: Models directory not found at $MODELS_DIR"
    exit 1
fi

# Find all .gguf files in the models directory
echo "Finding models in $MODELS_DIR..."
MODELS=$(find "$MODELS_DIR" -name "*.gguf" -type f)

if [ -z "$MODELS" ]; then
    echo "No .gguf models found in $MODELS_DIR"
    exit 1
fi

# Count models
MODEL_COUNT=$(echo "$MODELS" | wc -l)
echo "Found $MODEL_COUNT models"

# Change to project root directory
cd "$PROJECT_ROOT"

# Run each model with both uniform and normal distributions
for MODEL_PATH in $MODELS; do
    # Extract model name from path
    MODEL_NAME=$(basename "$MODEL_PATH" .gguf)
    echo "Processing model: $MODEL_NAME"
    
    # Run with uniform distribution
    echo "  Running with uniform distribution..."
    poetry run python dev-superlinear/run.py --model "$MODEL_PATH" --prompt "$PROMPT" --rng uniform --num-tokens "$NUM_TOKENS"
    
    # Run with normal distribution
    echo "  Running with normal distribution..."
    poetry run python dev-superlinear/run.py --model "$MODEL_PATH" --prompt "$PROMPT" --rng normal --num-tokens "$NUM_TOKENS"
    
    echo "  Completed runs for $MODEL_NAME"
    echo "----------------------------------------"
done

echo "All runs completed!"
echo "Results are saved in the runs directory" 