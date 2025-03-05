#ifndef LLAMA_RNG_PROVIDER_H
#define LLAMA_RNG_PROVIDER_H

#include <random>
#include <cstdint>

// Interface for RNG providers
struct llama_rng_provider_i {
    // Generate a random number between 0 and 1
    double (*generate)(void* ctx);
    
    // Clone the provider
    void* (*clone)(const void* ctx);
    
    // Reset the provider
    void (*reset)(void* ctx, uint32_t seed);
    
    // Free the provider
    void (*free)(void* ctx);
};

// RNG provider structure
struct llama_rng_provider {
    const struct llama_rng_provider_i* iface;
    void* ctx;
};

// Initialize an RNG provider
struct llama_rng_provider* llama_rng_provider_init(
    const struct llama_rng_provider_i* iface,
    void* ctx
);

// Generate a random number between 0 and 1
double llama_rng_provider_generate(struct llama_rng_provider* provider);

// Clone an RNG provider
struct llama_rng_provider* llama_rng_provider_clone(const struct llama_rng_provider* provider);

// Reset an RNG provider with a new seed
void llama_rng_provider_reset(struct llama_rng_provider* provider, uint32_t seed);

// Free an RNG provider
void llama_rng_provider_free(struct llama_rng_provider* provider);

// Initialize the default RNG provider
struct llama_rng_provider* llama_rng_provider_init_default(uint32_t seed);

#endif // LLAMA_RNG_PROVIDER_H 