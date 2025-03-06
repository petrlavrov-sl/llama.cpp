```bash
# Run from the project root
poetry run python dev-superlinear/run.py
```

The script uses `__file__` to automatically find all paths, so you don't need to worry about directory structure.

Edit dev-superlinear/config.yaml to customize your run:

```yaml
# RNG Provider Configuration
rng_provider: uniform  # Options: uniform, normal

# Model Configuration
model: gemma-2-2b  # Available shortcuts: gemma-2-2b, gemma-2-2b-it, llama-3.1-8b, llama-3.1-8b-instruct, llama-3.2-1b-instruct

# Number of tokens to generate (optional)
num_tokens: 100

# Prompt
prompt: "Tell me about the history of artificial intelligence"

# Run Directory (OPTIONAL) - If not provided, a directory will be auto-generated
# run_dir: my_custom_directory
```

Override config options with command line arguments:
```bash
poetry run python dev-superlinear/run.py --rng normal --model llama-3.1-8b --num-tokens 50
```

The script will:
1. Run the model with the specified configuration
2. If no run_dir is provided, generate a directory name: runs/{model}_{rng_provider}_{timestamp}
3. Generate a visualization of the RNG distribution (even if the model run fails)

## Troubleshooting

If you see errors in the log file, try reducing the number of tokens to generate with the `--num-tokens` parameter.