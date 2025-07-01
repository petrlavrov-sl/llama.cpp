# Superlinear llama.cpp Makefile
# Simple commands to avoid forgetting shell script meanings

.PHONY: help build-mac run-llama-run run-rng-service-mock download-models

# Default model settings
MODEL ?= models-superlinear/gemma-2-2b-it.gguf
PROMPT ?= "Tell me about the history of artificial intelligence"
OUTPUT_FILE ?= output.txt
LOG_FILE ?= log.txt

# RNG Service settings
PORT ?= 8000
HOST ?= 127.0.0.1
RNG_LOG_FILE ?= # Optional: set to path for request logs, empty = disable logging

help:
	@echo "Available commands:"
	@echo "  make build-mac         - Build llama.cpp for macOS"
	@echo "  make run-llama-run     - Run llama-run with model (use MODEL=path, PROMPT='text')"
	@echo "  make run-rng-service-mock - Run RNG service (use PORT=8000, HOST=127.0.0.1, RNG_FILE=path, RNG_LOG_FILE=path)"
	@echo "  make download-models   - Download models from HuggingFace"
	@echo "  make help              - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make run-llama-run MODEL=models-superlinear/llama-3.2-1b-instruct.gguf PROMPT='Hello world'"
	@echo "  make run-llama-run     # Uses defaults"
	@echo "  make run-rng-service-mock RNG_LOG_FILE=rng_requests.log  # Save request logs"
	@echo "  make run-rng-service-mock     # Disable request logging (cleaner output)"

build-mac:
	@echo "Building llama.cpp for macOS..."
	cmake -B build -DGGML_CUDA=OFF -DCMAKE_POLICY_VERSION_MINIMUM=3.5 || { \
		echo "❌ CMake configuration failed!"; \
		echo "💡 Try: rm -r ./build && make build-mac"; \
		exit 1; \
	}
	cmake --build build --config Release -j 8 || { \
		echo "❌ Build failed!"; \
		echo "💡 Try: rm -r ./build && make build-mac"; \
		exit 1; \
	}
	@echo "✅ Build complete! Binaries in ./build/bin/"

run-llama-run:
	@echo "Running llama-run with:"
	@echo "  Model: $(MODEL)"
	@echo "  Prompt: $(PROMPT)"
	@echo "  Output: $(OUTPUT_FILE)"
	@echo "  Log: $(LOG_FILE)"
	./build/bin/llama-run "$(MODEL)" "$(PROMPT)" > "$(OUTPUT_FILE)" 2>"$(LOG_FILE)"
	@echo "Done! Check $(OUTPUT_FILE) for results, $(LOG_FILE) for logs"

run-rng-service-mock:
	@echo "Starting RNG service on $(HOST):$(PORT)"
	@if [ -n "$(RNG_FILE)" ]; then \
		echo "Using RNG file: $(RNG_FILE)"; \
		RNG_FILE_ARG="--file ../../$(RNG_FILE)"; \
	else \
		echo "Generating random numbers on the fly"; \
		RNG_FILE_ARG=""; \
	fi; \
	if [ -n "$(RNG_LOG_FILE)" ]; then \
		echo "Request logs will be saved to: $(RNG_LOG_FILE)"; \
		cd tools-superlinear/rng_provider && poetry run python rng_service.py --host $(HOST) --port $(PORT) $$RNG_FILE_ARG --log-file "../../$(RNG_LOG_FILE)"; \
	else \
		echo "Request logging disabled"; \
		cd tools-superlinear/rng_provider && poetry run python rng_service.py --host $(HOST) --port $(PORT) $$RNG_FILE_ARG --no-access-logs; \
	fi
	# ✅ Added dynamic console speed display with rich library
	# Shows: requests/sec, bytes/sec, total requests, uptime, file progress

download-models:
	@echo "Model download not implemented yet"
	@echo "TODO: Implement HuggingFace model download"
	@echo "TODO: Handle HF_TOKEN authentication"
	@echo "TODO: Request access to gated models (Gemma, Llama)"
	@echo "TODO: Download and convert models to GGUF format"
	@echo ""
	@echo "For now, see docs-superlinear/model_setup.md for manual setup"
	@echo "Models should be placed in models-superlinear/ directory"
	@echo ""
	@echo "Available models based on your ls:"
	@echo "  - models-superlinear/gemma-2-2b-it.gguf"
	@echo "  - models-superlinear/llama-3.1-8b-instruct.gguf" 
	@echo "  - models-superlinear/llama-3.2-1b-instruct.gguf"

# TODO: Add more commands as needed
# TODO: make run-llama-server (with RNG provider service)
# TODO: make clean (clean build artifacts)
# TODO: make test (run basic model test)
# TODO: make check-models (verify downloaded models)
