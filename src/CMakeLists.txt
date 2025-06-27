llama_add_compile_flags()

#
# libraries
#

# Find libcurl
find_package(CURL REQUIRED)
# Include nlohmann/json as a header-only library
include(FetchContent)
FetchContent_Declare(
    json
    URL https://github.com/nlohmann/json/releases/download/v3.11.2/json.tar.xz
)
FetchContent_MakeAvailable(json)

# llama
add_library(llama
            ../include/llama.h
            llama.cpp
            llama-adapter.cpp
            llama-arch.cpp
            llama-batch.cpp
            llama-chat.cpp
            llama-context.cpp
            llama-grammar.cpp
            llama-hparams.cpp
            llama-impl.cpp
            llama-kv-cache.cpp
            llama-mmap.cpp
            llama-model-loader.cpp
            llama-model.cpp
            llama-quant.cpp
            llama-sampling.cpp
            llama-vocab.cpp
            unicode.h
            unicode.cpp
            unicode-data.cpp
            )

target_include_directories(llama PUBLIC . ../include ../common)
target_compile_features   (llama PUBLIC cxx_std_17) # don't bump

target_link_libraries(llama PUBLIC ggml CURL::libcurl nlohmann_json::nlohmann_json)

if (BUILD_SHARED_LIBS)
    set_target_properties(llama PROPERTIES POSITION_INDEPENDENT_CODE ON)
    target_compile_definitions(llama PRIVATE LLAMA_BUILD)
    target_compile_definitions(llama PUBLIC  LLAMA_SHARED)
endif()
