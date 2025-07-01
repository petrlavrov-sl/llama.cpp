// A basic application simulating a server with multiple clients.
// The clients submit requests to the server and they are processed in parallel.

#include "arg.h"
#include "common.h"
#include "sampling.h"
#include "log.h"
#include "llama.h"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
#include <ctime>
#include <fstream>
#include <unordered_map>

// trim whitespace from the beginning and end of a string
static std::string trim(const std::string & str) {
    size_t start = 0;
    size_t end = str.size();

    while (start < end && isspace(str[start])) {
        start += 1;
    }

    while (end > start && isspace(str[end - 1])) {
        end -= 1;
    }

    return str.substr(start, end - start);
}

static std::string k_system =
R"(Transcript of a never ending dialog, where the User interacts with an Assistant.
The Assistant is helpful, kind, honest, good at writing, and never fails to answer the User's requests immediately and with precision.

User: Recommend a nice restaurant in the area.
Assistant: I recommend the restaurant "The Golden Duck". It is a 5 star restaurant with a great view of the city. The food is delicious and the service is excellent. The prices are reasonable and the portions are generous. The restaurant is located at 123 Main Street, New York, NY 10001. The phone number is (212) 555-1234. The hours are Monday through Friday from 11:00 am to 10:00 pm. The restaurant is closed on Saturdays and Sundays.
User: Who is Richard Feynman?
Assistant: Richard Feynman was an American physicist who is best known for his work in quantum mechanics and particle physics. He was awarded the Nobel Prize in Physics in 1965 for his contributions to the development of quantum electrodynamics. He was a popular lecturer and author, and he wrote several books, including "Surely You're Joking, Mr. Feynman!" and "What Do You Care What Other People Think?".
User:)";

// No more default prompts - prompts will be loaded from file
std::vector<std::string> k_prompts;

struct client {
    ~client() {
        if (smpl) {
            common_sampler_free(smpl);
        }
    }

    int32_t id = 0;

    llama_seq_id seq_id = -1;

    llama_token sampled;

    int64_t t_start_prompt;
    int64_t t_start_gen;

    int32_t n_prompt  = 0;
    int32_t n_decoded = 0;
    int32_t i_batch   = -1;

    std::string input;
    std::string prompt;
    std::string response;

    struct common_sampler * smpl = nullptr;
};

// Structure to track prompt-response pairs
struct prompt_response {
    std::string prompt;
    std::string response;
    int64_t processing_time_us;
    int32_t prompt_tokens;
    int32_t response_tokens;
};

static void print_date_time() {
    std::time_t current_time = std::time(nullptr);
    std::tm* local_time = std::localtime(&current_time);
    char buffer[80];
    strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", local_time);

    LOG_INF("\n");
    LOG_INF("\033[35mrun parameters as of %s\033[0m\n", buffer);
    LOG_INF("\n");
}

// Define a split string function to ...
static std::vector<std::string> split_string(const std::string& input, char delimiter) {
    std::vector<std::string> tokens;
    std::istringstream stream(input);
    std::string token;
    while (std::getline(stream, token, delimiter)) {
        tokens.push_back(token);
    }
    return tokens;
}

// Print custom usage information
static void print_custom_usage(const char* program_name) {
    fprintf(stderr, "\nAdditional parameters for parallel processing:\n");
    fprintf(stderr, "  -f, --file FNAME         input file with prompts (REQUIRED, one prompt per line)\n");
    fprintf(stderr, "  -o, --output-file FNAME  save results to specified file\n");
    fprintf(stderr, "\nUsage example:\n");
    fprintf(stderr, "  %s -m models/7B/ggml-model-q4_0.bin -f prompts.txt -o results.txt --n-parallel 4\n\n", program_name);
}

// Process custom command line arguments
bool process_custom_arguments(int argc, char ** argv, std::string & output_file) {
    bool file_arg_present = false;
    
    // Check if help is requested
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            // Print our custom usage first
            print_custom_usage(argv[0]);
            // Don't modify these, let common_params_parse handle them
            continue;
        }
        
        // Check if file argument is present
        if (arg == "-f" || arg == "--file") {
            file_arg_present = true;
        }
    }
    
    if (!file_arg_present) {
        fprintf(stderr, "\033[31mError: No prompt file specified. A file with prompts is required.\033[0m\n");
        fprintf(stderr, "Please provide a file with prompts using the -f/--file option.\n\n");
        print_custom_usage(argv[0]);
        return false;
    }
    
    for (int i = 1; i < argc - 1; i++) {
        std::string arg = argv[i];
        
        if (arg == "--output-file" || arg == "-o") {
            output_file = argv[++i];
            // Skip this argument so it won't be processed by common_params_parse
            argv[i-1] = argv[i] = (char *)"";
        }
    }
    
    return true;
}

int main(int argc, char ** argv) {
    srand(1234);

    common_params params;
    
    // custom parameters not handled by common_params
    std::string output_file_path;
    
    // Container to store all prompt-response pairs
    std::vector<prompt_response> results;

    // Process our custom arguments first
    if (!process_custom_arguments(argc, argv, output_file_path)) {
        return 1;
    }

    if (!common_params_parse(argc, argv, params, LLAMA_EXAMPLE_PARALLEL)) {
        return 1;
    }

    common_init();

    // number of simultaneous "clients" to simulate
    const int32_t n_clients = params.n_parallel;

    // dedicate one sequence to the system prompt
    params.n_parallel += 1;

    // requests to simulate
    const int32_t n_seq_param = params.n_sequences;

    // insert new requests as soon as the previous one is done
    const bool cont_batching = params.cont_batching;

    const bool dump_kv_cache = params.dump_kv_cache;

    // init llama.cpp
    llama_backend_init();
    llama_numa_init(params.numa);

    // load the target model
    common_init_result llama_init = common_init_from_params(params);

    llama_model * model = llama_init.model.get();
    llama_context * ctx = llama_init.context.get();

    const llama_vocab * vocab = llama_model_get_vocab(model);

    // load the prompts from file - required
    if (params.prompt.empty()) {
        LOG_ERR("\033[31mError: No prompt file provided. A file with prompts is required.\033[0m\n");
        LOG_ERR("Please provide a file with prompts using the -f/--file option.\n");
        return 1;
    }
    
    // Load prompts from the file
    LOG_INF("\033[32mLoading prompts from file: %s\033[0m\n\n", params.prompt_file.c_str());

    std::vector<std::string> prompts = split_string(params.prompt, '\n');
    int index = 0;
    for (const auto& prompt : prompts) {
        if (!prompt.empty()) {
            k_prompts.resize(index + 1);
            k_prompts[index] = prompt;
            index++;
            LOG_INF("%3d prompt: %s\n", index, prompt.c_str());
        }
    }
    
    // Check if we have any valid prompts
    if (k_prompts.empty()) {
        LOG_ERR("\033[31mError: No valid prompts found in the file.\033[0m\n");
        return 1;
    }
    
    // Adjust number of sequences to match number of prompts
    // We want to process each prompt exactly once
    int32_t n_seq = k_prompts.size();
    if (n_seq_param < n_seq) {
        // If user specified fewer sequences than prompts, respect their choice
        n_seq = n_seq_param;
    }
    
    LOG_INF("\n\nProcessing %d prompts sequentially (not randomly) with %d parallel clients\n\n", n_seq, params.n_parallel);

    LOG_INF("\n\n");

    const int n_ctx = llama_n_ctx(ctx);

    std::vector<client> clients(n_clients);
    for (size_t i = 0; i < clients.size(); ++i) {
        auto & client = clients[i];
        client.id = i;
        client.smpl = common_sampler_init(model, params.sampling);
    }

    std::vector<llama_token> tokens_system;
    tokens_system = common_tokenize(ctx, k_system, true);
    const int32_t n_tokens_system = tokens_system.size();

    llama_seq_id g_seq_id = 0;

    // the max batch size is as large as the context to handle cases where we get very long input prompt from multiple
    // users. regardless of the size, the main loop will chunk the batch into a maximum of params.n_batch tokens at a time
    llama_batch batch = llama_batch_init(n_ctx, 0, 1);

    int32_t n_total_prompt = 0;
    int32_t n_total_gen    = 0;
    int32_t n_cache_miss   = 0;

    struct llama_kv_cache_view kvc_view = llama_kv_cache_view_init(ctx, n_clients);

    const auto t_main_start = ggml_time_us();

    LOG_INF("%s: Simulating parallel requests from clients:\n", __func__);
    LOG_INF("%s: n_parallel = %d, n_sequences = %d, cont_batching = %d, system tokens = %d\n", __func__, n_clients, n_seq, cont_batching, n_tokens_system);
    LOG_INF("\n");

    {
        LOG_INF("%s: Evaluating the system prompt ...\n", __func__);

        for (int32_t i = 0; i < n_tokens_system; ++i) {
            common_batch_add(batch, tokens_system[i], i, { 0 }, false);
        }

        if (llama_decode(ctx, batch) != 0) {
            LOG_ERR("%s: llama_decode() failed\n", __func__);
            return 1;
        }

        // assign the system KV cache to all parallel sequences
        for (int32_t i = 1; i <= n_clients; ++i) {
            llama_kv_cache_seq_cp(ctx, 0, i, -1, -1);
        }

        LOG_INF("\n");
    }

    LOG_INF("Processing requests ...\n\n");

    while (true) {
        if (dump_kv_cache) {
            llama_kv_cache_view_update(ctx, &kvc_view);
            common_kv_cache_dump_view_seqs(kvc_view, 40);
        }

        common_batch_clear(batch);

        // decode any currently ongoing sequences
        for (auto & client : clients) {
            if (client.seq_id == -1) {
                continue;
            }

            client.i_batch = batch.n_tokens;

            common_batch_add(batch, client.sampled, n_tokens_system + client.n_prompt + client.n_decoded, { client.id + 1 }, true);

            client.n_decoded += 1;
        }

        if (batch.n_tokens == 0) {
            // all sequences have ended - clear the entire KV cache
            for (int i = 1; i <= n_clients; ++i) {
                llama_kv_cache_seq_rm(ctx, i, -1, -1);
                // but keep the system prompt
                llama_kv_cache_seq_cp(ctx, 0, i, -1, -1);
            }

            LOG_INF("%s: clearing the KV cache\n", __func__);
        }

        // insert new sequences for decoding
        if (cont_batching || batch.n_tokens == 0) {
            for (auto & client : clients) {
                if (client.seq_id == -1 && g_seq_id < n_seq) {
                    client.seq_id = g_seq_id;

                    client.t_start_prompt = ggml_time_us();
                    client.t_start_gen    = 0;

                    // Get the next prompt in sequence instead of random
                    const size_t prompt_idx = g_seq_id % k_prompts.size();
                    client.input    = k_prompts[prompt_idx];
                    client.prompt   = client.input + "\nAssistant:";
                    client.response = "";

                    common_sampler_reset(client.smpl);

                    // do not prepend BOS because we have a system prompt!
                    std::vector<llama_token> tokens_prompt;
                    tokens_prompt = common_tokenize(ctx, client.prompt, false);

                    for (size_t i = 0; i < tokens_prompt.size(); ++i) {
                        common_batch_add(batch, tokens_prompt[i], i + n_tokens_system, { client.id + 1 }, false);
                    }

                    // extract the logits only for the last token
                    if (batch.n_tokens > 0) {
                        batch.logits[batch.n_tokens - 1] = true;
                    }

                    client.n_prompt  = tokens_prompt.size();
                    client.n_decoded = 0;
                    client.i_batch   = batch.n_tokens - 1;

                    LOG_INF("\033[31mClient %3d, seq %4d, started decoding ...\033[0m\n", client.id, client.seq_id);

                    g_seq_id += 1;

                    // insert new requests one-by-one
                    //if (cont_batching) {
                    //    break;
                    //}
                }
            }
        }

        if (batch.n_tokens == 0) {
            break;
        }

        // process in chunks of params.n_batch
        int32_t n_batch = params.n_batch;

        for (int32_t i = 0; i < (int32_t) batch.n_tokens; i += n_batch) {
            // experiment: process in powers of 2
            //if (i + n_batch > (int32_t) batch.n_tokens && n_batch > 32) {
            //    n_batch /= 2;
            //    i -= n_batch;
            //    continue;
            //}

            const int32_t n_tokens = std::min(n_batch, (int32_t) (batch.n_tokens - i));

            llama_batch batch_view = {
                n_tokens,
                batch.token    + i,
                nullptr,
                batch.pos      + i,
                batch.n_seq_id + i,
                batch.seq_id   + i,
                batch.logits   + i,
            };

            const int ret = llama_decode(ctx, batch_view);
            if (ret != 0) {
                if (n_batch == 1 || ret < 0) {
                    // if you get here, it means the KV cache is full - try increasing it via the context size
                    LOG_ERR("%s : failed to decode the batch, n_batch = %d, ret = %d\n", __func__, n_batch, ret);
                    return 1;
                }

                LOG_ERR("%s : failed to decode the batch, retrying with n_batch = %d\n", __func__, n_batch / 2);

                n_cache_miss += 1;

                // retry with half the batch size to try to find a free slot in the KV cache
                n_batch /= 2;
                i -= n_batch;

                continue;
            }

            LOG_DBG("%s : decoded batch of %d tokens\n", __func__, n_tokens);

            for (auto & client : clients) {
                if (client.i_batch < (int) i || client.i_batch >= (int) (i + n_tokens)) {
                    continue;
                }

                //printf("client %d, seq %d, token %d, pos %d, batch %d\n",
                //        client.id, client.seq_id, client.sampled, client.n_decoded, client.i_batch);

                const llama_token id = common_sampler_sample(client.smpl, ctx, client.i_batch - i);

                common_sampler_accept(client.smpl, id, true);

                if (client.n_decoded == 1) {
                    // start measuring generation time after the first token to make sure all concurrent clients
                    // have their prompt already processed
                    client.t_start_gen = ggml_time_us();
                }

                const std::string token_str = common_token_to_piece(ctx, id);

                client.response += token_str;
                client.sampled = id;

                //printf("client %d, seq %d, token %d, pos %d, batch %d: %s\n",
                //        client.id, client.seq_id, id, client.n_decoded, client.i_batch, token_str.c_str());

                if (client.n_decoded > 2 &&
                        (llama_vocab_is_eog(vocab, id) ||
                         (params.n_predict > 0 && client.n_decoded + client.n_prompt >= params.n_predict) ||
                         client.response.find("User:") != std::string::npos ||
                         client.response.find('\n') != std::string::npos)) {
                    // basic reverse prompt
                    const size_t pos = client.response.find("User:");
                    if (pos != std::string::npos) {
                        client.response = client.response.substr(0, pos);
                    }

                    // delete only the generated part of the sequence, i.e. keep the system prompt in the cache
                    llama_kv_cache_seq_rm(ctx,    client.id + 1, -1, -1);
                    llama_kv_cache_seq_cp(ctx, 0, client.id + 1, -1, -1);

                    const auto t_main_end = ggml_time_us();

                    LOG_INF("\033[31mClient %3d, seq %3d/%3d, prompt %4d t, response %4d t, time %5.2f s, speed %5.2f t/s, cache miss %d \033[0m \n\nInput:    %s\n\033[35mResponse: %s\033[0m\n\n",
                            client.id, client.seq_id, n_seq, client.n_prompt, client.n_decoded,
                            (t_main_end - client.t_start_prompt) / 1e6,
                            (double) (client.n_prompt + client.n_decoded) / (t_main_end - client.t_start_prompt) * 1e6,
                            n_cache_miss,
                            ::trim(client.input).c_str(),
                            ::trim(client.response).c_str());

                    // Store the result
                    prompt_response result;
                    result.prompt = ::trim(client.input);
                    result.response = ::trim(client.response);
                    result.processing_time_us = t_main_end - client.t_start_prompt;
                    result.prompt_tokens = client.n_prompt;
                    result.response_tokens = client.n_decoded;
                    results.push_back(result);

                    n_total_prompt += client.n_prompt;
                    n_total_gen    += client.n_decoded;

                    client.seq_id = -1;
                }

                client.i_batch = -1;
            }
        }
    }

    const auto t_main_end = ggml_time_us();

    print_date_time();

    LOG_INF("%s: n_parallel = %d, n_sequences = %d, cont_batching = %d, system tokens = %d\n", __func__, n_clients, n_seq, cont_batching, n_tokens_system);
    if (params.prompt_file.empty()) {
        params.prompt_file = "used built-in defaults";
    }
    LOG_INF("External prompt file: \033[32m%s\033[0m\n", params.prompt_file.c_str());
    LOG_INF("Model and path used:  \033[32m%s\033[0m\n\n", params.model.c_str());

    LOG_INF("Total prompt tokens: %6d, speed: %5.2f t/s\n", n_total_prompt, (double) (n_total_prompt              ) / (t_main_end - t_main_start) * 1e6);
    LOG_INF("Total gen tokens:    %6d, speed: %5.2f t/s\n", n_total_gen,    (double) (n_total_gen                 ) / (t_main_end - t_main_start) * 1e6);
    LOG_INF("Total speed (AVG):   %6s  speed: %5.2f t/s\n", "",             (double) (n_total_prompt + n_total_gen) / (t_main_end - t_main_start) * 1e6);
    LOG_INF("Cache misses:        %6d\n", n_cache_miss);

    LOG_INF("\n");

    // TODO: print sampling/grammar timings for all clients
    llama_perf_context_print(ctx);

    llama_batch_free(batch);

    llama_backend_free();

    // Save results to file if output file path was provided
    if (!output_file_path.empty()) {
        std::ofstream outfile(output_file_path);
        if (outfile.is_open()) {
            LOG_INF("Saving results to file: %s\n", output_file_path.c_str());
            
            outfile << "# Results from llama.cpp parallel processing\n";
            outfile << "# Total prompts: " << results.size() << "\n";
            outfile << "# Date: " << std::time(nullptr) << "\n\n";
            
            for (size_t i = 0; i < results.size(); ++i) {
                const auto& result = results[i];
                outfile << "### Prompt " << (i + 1) << ":\n";
                outfile << result.prompt << "\n\n";
                outfile << "### Response " << (i + 1) << ":\n";
                outfile << result.response << "\n\n";
                outfile << "### Stats " << (i + 1) << ":\n";
                outfile << "Processing time: " << (result.processing_time_us / 1e6) << " seconds\n";
                outfile << "Prompt tokens: " << result.prompt_tokens << "\n";
                outfile << "Response tokens: " << result.response_tokens << "\n";
                outfile << "Total tokens: " << (result.prompt_tokens + result.response_tokens) << "\n";
                outfile << "Token generation speed: " << ((result.prompt_tokens + result.response_tokens) / (result.processing_time_us / 1e6)) << " tokens/second\n";
                outfile << "\n---\n\n";
            }
            
            outfile.close();
            LOG_INF("Results saved successfully\n");
        } else {
            LOG_ERR("Failed to open output file: %s\n", output_file_path.c_str());
        }
    }

    LOG("\n\n");

    return 0;
}
