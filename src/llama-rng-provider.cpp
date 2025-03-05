 #include "llama-rng-provider.h"
#include "common.h"

#include <cstdlib>
#include <cstring>
#include <random>

// Default RNG provider implementation
struct llama_rng_provider_default {
    uint32_t seed;
    uint32_t seed_cur;
    std::mt19937 rng;
};

// Generate a random number between 0 and 1
static double llama_rng_provider_default_generate(void* ctx) {
    auto* provider_ctx = (llama_rng_provider_default*)ctx;
    return std::uniform_real_distribution<>(0.0, 1.0)(provider_ctx->rng);
}

// Clone the provider
static void* llama_rng_provider_default_clone(const void* ctx) {
    const auto* provider_ctx = (const llama_rng_provider_default*)ctx;
    auto* new_ctx = new llama_rng_provider_default{
        /* .seed     = */ provider_ctx->seed,
        /* .seed_cur = */ provider_ctx->seed_cur,
        /* .rng      = */ provider_ctx->rng,
    };
    return new_ctx;
}

// Reset the provider
static void llama_rng_provider_default_reset(void* ctx, uint32_t seed) {
    auto* provider_ctx = (llama_rng_provider_default*)ctx;
    provider_ctx->seed = seed;
    provider_ctx->seed_cur = get_rng_seed(seed);
    provider_ctx->rng.seed(provider_ctx->seed_cur);
}

// Free the provider
static void llama_rng_provider_default_free(void* ctx) {
    delete (llama_rng_provider_default*)ctx;
}

// Default RNG provider interface
static struct llama_rng_provider_i llama_rng_provider_default_i = {
    /* .generate = */ llama_rng_provider_default_generate,
    /* .clone    = */ llama_rng_provider_default_clone,
    /* .reset    = */ llama_rng_provider_default_reset,
    /* .free     = */ llama_rng_provider_default_free,
};

// Initialize an RNG provider
struct llama_rng_provider* llama_rng_provider_init(
    const struct llama_rng_provider_i* iface,
    void* ctx
) {
    auto* provider = new llama_rng_provider{
        /* .iface = */ iface,
        /* .ctx   = */ ctx,
    };
    return provider;
}

// Generate a random number between 0 and 1
double llama_rng_provider_generate(struct llama_rng_provider* provider) {
    return provider->iface->generate(provider->ctx);
}

// Clone an RNG provider
struct llama_rng_provider* llama_rng_provider_clone(const struct llama_rng_provider* provider) {
    void* new_ctx = provider->iface->clone(provider->ctx);
    return llama_rng_provider_init(provider->iface, new_ctx);
}

// Reset an RNG provider with a new seed
void llama_rng_provider_reset(struct llama_rng_provider* provider, uint32_t seed) {
    provider->iface->reset(provider->ctx, seed);
}

// Free an RNG provider
void llama_rng_provider_free(struct llama_rng_provider* provider) {
    provider->iface->free(provider->ctx);
    delete provider;
}

// Initialize the default RNG provider
struct llama_rng_provider* llama_rng_provider_init_default(uint32_t seed) {
    auto seed_cur = get_rng_seed(seed);
    auto* ctx = new llama_rng_provider_default{
        /* .seed     = */ seed,
        /* .seed_cur = */ seed_cur,
        /* .rng      = */ std::mt19937(seed_cur),
    };
    return llama_rng_provider_init(&llama_rng_provider_default_i, ctx);
} 