#!/bin/bash

# Configuration
RNG_SERVICE_PORT=8000
RNG_SERVICE_HOST="127.0.0.1"
RNG_SERVICE_URL="http://${RNG_SERVICE_HOST}:${RNG_SERVICE_PORT}/random"

# Model configuration
MODEL_PATH="models/smollm-360m-instruct-add-basics-q8_0.gguf"
PARALLEL=4
GPU_LAYERS=99
CONTEXT_SIZE=4096
FLASH_ATTN=true

# Start RNG service in the background
echo "Starting RNG service..."
poetry run python tools-superlinear/rng_provider/rng_service.py --host "$RNG_SERVICE_HOST" --port "$RNG_SERVICE_PORT" &
RNG_SERVICE_PID=$!

# Wait for the service to start
sleep 2

# Check if the service is running
if ! curl -s "$RNG_SERVICE_URL" > /dev/null; then
    echo "Error: RNG service failed to start"
    kill $RNG_SERVICE_PID
    exit 1
fi

echo "RNG service is running at $RNG_SERVICE_URL"

# Build llama-server command
LLAMA_CMD="./build/bin/llama-server"
LLAMA_ARGS=(
    "-m" "$MODEL_PATH"
    "-np" "$PARALLEL"
    "-ngl" "$GPU_LAYERS"
    "-c" "$CONTEXT_SIZE"
)

if [ "$FLASH_ATTN" = true ]; then
    LLAMA_ARGS+=("-fa")
fi

# Set environment variables and run llama-server
echo "Starting llama-server..."
LLAMA_RNG_PROVIDER=external-api \
LLAMA_RNG_API_URL="$RNG_SERVICE_URL" \
$LLAMA_CMD "${LLAMA_ARGS[@]}"

# Cleanup
echo "Stopping RNG service..."
kill $RNG_SERVICE_PID 