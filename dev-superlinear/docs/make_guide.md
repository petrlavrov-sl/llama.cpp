# Build Guide

All commands in this guide are supposed to be executed from the repo root. (llama.cpp/)

Step 1: build the project
```bash
# Create a build directory
mkdir -p build
cmake --build build --config Release
```

This will create the build/bin dir with different executable build targets.
Of interest to us are
./build/bin/llama-run
./build/bin/llama-simple
./build/bin/llama-cli

To verify that the build was successful, run a simple test:
You need to download and convert to gguf format at least one model following the [model_setup.md] guide

```
./build/bin/llama-run ./models-superlinear/gemma-2-2b.gguf "Tell me about the history of artificial intelligence" > output.txt 2>log.txt
```
