# Model Setup Guide

This guide explains how to download a model for use with llama.cpp. **Do this step first before building.**

## Quick Start (Download One Model)

If you just want to get started quickly, download the Gemma 2 2B model:

```bash
# Install dependencies
poetry update
poetry install
poetry add huggingface_hub

# Set Hugging Face token (get this from https://huggingface.co/settings/tokens)
export HF_TOKEN=your_huggingface_token

# Request access to Gemma at https://huggingface.co/google/gemma-2-2b
# Click "Access repository" and accept the terms

# Download Gemma 2 2B (smallest model, good for testing)
poetry run huggingface-cli download google/gemma-2-2b --local-dir ./models-superlinear/gemma/gemma-2-2b/huggingface

# Convert to GGUF format
poetry run python convert_hf_to_gguf.py --outfile ./models-superlinear/gemma-2-2b.gguf ./models-superlinear/gemma/gemma-2-2b/huggingface
```

After downloading and converting this model, proceed to the [Build Guide](build_guide.md).

## Full Model Setup (Optional)

If you want to download all models, follow these steps after you've verified everything works with the first model.

### Authentication

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

### Request Model Access

You need to request access to the models before downloading them:

#### Gemma Models
1. Request access to Gemma models at [Google Gemma Access Form](https://huggingface.co/google/gemma-2-2b)
2. Click on "Access repository" button
3. Accept the terms and conditions

#### Llama Models
1. Request access to Llama models at [Meta Llama Access Form](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
2. Click on "Access repository" button
3. Accept the terms and conditions

### Downloading All Models

```bash
# Download all models
poetry run huggingface-cli download meta-llama/Llama-3.2-1B-Instruct --local-dir ./models-superlinear/llama/llama-3.2-1b-instruct/huggingface && \
poetry run huggingface-cli download meta-llama/Llama-3.1-8B-Instruct --local-dir ./models-superlinear/llama/llama-3.1-8b-instruct/huggingface && \
poetry run huggingface-cli download meta-llama/Llama-3.1-8B --local-dir ./models-superlinear/llama/llama-3.1-8b/huggingface && \
poetry run huggingface-cli download google/gemma-2-2b-it --local-dir ./models-superlinear/gemma/gemma-2-2b-it/huggingface
```

### Converting All Models to GGUF

```bash
# Convert all models
poetry run python convert_hf_to_gguf.py --outfile ./models-superlinear/llama-3.2-1b-instruct.gguf ./models-superlinear/llama/llama-3.2-1b-instruct/huggingface && \
poetry run python convert_hf_to_gguf.py --outfile ./models-superlinear/llama-3.1-8b-instruct.gguf ./models-superlinear/llama/llama-3.1-8b-instruct/huggingface && \
poetry run python convert_hf_to_gguf.py --outfile ./models-superlinear/llama-3.1-8b.gguf ./models-superlinear/llama/llama-3.1-8b/huggingface && \
poetry run python convert_hf_to_gguf.py --outfile ./models-superlinear/gemma-2-2b-it.gguf ./models-superlinear/gemma/gemma-2-2b-it/huggingface
```

## Verifying Models

To verify that the models were downloaded and converted correctly:

```bash
# List the downloaded models
ls -lh ./models-superlinear/*.gguf

# Test a model with a simple prompt
./build/bin/llama-simple -m ./models-superlinear/gemma-2-2b.gguf -p "Hello, world!" -n 20
```

## Troubleshooting

### Common Issues

1. **Authentication errors**: Make sure your HF_TOKEN is set correctly
   ```bash
   # Check if token is set
   echo $HF_TOKEN
   
   # Reset token if needed
   export HF_TOKEN=your_huggingface_token
   ```

2. **Download fails**: Ensure you have accepted the model license on Hugging Face

3. **Conversion errors**: Check that the model files were downloaded correctly
   ```bash
   # Check if model files exist
   ls -la ./models-superlinear/llama/llama-3.2-1b-instruct/huggingface
   ```

4. **Permission denied**: Fix permissions if needed
   ```bash
   # Fix permissions
   chmod -R 755 ./models-superlinear
   ``` 