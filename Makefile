# Superlinear llama.cpp Makefile
# Simple commands to avoid forgetting shell script meanings

.PHONY: help build build-mac build-ubuntu run-llama-run run-rng-service test-fpga download-models run-with-fpga start-fpga stop-fpga visualize-rng-log check_hf_token download-llama-3-1-8b download-qwen3-8b download-gemma-3-12b download-gemma-2-2b download-llama-3-2-1b download-mistral-small

# Default model settings
MODEL ?= models/gemma-2-2b-it.gguf
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
	@echo "  make run-llama-run MODEL=models/llama-3.2-1b-instruct.gguf PROMPT='Hello world'"
	@echo "  make run-llama-run     # Uses defaults, saves to a timestamped folder in runs/"
	@echo "  make run-with-fpga ARGS='-c 2048' # Run with FPGA and custom llama arguments"
	@echo "  make run-rng-service FPGA_PORT=/dev/tty.usbserial-XXXX  # Force specific FPGA port"
	@echo "  make run-rng-service RNG_FILE=rng_values.txt  # Use file source (if no FPGA found)"
	@echo "  make run-rng-service     # Auto-detect FPGA, fallback to software generation"

build:
	@OS=$$(uname -s); \
	if [ "$$OS" = "Linux" ]; then \
		echo "Building llama.cpp for Linux/Ubuntu..."; \
		CUDA_FLAG="-DGGML_CUDA=OFF"; \
		if command -v nvcc >/dev/null 2>&1; then \
			CUDA_FLAG="-DGGML_CUDA=ON"; \
		fi; \
		CMAKE_FLAGS="$$CUDA_FLAG -DCMAKE_BUILD_TYPE=Release"; \
		JOBS=$$(nproc); \
	elif [ "$$OS" = "Darwin" ]; then \
		echo "Building llama.cpp for macOS..."; \
		METAL_FLAG="-DGGML_METAL=OFF"; \
		if [ "$$(uname -m)" = "arm64" ]; then \
			METAL_FLAG="-DGGML_METAL=ON"; \
		fi; \
		CMAKE_FLAGS="-DGGML_CUDA=OFF $$METAL_FLAG -DCMAKE_BUILD_TYPE=Release"; \
		JOBS=$$(sysctl -n hw.logicalcpu); \
	else \
		echo "Unsupported OS: $$OS"; \
		exit 1; \
	fi; \
	cmake -B build $$CMAKE_FLAGS || { \
		echo "❌ CMake configuration failed!"; \
		echo "💡 Try: rm -rf ./build && make build"; \
		exit 1; \
	};
	cmake --build build --config Release -j $$JOBS || { \
		echo "❌ Build failed!"; \
		echo "💡 Try: rm -rf ./build && make build"; \
		exit 1; \
	};
	@echo "✅ Build complete! Binaries in ./build/bin/"

build-ubuntu:
	@echo "Building llama.cpp for Ubuntu..."
	cmake -B build -DLLAMA_CUDA=ON -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 || { \
    		echo "❌ CMake configuration failed!"; \
    		echo "💡 Try: rm -r ./build && make build-ubuntu"; \
    		exit 1; \
	}
	cmake --build build --config Release -j 8 || { \
		echo "❌ Build failed!"; \
		echo "💡 Try: rm -r ./build && make build-mac"; \
		exit 1; \
	}
	@echo "✅ Build complete! Binaries in ./build/bin/"

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

# Example:
# make run-with-fpga MODEL=./models/gemma-2-2b-it.gguf ARGS="-c 4096 --temp 0.5"
run-llama-run-with-fpga: build
	@set -e; \
	echo "🚀 Running llama-run with direct FPGA RNG..."; \
	mkdir -p "$(RUN_DIR)"; \
	echo "📝 Outputs will be saved in $(RUN_DIR)"; \
	echo "🔎 Attempting to auto-detect FPGA device..."; \
	FPGA_DEVICE=$$(cd tools-superlinear/rng_provider && poetry run python run_auto_detect.py); \
	if [ -z "$$FPGA_DEVICE" ]; then \
		echo "❌ Error: Could not auto-detect FPGA device."; \
		exit 1; \
	fi; \
	echo "✅ FPGA device detected at: $$FPGA_DEVICE"; \
	sleep 0.1; \
	echo "⚡ Starting FPGA stream..."; \
	cd $(CURDIR)/tools-superlinear/rng_provider && poetry run python run_start_fpga.py "$$FPGA_DEVICE"; \
	\
	export LLAMA_RNG_PROVIDER="fpga-serial"; \
	export LLAMA_FPGA_PORT="$$FPGA_DEVICE"; \
	export LLAMA_FPGA_BAUDRATE="$(FPGA_BAUDRATE)"; \
	export LLAMA_RNG_DEBUG="1"; \
	export LLAMA_RNG_OUTPUT="$(RNG_VALUES_FILE)"; \
	\
	cd $(CURDIR); \
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
	echo "⚡ Stopping FPGA stream..."; \
	cd $(CURDIR)/tools-superlinear/rng_provider && poetry run python run_stop_fpga.py "$$FPGA_DEVICE"; \
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

visualize-rng-log:
	@LOG_FILE_PATH=${LOG_FILE} ; \
	if [ -z "$${LOG_FILE_PATH}" ]; then \
		echo "Usage: make visualize-rng-log LOG_FILE=<path-to-log-file>"; \
		echo "Example: make visualize-rng-log LOG_FILE=runs/run_20250709_103000/rng_values.txt"; \
		exit 1; \
	fi; \
	echo "📊 Starting visualizer for: $${LOG_FILE_PATH}"; \
	cd tools-superlinear/rng_provider && poetry run python rng_visualizer.py --file ../../$${LOG_FILE_PATH}

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

check_hf_token:
	@if [ -z "$$HF_TOKEN" ]; then \
		echo "❌ HF_TOKEN environment variable not set!"; \
		echo "💡 Run: export HF_TOKEN=<your_huggingface_token> or use huggingface-cli login"; \
		exit 1; \
	else \
		echo "✅ HF_TOKEN is set. Proceeding with downloads..."; \
	fi

# Individual model download targets
download-gemma-2-2b: check_hf_token
	@if [ -f "./models/gemma-2-2b-it.gguf" ]; then \
		echo "✅ Gemma-2-2B-IT already downloaded. Skipping."; \
	else \
		echo "Downloading Gemma-2-2B-IT..."; \
		mkdir -p models/gemma/gemma-2-2b-it/huggingface; \
		poetry run huggingface-cli download google/gemma-2-2b-it --local-dir ./models/gemma/gemma-2-2b-it/huggingface || { \
			echo "❌ Failed to download Gemma-2-2B-IT"; \
			echo "💡 Ensure you have access to google/gemma-2-2b-it"; \
			exit 1; \
		}; \
		echo "Converting Gemma-2-2B-IT to GGUF..."; \
		poetry run python convert_hf_to_gguf.py --outfile ./models/gemma-2-2b-it.gguf ./models/gemma/gemma-2-2b-it/huggingface || { \
			echo "❌ Failed to convert Gemma-2-2B-IT"; \
			exit 1; \
		}; \
	fi

download-llama-3-2-1b: check_hf_token
	@if [ -f "./models/llama-3.2-1b-instruct.gguf" ]; then \
		echo "✅ Llama-3.2-1B-Instruct already downloaded. Skipping."; \
	else \
		echo "Downloading Llama-3.2-1B-Instruct..."; \
		mkdir -p models/llama/llama-3.2-1b-instruct/huggingface; \
		poetry run huggingface-cli download meta-llama/Llama-3.2-1B-Instruct --local-dir ./models/llama/llama-3.2-1b-instruct/huggingface || { \
			echo "❌ Failed to download Llama-3.2-1B-Instruct"; \
			echo "💡 Ensure you have access to meta-llama/Llama-3.2-1B-Instruct and HF_TOKEN is valid"; \
			exit 1; \
		}; \
		echo "Converting Llama-3.2-1B-Instruct to GGUF..."; \
		poetry run python convert_hf_to_gguf.py --outfile ./models/llama-3.2-1b-instruct.gguf ./models/llama/llama-3.2-1b-instruct/huggingface || { \
			echo "❌ Failed to convert Llama-3.2-1B-Instruct"; \
			exit 1; \
		}; \
	fi

download-llama-3-1-8b: check_hf_token
	@if [ -f "./models/llama-3.1-8b-instruct.gguf" ]; then \
		echo "✅ Llama-3.1-8B-Instruct already downloaded. Skipping."; \
	else \
		echo "Downloading Llama-3.1-8B-Instruct..."; \
		mkdir -p models/llama/llama-3.1-8b-instruct/huggingface; \
		poetry run huggingface-cli download meta-llama/Llama-3.1-8B-Instruct --local-dir ./models/llama/llama-3.1-8b-instruct/huggingface  || { \
			echo "❌ Failed to download Llama-3.1-8B-Instruct"; \
			echo "💡 Ensure you have access to meta-llama/Llama-3.1-8B-Instruct"; \
			exit 1; \
		}; \
		echo "Converting Llama-3.1-8B-Instruct to GGUF..."; \
		poetry run python convert_hf_to_gguf.py --outfile ./models/llama-3.1-8b-instruct.gguf ./models/llama/llama-3.1-8b-instruct/huggingface || { \
			echo "❌ Failed to convert Llama-3.1-8B-Instruct"; \
			exit 1; \
		}; \
	fi
download-gemma-3-12b: check_hf_token
	@if [ -f "./models/gemma-3-12b-it.gguf" ]; then \
		echo "✅ Gemma-3-12B-IT already downloaded. Skipping."; \
	else \
		echo "Downloading Gemma-3-12B-IT (pre-converted GGUF)..."; \
		mkdir -p models; \
		poetry run huggingface-cli download unsloth/gemma-3-12b-it-GGUF --local-dir ./models || { \
			echo "❌ Failed to download Gemma-3-12B-IT GGUF"; \
			echo "💡 Ensure you have access to unsloth/gemma-3-12b-it-GGUF"; \
			exit 1; \
		}; \
		mv ./models/gemma-3-12b-it.Q4_K_M.gguf ./models/gemma-3-12b-it.gguf 2>/dev/null || true; \
		echo "✅ Downloaded Gemma-3-12B-IT GGUF successfully"; \
	fi

download-gemma-3-4b: check_hf_token
	@if [ -f "./models/gemma-3-4b-it.gguf" ]; then \
		echo "✅ Gemma-3-4B-IT already downloaded. Skipping."; \
	else \
		echo "Downloading Gemma-3-4B-IT (pre-converted GGUF)..."; \
		mkdir -p models; \
		poetry run huggingface-cli download unsloth/gemma-3-4b-it-GGUF --local-dir ./models || { \
			echo "❌ Failed to download Gemma-3-4B-IT GGUF"; \
			echo "💡 Ensure you have access to unsloth/gemma-3-4b-it-GGUF"; \
			exit 1; \
		}; \
		mv ./models/gemma-3-4b-it.Q4_K_M.gguf ./models/gemma-3-4b-it.gguf 2>/dev/null || true; \
		echo "✅ Downloaded Gemma-3-4B-IT GGUF successfully"; \
	fi

download-mistral-7b: check_hf_token
	@if [ -f "./models/mistral-7b-instruct-v0.3.gguf" ]; then \
		echo "✅ Mistral-7B-Instruct-v0.3 already downloaded. Skipping."; \
	else \
		echo "Downloading Mistral-7B-Instruct-v0.3 (pre-converted GGUF)..."; \
		mkdir -p models; \
		poetry run huggingface-cli download MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF --local-dir ./models || { \
			echo "❌ Failed to download Mistral-7B-Instruct-v0.3 GGUF"; \
			echo "💡 Ensure you have access to MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF"; \
			exit 1; \
		}; \
		mv ./models/mistral-7b-instruct-v0.3.Q4_K_M.gguf ./models/mistral-7b-instruct-v0.3.gguf 2>/dev/null || true; \
		echo "✅ Downloaded Mistral-7B-Instruct-v0.3 GGUF successfully"; \
	fi

download-qwen3-8b: check_hf_token
	@if [ -f "./models/qwen3-8b.gguf" ]; then \
		echo "✅ Qwen3-8B already downloaded. Skipping."; \
	else \
		echo "Downloading Qwen3-8B (pre-converted GGUF)..."; \
		mkdir -p models; \
		poetry run huggingface-cli download unsloth/Qwen3-8B-GGUF --local-dir ./models || { \
			echo "❌ Failed to download Qwen3-8B GGUF"; \
			echo "💡 Ensure you have access to unsloth/Qwen3-8B-GGUF"; \
			exit 1; \
		}; \
		mv ./models/qwen3-8b.Q4_K_M.gguf ./models/qwen3-8b.gguf 2>/dev/null || true; \
		echo "✅ Downloaded Qwen3-8B GGUF successfully"; \
	fi

# Main download target that depends on all individual model downloads
download-models: download-gemma-2-2b download-llama-3-2-1b download-llama-3-1-8b download-gemma-3-12b download-gemma-3-4b download-mistral-7b download-qwen3-8b
	@echo "✅ Model download and conversion complete!"
	@echo "Available models based on your setup:"
	@echo "  - models/gemma-2-2b-it.gguf"
	@echo "  - models/gemma-3-12b-it.gguf"
	@echo "  - models/gemma-3-4b-it.gguf"
	@echo "  - models/llama-3.1-8b-instruct.gguf"
	@echo "  - models/llama-3.2-1b-instruct.gguf"
	@echo "  - models/qwen3-8b.gguf"
	@echo "  - models/mistral-7b-instruct-v0.3.gguf"

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
