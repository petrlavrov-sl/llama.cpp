# LLM Token Probability Visualization Tools

This directory contains tools for analyzing and visualizing token probabilities during LLM text generation in llama.cpp.

## Tools

1. **token_probability_visualizer.py** - Visualizes token probabilities with color coding based on selection probability
2. **visualize_rng.py** (in tools/) - Visualizes RNG distribution patterns

## Usage Instructions

### Capturing Token Probability Data

To capture token probability data during inference, you can use one of these approaches:

#### 1. Using stderr output (simple)

Run llama.cpp inference with stderr redirected to a file:

```bash
./build/bin/llama-run models/your-model.gguf "Your prompt" 2> inference_log.txt > output.txt
```

#### 2. Using JSON format (advanced)

Run with the `LLAMA_TOKEN_DATA_FILE` environment variable to output structured JSON:

```bash
LLAMA_TOKEN_DATA_FILE=token_data.json ./build/bin/llama-run models/your-model.gguf "Your prompt" > output.txt
```

### Visualizing Token Probabilities

Once you have the data, use the visualization tool:

```bash
# Basic usage
python tools-superlinear/token_probability_visualizer.py inference_log.txt output.txt

# Advanced options
python tools-superlinear/token_probability_visualizer.py inference_log.txt output.txt --mode relative --html visualization.html --json token_probs.json --plot token_probs_plot.png
```

### Visualizing RNG Distribution

If you're using the RNG capture from the system:

```bash
# Set the environment variable to output raw RNG values
LLAMA_RNG_OUTPUT=rng_values.txt ./build/bin/llama-run models/your-model.gguf "Your prompt"

# Visualize the RNG distribution
python tools/visualize_rng.py rng_values.txt
```

## Visualization Modes

### Absolute Mode (default)

Colors tokens based on their absolute probability value:
- Red: High probability (close to 1.0)
- Yellow: Medium probability
- Green: Low probability (close to 0.0)

### Relative Mode

Colors tokens relative to the range of probabilities in the generated text:
- Red: Highest relative probability in the text
- Yellow: Medium relative probability 
- Green: Lowest relative probability in the text

## Output Files

- **HTML visualization**: Interactive webpage showing the generated text with tokens colored by probability
- **JSON data**: Structured data of token probabilities for further analysis
- **Plot**: Visual chart showing the distribution of token probabilities over the sequence

## Example

To generate an example visualization:

```bash
# Run inference with probability capture
./build/bin/llama-run models/gemma/gemma-1.1-7b-it.Q4_K_M.gguf "Tell me about deep learning" 2> inference_log.txt > output.txt

# Generate visualization
python tools-superlinear/token_probability_visualizer.py inference_log.txt output.txt

# Open the visualization in your browser
open visualization.html
```