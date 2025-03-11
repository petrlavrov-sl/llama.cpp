# External API RNG Provider

This directory contains a Python service that provides random numbers to llama.cpp via an HTTP API.

## Overview

The external API RNG provider allows:

1. Serving random numbers from a file over HTTP
2. Controlling randomness in LLM text generation
3. Observing how specific random sequences affect output

## Setup and Usage

### 1. Install Requirements

```bash
pip install -r rng_service_requirements.txt
```

### 2. Generate or Prepare Random Numbers

You can either generate random numbers on the fly or prepare a file with specific numbers:

```bash
# Generate 10,000 random numbers and save to a file
python rng_service.py --file random_numbers.txt --generate 10000
```

Or create a custom file with specific random values (one value per line):

```bash
# Example: Create an evenly distributed sequence
python -c "import numpy as np; np.savetxt('even_distribution.txt', np.linspace(0, 1, 1000))"
```

### 3. Start the RNG Service

```bash
python rng_service.py --file random_numbers.txt --host 127.0.0.1 --port 8000
```

### 4. Run llama.cpp with the External RNG Provider

Use the `run.py` script from the `run-llama` directory:

```bash
cd ../run-llama
python run.py --rng external-api --api-url http://localhost:8000/random --model gemma-2-2b-it --prompt "Tell me about AI"
```

Or modify the `config.yaml` file:

```yaml
rng_provider: external-api
api_url: http://localhost:8000/random
```

## API Endpoints

The RNG service provides the following endpoints:

- **GET /** - Root endpoint showing service status
- **GET /random** - Returns a random number between 0 and 1 in JSON format: `{"random": 0.123}`
- **GET /status** - Shows current service status: total numbers loaded, current index, and remaining numbers

## Advanced Usage

### Creating Predictable Sequences

For deterministic testing, you can create fixed sequences:

```python
# Ascending values from 0 to 1
values = [i/1000 for i in range(1001)]

# Save to file
with open("predictable_seq.txt", "w") as f:
    for v in values:
        f.write(f"{v}\n")
```

### Repeating Sequences

To see how a specific random sequence affects generation:

1. Create a file with a small number of random values
2. The service will automatically wrap around to the beginning when all values have been used

### Visualizing RNG Distribution

The random values used during generation are saved to `rng_values.txt` in the run directory. 
You can visualize the distribution using the tools in the repository.

## Troubleshooting

- **No numbers available**: Make sure the file exists and contains valid numbers
- **Connection refused**: Check that the host/port settings are correct
- **llama.cpp not finding the service**: Verify the API URL is correctly specified