# CLAUDE.md - llama.cpp Reference Guide

## Build Commands
```bash
# Standard build
cmake -B build && cmake --build build --config Release -j 8

# With CUDA
cmake -B build -DGGML_CUDA=ON && cmake --build build --config Release -j 8

# With Metal (macOS)
cmake -B build && cmake --build build --config Release -j 8
```

## Test Commands
```bash
# Run all tests
cd build && ctest

# Run specific test
cd build && ctest -R test-tokenizer-0

# Run single test with args
./build/bin/test-tokenizer-0 models/ggml-vocab-llama-spm.gguf
```

## Code Style Guidelines
- 4 spaces for indentation, brackets on same line
- Use `snake_case` for functions, variables, types
- Optimize for longest common prefix (`number_small` vs `small_number`)
- Type declarations: prefer `void * ptr` and `int & a` (right-side pointers/references)
- Use sized integer types (`int32_t`) in public API
- Enums are UPPERCASE with prefix (`LLAMA_VOCAB_TYPE_NONE`)
- C/C++ files: lowercase with dashes (.h, .c, .cpp)
- Python files: lowercase with underscores
- Follow existing patterns, keep code simple (avoid templates, fancy STL)