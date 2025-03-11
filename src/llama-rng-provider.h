#ifndef LLAMA_RNG_PROVIDER_H
#define LLAMA_RNG_PROVIDER_H

#include <random>
#include <string>
#include <fstream>
#include <curl/curl.h>
#include <nlohmann/json.hpp>

// Simple RNG Provider base class
class RNGProvider {
public:
    RNGProvider(const std::string& name) : name(name) {}
    virtual ~RNGProvider() {
        if (output_file.is_open()) {
            output_file.close();
        }
    }
    
    // Generate a random number between 0 and 1
    virtual double generate() = 0;
    
    // Set output file for logging random numbers
    void set_output_file(const std::string& filename) {
        if (output_file.is_open()) {
            output_file.close();
        }
        
        if (!filename.empty()) {
            output_file.open(filename);
            if (output_file.is_open()) {
                output_file << "# RNG values from " << name << " provider\n";
                output_file.flush();
            }
        }
    }
    
    // Get the name of the provider
    const std::string& get_name() const {
        return name;
    }

protected:
    // Log the generated value to file if enabled
    void log_value(double value) {
        if (output_file.is_open()) {
            output_file << value << "\n";
            output_file.flush();
        }
    }

private:
    std::string name;
    std::ofstream output_file;
};

// Uniform distribution RNG provider
class UniformRNGProvider : public RNGProvider {
public:
    UniformRNGProvider(uint32_t seed) 
        : RNGProvider("uniform"), rng(seed) {}
    
    double generate() override {
        double value = std::uniform_real_distribution<>(0.0, 1.0)(rng);
        log_value(value);
        return value;
    }
    
private:
    std::mt19937 rng;
};

// Normal distribution RNG provider
class NormalRNGProvider : public RNGProvider {
public:
    NormalRNGProvider(uint32_t seed) 
        : RNGProvider("normal"), rng(seed) {}
    
    double generate() override {
        // Generate normal distribution with mean 0.5 and std dev 0.15
        double raw_value = std::normal_distribution<>(0.5, 0.15)(rng);
        // Clamp to 0-1 range
        double value = std::max(0.0, std::min(1.0, raw_value));
        log_value(value);
        return value;
    }
    
private:
    std::mt19937 rng;
};

// External API-based RNG provider
class ExternalAPIRNGProvider : public RNGProvider {
public:
    ExternalAPIRNGProvider(const std::string& api_url) 
        : RNGProvider("external-api"), api_url(api_url) {
        // Initialize curl
        curl_global_init(CURL_GLOBAL_DEFAULT);
        curl = curl_easy_init();
        if (!curl) {
            fprintf(stderr, "Failed to initialize curl\n");
        }
    }
    
    ~ExternalAPIRNGProvider() override {
        if (curl) {
            curl_easy_cleanup(curl);
        }
        curl_global_cleanup();
    }
    
    double generate() override {
        if (!curl) {
            fprintf(stderr, "Curl not initialized, returning default value\n");
            return 0.5; // Default value if curl failed
        }
        
        // Make request to the API
        std::string response_data;
        curl_easy_setopt(curl, CURLOPT_URL, api_url.c_str());
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response_data);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L); // 5 second timeout
        
        CURLcode res = curl_easy_perform(curl);
        if (res != CURLE_OK) {
            throw std::runtime_error(std::string("curl_easy_perform() failed: ") + curl_easy_strerror(res));
        }
        // Parse JSON response
        try {
            nlohmann::json j = nlohmann::json::parse(response_data);
            if (j.contains("random") && j["random"].is_number()) {
                double value = j["random"];
                // Ensure value is in the range [0, 1]
                value = std::max(0.0, std::min(1.0, value));
                log_value(value);
                return value;
            }
            throw std::runtime_error("API response missing 'random' field: " + response_data);
        } catch (std::exception& e) {
            throw std::runtime_error(std::string("RNG API error: ") + e.what());
        }
    }
    
private:
    std::string api_url;
    CURL* curl;
    
    // Static callback function for curl
    static size_t write_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
        std::string* response = reinterpret_cast<std::string*>(userdata);
        response->append(ptr, size * nmemb);
        return size * nmemb;
    }
};

// Factory function to create RNG providers
inline RNGProvider* create_rng_provider(const std::string& type, uint32_t seed) {
    if (type == "normal") {
        return new NormalRNGProvider(seed);
    } else if (type == "external-api") {
        // Check for API URL environment variable
        const char* api_url = std::getenv("LLAMA_RNG_API_URL");
        if (api_url == nullptr) {
            fprintf(stderr, "Error: LLAMA_RNG_API_URL environment variable not set for external-api provider\n");
            return new UniformRNGProvider(seed); // Fallback to uniform
        }
        return new ExternalAPIRNGProvider(api_url);
    }
    // Default to uniform
    return new UniformRNGProvider(seed);
}

#endif // LLAMA_RNG_PROVIDER_H 