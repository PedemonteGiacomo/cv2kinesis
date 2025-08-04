// parallel_to_grayscale.c - Implementazione OpenMP per conversione grayscale
#include <omp.h>
#include <stdio.h>
#include "parallel_to_grayscale.h"

void convert_to_grayscale(unsigned char *data, int width, int height, int channels) {
    int numPixels = width * height;
    
    printf("[grayscale] Converting %d pixels using %d threads\n", numPixels, omp_get_max_threads());
    
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < numPixels; i++) {
        int idx = i * channels;
        
        // Leggi valori RGB
        unsigned char r = data[idx];
        unsigned char g = data[idx + 1];
        unsigned char b = data[idx + 2];
        
        // Formula standard per luminanza (ITU-R BT.601)
        unsigned char lum = (unsigned char)(0.299f * r + 0.587f * g + 0.114f * b);
        
        // Applica luminanza a tutti i canali RGB
        data[idx] = lum;     // R
        data[idx + 1] = lum; // G  
        data[idx + 2] = lum; // B
        
        // Se c'è canale alpha (channels==4), rimane invariato
        // data[idx + 3] non viene modificato
    }
    
    printf("[grayscale] Grayscale conversion completed\n");
}
