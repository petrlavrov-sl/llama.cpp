# Superlinear llama.cpp Makefile
# Simple commands to avoid forgetting shell script meanings

.PHONY: help build-mac run-llama-run run-rng-service test-fpga download-models run-with-fpga start-fpga stop-fpga

# Default model settings
MODEL ?= models-superlinear/gemma-2-2b-it.gguf
PROMPT ?= "Tell me about the history of artificial intelligence"

# --- Run directory setup ---
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)
RUN_DIR ?= runs/run_$(TIMESTAMP)
OUTPUT_FILE ?= $(RUN_DIR)/output.txt
LOG_FILE ?= $(RUN_DIR)/log.txt
RNG_VALUES_FILE ?= $(RUN_DIR)/rng_values.txt

ARGS ?= ""

# RNG Service settings
PORT ?= 8000
HOST ?= 127.0.0.1
RNG_FILE ?= # Optional: set to path for RNG file, empty = auto-detect FPGA then software generation
FPGA_PORT ?= # Optional: force specific FPGA port (e.g., /dev/tty.usbserial-XXXX), empty = auto-detect
FPGA_BAUDRATE ?= 921600
RNG_LOG_FILE ?= # Optional: set to path for request logs, empty = disable logging

help:
	@echo "Available commands:"
	@echo "  make build-mac         - Build llama.cpp for macOS"
	@echo "  make run-llama-run     - Run llama-run with model (use MODEL=path, PROMPT='text')"
	@echo "  make run-with-fpga     - Run llama-run with direct FPGA RNG (use MODEL=, PROMPT=, ARGS=)"
	@echo "  make start-fpga        - Send start (toggle) signal to FPGA"
	@echo "  make stop-fpga         - Send stop (toggle) signal to FPGA"
	@echo "  make run-rng-service     - Run RNG service (auto-detects FPGA, use PORT=8000, HOST=127.0.0.1, RNG_FILE=path, RNG_LOG_FILE=path)"
	@echo "  make test-fpga           - Test FPGA connection only (use FPGA_PORT=port to force specific port)"
	@echo "  make download-models   - Download models from HuggingFace"
	@echo "  make help              - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make run-llama-run MODEL=models-superlinear/llama-3.2-1b-instruct.gguf PROMPT='Hello world'"
	@echo "  make run-llama-run     # Uses defaults, saves to a timestamped folder in runs/"
	@echo "  make run-with-fpga ARGS='-c 2048' # Run with FPGA and custom llama arguments"
	@echo "  make run-rng-service FPGA_PORT=/dev/tty.usbserial-XXXX  # Force specific FPGA port"
	@echo "  make run-rng-service RNG_FILE=rng_values.txt  # Use file source (if no FPGA found)"
	@echo "  make run-rng-service     # Auto-detect FPGA, fallback to software generation"

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

run-with-fpga: build-mac
	@set -e; \
	echo "🚀 Running llama-run with direct FPGA RNG..."; \
	@mkdir -p "$(RUN_DIR)"; \
	echo "📝 Outputs will be saved in $(RUN_DIR)"; \
	echo "🔎 Attempting to auto-detect FPGA device..."; \
	@FPGA_DEVICE=$$(cd tools-superlinear/rng_provider && poetry run python run_auto_detect.py); \
	if [ -z "$$FPGA_DEVICE" ]; then \
		echo "❌ Error: Could not auto-detect FPGA device."; \
		exit 1; \
	fi; \
	echo "✅ FPGA device detected at: $$FPGA_DEVICE"; \
	\
	trap 'echo "🔌 Stopping FPGA stream..."; cd tools-superlinear/rng_provider && poetry run python run_stop_fpga.py "$$FPGA_DEVICE"' EXIT; \
	\
	echo "⚡ Starting FPGA stream..."; \
	cd tools-superlinear/rng_provider && poetry run python run_start_fpga.py "$$FPGA_DEVICE"; \
	\
	export LLAMA_RNG_PROVIDER="fpga-serial"; \
	export LLAMA_FPGA_PORT="$$FPGA_DEVICE"; \
	export LLAMA_FPGA_BAUDRATE="$(FPGA_BAUDRATE)"; \
	export LLAMA_RNG_DEBUG="1"; \
	export LLAMA_RNG_OUTPUT="$(RNG_VALUES_FILE)"; \
	\
	echo "🔧 Environment variables set, running llama-run with:"; \
	echo "   - Model: $(MODEL)"; \
	echo "   - Prompt: $(PROMPT)"; \
	echo "   - Extra args: $(ARGS)"; \
	echo "   - Output: $(OUTPUT_FILE)"; \
	echo "   - Log: $(LOG_FILE)"; \
	echo "   - RNG Data: $(RNG_VALUES_FILE)"; \
	echo "------------------------------------------"; \
	./build/bin/llama-run "$(MODEL)" "$(PROMPT)" $(ARGS) > "$(OUTPUT_FILE)" 2>"$(LOG_FILE)"; \
	echo "------------------------------------------"; \
	echo "✅ Execution finished. Check $(RUN_DIR) for outputs."

run-llama-run:
	@mkdir -p "$(RUN_DIR)"; \
	echo "📝 Outputs will be saved in $(RUN_DIR)"; \
	echo "Running llama-run with:"
	@echo "  Model: $(MODEL)"
	@echo "  Prompt: $(PROMPT)"
	@echo "  Output: $(OUTPUT_FILE)"
	@echo "  Log: $(LOG_FILE)"
	./build/bin/llama-run "$(MODEL)" "$(PROMPT)" > "$(OUTPUT_FILE)" 2>"$(LOG_FILE)"
	@echo "Done! Check $(RUN_DIR) for results"

run-rng-service:
	@echo "Starting RNG service on $(HOST):$(PORT)"
	@echo "🔍 Auto-detecting FPGA device..."
	@ARGS="--host $(HOST) --port $(PORT)"; \
	if [ -n "$(FPGA_PORT)" ]; then \
		echo "⚡ Forcing FPGA port: $(FPGA_PORT) at $(FPGA_BAUDRATE) baud"; \
		ARGS="$$ARGS --fpga-port $(FPGA_PORT) --fpga-baudrate $(FPGA_BAUDRATE)"; \
	elif [ -n "$(RNG_FILE)" ]; then \
		echo "📁 Using RNG file: $(RNG_FILE) (FPGA auto-detect will still be attempted)"; \
		ARGS="$$ARGS --file ../../$(RNG_FILE)"; \
	fi; \
	if [ -n "$(RNG_LOG_FILE)" ]; then \
		echo "📝 Request logs will be saved to: $(RNG_LOG_FILE)"; \
		ARGS="$$ARGS --log-file ../../$(RNG_LOG_FILE)"; \
	else \
		echo "🚫 Request logging disabled"; \
		ARGS="$$ARGS --no-access-logs"; \
	fi; \
	cd tools-superlinear/rng_provider && poetry run python rng_service.py $$ARGS
	# ✅ Auto-detects FPGA quantum RNG source with live throughput display
	# Priority: FPGA → File → Software generation
	# Shows: requests/sec, bytes/sec, total requests, uptime, FPGA stats

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

start-fpga:
	@echo "🚀 Starting FPGA stream..."
	@FPGA_DEVICE=$$(cd tools-superlinear/rng_provider && poetry run python run_auto_detect.py); \
	if [ -z "$$FPGA_DEVICE" ]; then \
		echo "❌ Error: Could not auto-detect FPGA device."; \
		exit 1; \
	fi; \
	cd tools-superlinear/rng_provider && poetry run python run_start_fpga.py "$$FPGA_DEVICE"

stop-fpga:
	@echo "🔌 Stopping FPGA stream..."
	@FPGA_DEVICE=$$(cd tools-superlinear/rng_provider && poetry run python run_auto_detect.py); \
	if [ -z "$$FPGA_DEVICE" ]; then \
		echo "❌ Error: Could not auto-detect FPGA device."; \
		exit 1; \
	fi; \
	cd tools-superlinear/rng_provider && poetry run python run_stop_fpga.py "$$FPGA_DEVICE"

# TODO: Add more commands as needed
# TODO: make run-llama-server (with RNG provider service)
# TODO: make clean (clean build artifacts)
# TODO: make test (run basic model test)
# TODO: make check-models (verify downloaded models)
