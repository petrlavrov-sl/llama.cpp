#ifndef LLAMA_RNG_PROVIDER_H
#define LLAMA_RNG_PROVIDER_H

#include <random>
#include <string>
#include <fstream>

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

// Factory function to create RNG providers
inline RNGProvider* create_rng_provider(const std::string& type, uint32_t seed) {
    if (type == "normal") {
        return new NormalRNGProvider(seed);
    }
    // Default to uniform
    return new UniformRNGProvider(seed);
}

#endif // LLAMA_RNG_PROVIDER_H 