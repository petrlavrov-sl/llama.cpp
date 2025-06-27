# External API RNG Provider

This document explains how to set up and use the external API RNG provider with llama.cpp.

## Overview

The external API RNG provider replaces the default random number generator in llama.cpp with one that gets random numbers from an external HTTP API. This is useful for:

1. Studying how different random sequences affect LLM outputs
2. Ensuring deterministic generation across different machines
3. Debugging sampling issues by using a controlled source of randomness

## Setup

### 1. Start the Python RNG Service

The Python RNG service reads random numbers from a file and serves them via a REST API.

```bash
# First, install the required dependencies
pip install -r rng_service_requirements.txt

# Generate a file with 10,000 random numbers and start the service
python rng_service.py --file random_numbers.txt --generate 10000 --host 127.0.0.1 --port 8000
```

The service will:
- If the file doesn't exist, generate N random numbers and save them to the file
- If the file exists, load the random numbers from the file
- Start a FastAPI service that serves these numbers via the `/random` endpoint

### 2. Using with llama-run (run.py)

To use the external API RNG with the `run.py` script, you can add a new mode by editing the script to include an option for the external RNG provider.

```python
# Add to run.py
parser.add_argument("--external-rng", type=str, help="URL for external RNG API", default=None)

# Add to the environment variables section
if args.external_rng:
    # Set environment variable for external RNG
    os.environ["LLAMA_EXTERNAL_RNG_URL"] = args.external_rng
```

Then, modify the llama-run code to check for this environment variable and initialize the external RNG provider if it's set.

## Usage

### Running with the External RNG

```bash
# Start the RNG service
python rng_service.py --file random_numbers.txt --generate 10000 &

# Run inference with the external RNG
python run.py --mode llama-run --external-rng http://localhost:8000/random --model models/gemma-1.1-7b-it.Q4_K_M.gguf --prompt "Tell me about artificial intelligence"
```

### Verifying It's Working

When the external RNG provider is active, you should see:

1. Log messages from the RNG service showing that it's serving random numbers
2. Log messages from llama.cpp showing the random values being used during sampling

You can check the RNG service logs to confirm that it's receiving requests:

```bash
curl http://localhost:8000/status
```

This will show:
- The total number of random numbers available
- The current index 
- How many numbers remain before wrapping around

## Advanced Usage

### Creating Custom Random Sequences

You can create custom random number sequences for specific testing:

```bash
# Generate an evenly distributed sequence from 0 to 1
python -c "import numpy as np; np.savetxt('even_distribution.txt', np.linspace(0, 1, 1000))"

# Use a biased distribution to test sampling behavior
python -c "import numpy as np; np.savetxt('biased_high.txt', np.random.beta(5, 1, 1000))"
```

Then start the RNG service with your custom file:

```bash
python rng_service.py --file even_distribution.txt
```

### Comparing Multiple Runs

To compare how different random sequences affect generation:

1. Create different random number files
2. Run the same prompt with each random number file
3. Compare the outputs to see how randomness influences generation

```bash
# Run with first sequence
python rng_service.py --file sequence1.txt &
python run.py --mode llama-run --external-rng http://localhost:8000/random --model models/gemma-1.1-7b-it.Q4_K_M.gguf --prompt "Tell me about AI" > output1.txt

# Kill the service and run with second sequence
kill %1
python rng_service.py --file sequence2.txt &
python run.py --mode llama-run --external-rng http://localhost:8000/random --model models/gemma-1.1-7b-it.Q4_K_M.gguf --prompt "Tell me about AI" > output2.txt
```

## Implementation Details

The external RNG provider is implemented in:
- `llama-rng-provider.h` - Defines the RNG provider interface
- `llama-rng-provider.cpp` - Contains the implementation for both default and API-based providers

The provider is initialized by the factory function `create_rng_provider("external-api", seed)` which:
1. Reads the API URL from the LLAMA_RNG_API_URL environment variable
2. Creates a new ExternalAPIRNGProvider instance
3. Sets up the provider to make HTTP requests to the specified API URL
4. Parses the JSON responses to extract the `random` field value

The Python service (`rng_service.py`) provides a simple API that:
1. Loads random numbers from a file or generates them if needed
2. Serves them one at a time via a REST API
3. Wraps around to the beginning when it reaches the end of the list

## Troubleshooting

1. **Service Not Starting**: Make sure you have FastAPI and uvicorn installed
2. **Connection Refused**: Verify the host/port settings and that the service is running
3. **Invalid Response**: Check that the API response contains a `random` field with a valid number
4. **Build Errors**: Ensure libcurl and nlohmann_json dependencies are properly installed

## Performance Considerations

- The external API adds network latency to each token generation
- For production use, consider running the service on the same machine to minimize latency
- Pre-generate large files of random numbers to avoid wrapping around too quickly