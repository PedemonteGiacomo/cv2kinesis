/*
 * Esempio di algoritmo OpenMP semplice
 * Simula un'operazione di elaborazione immagine
 */
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <omp.h>
#include <cstring>

void print_usage(const char* prog) {
    std::cout << "Usage: " << prog << " -i <input_file> -o <output_file> [-t <threads>]" << std::endl;
}

int main(int argc, char* argv[]) {
    std::string input_file, output_file;
    int num_threads = 2;
    
    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-i") == 0 && i + 1 < argc) {
            input_file = argv[++i];
        } else if (strcmp(argv[i], "-o") == 0 && i + 1 < argc) {
            output_file = argv[++i];
        } else if (strcmp(argv[i], "-t") == 0 && i + 1 < argc) {
            num_threads = std::atoi(argv[++i]);
        }
    }
    
    if (input_file.empty() || output_file.empty()) {
        print_usage(argv[0]);
        return 1;
    }
    
    std::cout << "Processing " << input_file << " -> " << output_file << std::endl;
    std::cout << "Using " << num_threads << " OpenMP threads" << std::endl;
    
    // Set OpenMP threads
    omp_set_num_threads(num_threads);
    
    // Leggi il file di input
    std::ifstream input(input_file, std::ios::binary);
    if (!input) {
        std::cerr << "Error: Cannot open input file: " << input_file << std::endl;
        return 1;
    }
    
    // Leggi tutto il contenuto
    input.seekg(0, std::ios::end);
    size_t size = input.tellg();
    input.seekg(0, std::ios::beg);
    
    std::vector<char> buffer(size);
    input.read(buffer.data(), size);
    input.close();
    
    std::cout << "Input file size: " << size << " bytes" << std::endl;
    
    // Simula elaborazione parallela (esempio: modifica alcuni bytes)
    #pragma omp parallel for
    for (size_t i = 0; i < size; i++) {
        // Operazione fittizia: incrementa ogni byte di 1 (con overflow)
        buffer[i] = static_cast<char>((static_cast<unsigned char>(buffer[i]) + 1) % 256);
    }
    
    // Scrivi il risultato
    std::ofstream output(output_file, std::ios::binary);
    if (!output) {
        std::cerr << "Error: Cannot create output file: " << output_file << std::endl;
        return 1;
    }
    
    output.write(buffer.data(), size);
    output.close();
    
    std::cout << "Processing completed successfully!" << std::endl;
    
    return 0;
}
