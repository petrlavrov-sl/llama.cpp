#!/bin/bash
# Example script to run token probability visualization

# Check if model path is provided
if [ $# -eq 0 ]; then
  echo "Usage: $0 <model_path> [prompt]"
  echo "Example: $0 models/gemma/gemma-1.1-7b-it.Q4_K_M.gguf 'Tell me about AI'"
  exit 1
fi

MODEL=$1
PROMPT=${2:-"Tell me about artificial intelligence"}
OUTPUT_DIR="token_viz_output"

# Create output directory
mkdir -p $OUTPUT_DIR

# Run the model and capture output
echo "Running model with prompt: '$PROMPT'"
echo "Capturing token probability data..."

# Run using both methods
./build/bin/llama-run --ngl 999 $MODEL "$PROMPT" 2> $OUTPUT_DIR/inference_log.txt > $OUTPUT_DIR/output.txt

# Also save in JSON format
LLAMA_TOKEN_DATA_FILE=$OUTPUT_DIR/token_data.jsonl ./build/bin/llama-run --ngl 999 $MODEL "$PROMPT" > $OUTPUT_DIR/output_json.txt

echo "Generating visualizations..."

# Generate standard visualization
python tools-superlinear/token_probability_visualizer.py $OUTPUT_DIR/inference_log.txt $OUTPUT_DIR/output.txt --html $OUTPUT_DIR/visualization.html

# Generate relative mode visualization
python tools-superlinear/token_probability_visualizer.py $OUTPUT_DIR/inference_log.txt $OUTPUT_DIR/output.txt --mode relative --html $OUTPUT_DIR/visualization_relative.html

echo "Visualizations generated in $OUTPUT_DIR directory"
echo "- Standard visualization: $OUTPUT_DIR/visualization.html"
echo "- Relative mode visualization: $OUTPUT_DIR/visualization_relative.html"
echo "- Token probability JSON: $OUTPUT_DIR/token_probs.json"
echo "- Token probability plots: $OUTPUT_DIR/token_probs_plot.png"

# Open the visualization (macOS specific, adjust for other platforms)
if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "Opening visualization in browser..."
  open $OUTPUT_DIR/visualization.html
fi