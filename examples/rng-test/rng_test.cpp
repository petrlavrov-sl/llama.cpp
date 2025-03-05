#include "llama.h"
#include "common.h"

#include <cstdio>
#include <string>
#include <vector>

int main(int argc, char ** argv) {
    // Initialize llama backend
    llama_backend_init();

    // Parse command line arguments
    gpt_params params;
    params.model = "models/llama-3.2-1b.Q4_K_M.gguf"; // Default model
    
    if (argc > 1) {
        params.model = argv[1];
    }

    // Load the model
    llama_model_params model_params = llama_model_default_params();
    llama_model * model = llama_load_model_from_file(params.model.c_str(), model_params);
    if (model == NULL) {
        fprintf(stderr, "Failed to load model '%s'\n", params.model.c_str());
        return 1;
    }

    // Create context
    llama_context_params ctx_params = llama_context_default_params();
    ctx_params.n_ctx = 512;
    llama_context * ctx = llama_new_context_with_model(model, ctx_params);
    if (ctx == NULL) {
        fprintf(stderr, "Failed to create context\n");
        llama_free_model(model);
        return 1;
    }

    // Create a sampler chain with the default dist sampler
    struct llama_sampler_chain_params chain_params = llama_sampler_chain_default_params();
    struct llama_sampler * chain = llama_sampler_chain_init(chain_params);
    llama_sampler_chain_add(chain, llama_sampler_init_dist(42)); // Use seed 42

    // Tokenize a simple prompt
    const char * prompt = "Once upon a time";
    std::vector<llama_token> tokens(32);
    int n_tokens = llama_tokenize(llama_model_get_vocab(model), prompt, -1, tokens.data(), tokens.size(), true, false);
    tokens.resize(n_tokens);

    // Create a batch with the prompt
    llama_batch batch = llama_batch_init(n_tokens, 0, 1);
    for (int i = 0; i < n_tokens; i++) {
        batch.token[i] = tokens[i];
        batch.pos[i] = i;
        batch.n_seq_id[i] = 1;
        batch.seq_id[i][0] = 0;
        batch.logits[i] = 0;
    }

    // Process the batch
    if (llama_decode(ctx, batch) != 0) {
        fprintf(stderr, "Failed to decode\n");
        llama_batch_free(batch);
        llama_free(ctx);
        llama_free_model(model);
        return 1;
    }

    // Generate tokens with uniform distribution (default)
    printf("Generating tokens with uniform distribution:\n");
    for (int i = 0; i < 10; i++) {
        // Get logits from the last token
        float * logits = llama_get_logits_ith(ctx, n_tokens - 1);
        
        // Prepare token data array
        std::vector<llama_token_data> candidates;
        candidates.reserve(llama_vocab_n_tokens(llama_model_get_vocab(model)));
        for (int j = 0; j < llama_vocab_n_tokens(llama_model_get_vocab(model)); j++) {
            candidates.push_back({j, logits[j], 0.0f});
        }
        
        llama_token_data_array candidates_p = {candidates.data(), candidates.size(), 0, false};
        
        // Sample with the chain
        llama_sampler_apply(chain, &candidates_p);
        llama_token token = candidates_p.data[candidates_p.selected].id;
        
        // Print the token
        char token_text[32];
        int token_text_len = llama_token_to_piece(llama_model_get_vocab(model), token, token_text, sizeof(token_text), 0, true);
        token_text[token_text_len] = '\0';
        printf("Token %d: %s\n", i, token_text);
    }

    // Switch to normal distribution
    llama_set_rng_provider("normal", 42);
    
    printf("\nGenerating tokens with normal distribution:\n");
    for (int i = 0; i < 10; i++) {
        // Get logits from the last token
        float * logits = llama_get_logits_ith(ctx, n_tokens - 1);
        
        // Prepare token data array
        std::vector<llama_token_data> candidates;
        candidates.reserve(llama_vocab_n_tokens(llama_model_get_vocab(model)));
        for (int j = 0; j < llama_vocab_n_tokens(llama_model_get_vocab(model)); j++) {
            candidates.push_back({j, logits[j], 0.0f});
        }
        
        llama_token_data_array candidates_p = {candidates.data(), candidates.size(), 0, false};
        
        // Sample with the chain
        llama_sampler_apply(chain, &candidates_p);
        llama_token token = candidates_p.data[candidates_p.selected].id;
        
        // Print the token
        char token_text[32];
        int token_text_len = llama_token_to_piece(llama_model_get_vocab(model), token, token_text, sizeof(token_text), 0, true);
        token_text[token_text_len] = '\0';
        printf("Token %d: %s\n", i, token_text);
    }

    // Clean up
    llama_sampler_free(chain);
    llama_batch_free(batch);
    llama_free(ctx);
    llama_free_model(model);
    llama_backend_free();

    printf("\nRNG values have been saved to rng_values.txt and rng_values_normal.txt\n");
    printf("You can visualize them using the Python script:\n");
    printf("python tools/visualize_rng.py rng_values.txt\n");
    printf("python tools/visualize_rng.py rng_values_normal.txt\n");

    return 0;
} 