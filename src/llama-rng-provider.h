#ifndef LLAMA_RNG_PROVIDER_H
#define LLAMA_RNG_PROVIDER_H

#include <random>
#include <string>
#include <fstream>
#include <vector>
#include <thread>
#include <chrono>
#include <stdexcept>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <iomanip> // Required for std::fixed and std::setprecision

// Platform-specific serial includes
#ifdef _WIN32
    #include <windows.h>
#else
    #include <fcntl.h>
    #include <termios.h>
    #include <unistd.h>
    #include <glob.h> // For auto-detection
#endif
#if defined(__APPLE__) && defined(__MACH__)
    #include <sys/ioctl.h>
    #include <IOKit/serial/ioss.h>
#endif

// Simple RNG Provider base class
class RNGProvider {
public:
    RNGProvider(const std::string& name) : name(name) {
        // Check if debug output is enabled
        const char* debug_env = std::getenv("LLAMA_RNG_DEBUG");
        debug_enabled = (debug_env != nullptr && std::string(debug_env) == "1");
    }
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

        if (!filename.empty() && debug_enabled) {
            output_file.open(filename);
            if (output_file.is_open()) {
                output_file << "# RNG values from " << name << " provider\n";
                output_file << "# Format: timestamp_ms,random_value\n";
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
            auto now = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::system_clock::now().time_since_epoch()
            ).count();
            output_file << now << "," << std::fixed << std::setprecision(10) << value << "\n";
            output_file.flush();
        }
    }

private:
    std::string name;
    std::ofstream output_file;
    bool debug_enabled = false;
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
            throw std::runtime_error("Curl not initialized - cannot generate random numbers");
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

// Serial FPGA RNG provider - connects directly to FPGA via UART
class SerialFPGARNGProvider : public RNGProvider {
public:
    SerialFPGARNGProvider(std::string port = "", int baudrate = 921600)
        : RNGProvider("fpga-serial"), port_name(port), baudrate(baudrate) {
#ifdef _WIN32
        serial_handle = INVALID_HANDLE_VALUE;
#else
        serial_fd = -1;
#endif
        if (port_name.empty()) {
            port_name = auto_detect_port();
        }

        if (port_name.empty() || !open_serial_port()) {
            throw std::runtime_error("Failed to open or configure serial port: " + port_name);
        }
    }

    ~SerialFPGARNGProvider() override {
        if (is_open()) {
            close_serial_port();
        }
    }

    double generate() override {
        // Read 4 bytes to form a 32-bit integer for higher precision
        uint32_t random_int = read_u32();
        // Normalize to [0, 1] using the full range of uint32_t
        double value = random_int / (double)0xFFFFFFFF;
        log_value(value);
        return value;
    }

private:
    std::string port_name;
    int baudrate;
#ifdef _WIN32
    HANDLE serial_handle;
#else
    int serial_fd;
#endif

    bool is_open() const {
#ifdef _WIN32
        return serial_handle != INVALID_HANDLE_VALUE;
#else
        return serial_fd >= 0;
#endif
    }

    void close_serial_port() {
#ifdef _WIN32
        if (is_open()) {
            CloseHandle(serial_handle);
            serial_handle = INVALID_HANDLE_VALUE;
        }
#else
        if (is_open()) {
            close(serial_fd);
            serial_fd = -1;
        }
#endif
    }

    // Simplified C++ auto-detection. Using the Python script is more reliable.
    std::string auto_detect_port() {
#ifndef _WIN32
        const std::vector<std::string> patterns = {
            "/dev/cu.usbserial*", "/dev/tty.usbserial*", "/dev/ttyUSB*", "/dev/cu.usbmodem*"
        };
        glob_t glob_result;
        for (const auto& pattern : patterns) {
            memset(&glob_result, 0, sizeof(glob_result));
            if (glob(pattern.c_str(), GLOB_TILDE, NULL, &glob_result) == 0) {
                if (glob_result.gl_pathc > 0) {
                    std::string detected_port = glob_result.gl_pathv[0];
                    globfree(&glob_result);
                    // This is a basic detection; it doesn't verify the device.
                    return detected_port;
                }
            }
            globfree(&glob_result);
        }
#else
        // Windows auto-detection is complex; recommend setting env var.
#endif
        return ""; // Not found
    }

    bool open_serial_port() {
#ifdef _WIN32
        std::string full_port = "\\\\.\\" + port_name;
        serial_handle = CreateFileA(full_port.c_str(), GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
        if (serial_handle == INVALID_HANDLE_VALUE) return false;

        DCB dcbSerialParams = {0};
        dcbSerialParams.DCBlength = sizeof(dcbSerialParams);
        if (!GetCommState(serial_handle, &dcbSerialParams)) return false;

        dcbSerialParams.BaudRate = baudrate;
        dcbSerialParams.ByteSize = 8;
        dcbSerialParams.StopBits = ONESTOPBIT;
        dcbSerialParams.Parity = NOPARITY;
        if(!SetCommState(serial_handle, &dcbSerialParams)) return false;

        COMMTIMEOUTS timeouts = {0};
        timeouts.ReadIntervalTimeout = 50;
        timeouts.ReadTotalTimeoutConstant = 50;
        timeouts.ReadTotalTimeoutMultiplier = 10;
        timeouts.WriteTotalTimeoutConstant = 50;
        timeouts.WriteTotalTimeoutMultiplier = 10;
        if(!SetCommTimeouts(serial_handle, &timeouts)) return false;

        return true;
#else
        serial_fd = open(port_name.c_str(), O_RDWR | O_NOCTTY);
        if (serial_fd < 0) return false;

        struct termios tty;
        if(tcgetattr(serial_fd, &tty) != 0) return false;

        // Set control flags
        tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8; // 8-bit chars
        tty.c_cflag |= (CLOCAL | CREAD);           // ignore modem controls
        tty.c_cflag &= ~(PARENB | PARODD);         // shut off parity
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CRTSCTS;

        // Set local flags
        tty.c_lflag = 0; // no signaling chars, no echo

        // Set input flags
        tty.c_iflag &= ~(IXON | IXOFF | IXANY); // shut off xon/xoff ctrl
        tty.c_iflag &= ~IGNBRK;                // disable break processing

        // Set output flags
        tty.c_oflag = 0; // no remapping, no delays

        // Set timeouts
        tty.c_cc[VMIN]  = 1; // block until 1 byte is read
        tty.c_cc[VTIME] = 5; // 0.5 seconds read timeout

#if defined(__APPLE__) && defined(__MACH__)
        // For macOS, we must use a special ioctl to set non-standard baud rates.
        // First, set a standard rate.
        cfsetospeed(&tty, B230400);
        cfsetispeed(&tty, B230400);
#else
        // For Linux, we can use the Bxxxx constants directly if defined.
        speed_t baud_rate_flag;
        switch(baudrate) {
            case 9600:   baud_rate_flag = B9600;   break;
            case 115200: baud_rate_flag = B115200; break;
            case 921600: baud_rate_flag = B921600; break;
            default: return false; // Unsupported baud rate
        }
        cfsetospeed(&tty, baud_rate_flag);
        cfsetispeed(&tty, baud_rate_flag);
#endif

        if (tcsetattr(serial_fd, TCSANOW, &tty) != 0) {
            close_serial_port();
            return false;
        }

#if defined(__APPLE__) && defined(__MACH__)
        // Now, set the custom speed for macOS using ioctl.
        speed_t speed = baudrate;
        if (ioctl(serial_fd, IOSSIOSPEED, &speed) == -1) {
            close_serial_port();
            return false;
        }
#endif
        return true;
#endif
    }

    void send_toggle_command() {
        char toggle_char = 't'; // Any char toggles the stream
        write_bytes(&toggle_char, 1);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    void write_bytes(const void* data, size_t length) {
#ifdef _WIN32
        DWORD bytes_written = 0;
        if (is_open()) WriteFile(serial_handle, data, length, &bytes_written, NULL);
#else
        if (is_open()) write(serial_fd, data, length);
#endif
    }

    uint8_t read_byte() {
        if (!is_open()) {
             throw std::runtime_error("Serial port not open for reading.");
        }
        uint8_t byte;
#ifdef _WIN32
        DWORD bytes_read = 0;
        if (!ReadFile(serial_handle, &byte, 1, &bytes_read, NULL) || bytes_read != 1) {
            throw std::runtime_error("Failed to read from FPGA serial port (Win)");
        }
#else
        ssize_t n = read(serial_fd, &byte, 1);
        if (n != 1) {
            throw std::runtime_error("Failed to read from FPGA serial port (Unix)");
        }
#endif
        return byte;
    }

    uint32_t read_u32() {
        uint8_t bytes[4];
        for (int i = 0; i < 4; ++i) {
            bytes[i] = read_byte();
        }
        // Combine bytes into a 32-bit integer (assuming little-endian from FPGA)
        return ((uint32_t)bytes[3] << 24) |
               ((uint32_t)bytes[2] << 16) |
               ((uint32_t)bytes[1] << 8)  |
               ((uint32_t)bytes[0]);
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
    } else if (type == "fpga-serial") {
        const char* port = std::getenv("LLAMA_FPGA_PORT");
        const char* baud_str = std::getenv("LLAMA_FPGA_BAUDRATE");
        int baudrate = baud_str ? std::atoi(baud_str) : 921600;
        return new SerialFPGARNGProvider(port ? port : "", baudrate);
    }
    // Default to uniform
    return new UniformRNGProvider(seed);
}

#endif // LLAMA_RNG_PROVIDER_H
