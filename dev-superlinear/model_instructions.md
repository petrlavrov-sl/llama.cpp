# Model Download and Conversion Instructions

## Environment Setup
```bash
# Install dependencies
poetry update
poetry install
poetry add huggingface_hub
```

## Authentication

### Generate Hugging Face Token
1. Go to [Hugging Face Token Settings](https://huggingface.co/settings/tokens)
2. Click on "New token"
3. Give it a name (e.g., "llama.cpp")
4. Select "Read" access
5. Click "Generate token"
6. Copy the token and set it as an environment variable:

```bash
# Set Hugging Face token
export HF_TOKEN=your_huggingface_token
```

## Request Model Access

### Gemma Models
1. Request access to Gemma models at [Google Gemma Access Form](https://huggingface.co/google/gemma-2-2b)
2. Click on "Access repository" button
3. Accept the terms and conditions
4. Wait for approval (usually instant)

### Llama Models
1. Request access to Llama models at [Meta Llama Access Form](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B)
2. Click on "Access repository" button
3. Accept the terms and conditions
4. Wait for approval (usually instant)

## Downloading Models

### Gemma Models
```bash
# Download Gemma 2 2B
poetry run huggingface-cli download google/gemma-2-2b --local-dir ./models/gemma-2-2b

# Download Gemma 1.1 7B Instruct
poetry run huggingface-cli download google/gemma-1.1-7b-it --local-dir ./models/gemma/gemma-1.1-7b-it
```

### Llama Models
```bash
# Download Llama 3.1 8B
poetry run huggingface-cli download meta-llama/Meta-Llama-3.1-8B --local-dir ./models/llama-3.1-8b

# Download Llama 3.2 1B
poetry run huggingface-cli download meta-llama/Meta-Llama-3.2-1B --local-dir ./models/llama/llama-3.2-1b
```

## Converting Models to GGUF

### Format Options
- `auto`: Automatic selection of format

### Conversion Commands

#### Gemma Models
```bash
# Convert Gemma 2 2B to F16 GGUF
poetry run python convert_hf_to_gguf.py --outtype auto --outfile models/gemma-2-2b-gguf models/gemma-2-2b

# Convert Gemma 1.1 7B Instruct to Q4_K_M GGUF
poetry run python convert_hf_to_gguf.py --outfile models/gemma/gemma-1.1-7b-it.Q4_K_M.gguf --outtype auto models/gemma/gemma-1.1-7b-it
```

#### Llama Models
```bash
# Convert Llama 3.2 1B to Q4_K_M GGUF
poetry run python convert_hf_to_gguf.py --outfile models/llama/llama-3.2-1b.Q4_K_M.gguf --outtype auto models/llama/llama-3.2-1b
```

## Running Models

### Using llama-run
```bash
# Basic usage
./build/bin/llama-run models/gemma-2-2b-gguf "Your prompt here"

# Save output to file
./build/bin/llama-run models/gemma-2-2b-gguf "Your prompt here" > output.txt

# Save output and logs separately
./build/bin/llama-run models/gemma-2-2b-gguf "Your prompt here" > output.txt 2> log.txt
```

### Using llama-simple
```bash
# Run with specific token count (-n)
./build/bin/llama-simple -m models/gemma-2-2b-gguf -n 100 -p "Your prompt here" >> output.txt
```

### Using llama-cli
```bash
# Download and convert in one step
./build/bin/llama-cli -hf google/gemma-1.1-7b-it:Q4_K_M -m models/gemma/gemma-1.1-7b-it.Q4_K_M.gguf --hf-token your_huggingface_token
``` 
