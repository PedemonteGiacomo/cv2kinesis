// main.c - Algoritmo grayscale con OpenMP per MIP
#define _POSIX_C_SOURCE 200809L

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <omp.h>
#include "parallel_to_grayscale.h"

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Uso: %s <input_img> <output_img.png> [passaggi_kernel]\n", argv[0]);
        return 1;
    }

    printf("[grayscale] Starting processing...\n");
    printf("[grayscale] Input: %s\n", argv[1]);
    printf("[grayscale] Output: %s\n", argv[2]);
    printf("[grayscale] OpenMP threads: %d\n", omp_get_max_threads());

    int width, height, channels;
    unsigned char *img = stbi_load(argv[1], &width, &height, &channels, 0);
    if (!img) {
        fprintf(stderr, "[grayscale] Errore caricando immagine: %s\n", argv[1]);
        return 1;
    }

    printf("[grayscale] Image loaded: %dx%d, channels: %d\n", width, height, channels);

    int passes = (argc >= 4) ? atoi(argv[3]) : 1;
    if (passes < 1) passes = 1;

    printf("[grayscale] Kernel passes: %d\n", passes);

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    for (int p = 0; p < passes; ++p) {
        convert_to_grayscale(img, width, height, channels);
    }

    clock_gettime(CLOCK_MONOTONIC, &t1);
    double secs = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
    printf("[grayscale] Compute kernel ×%d: %.4f s\n", passes, secs);

    if (!stbi_write_png(argv[2], width, height, channels, img, width * channels)) {
        fprintf(stderr, "[grayscale] Errore nel salvataggio: %s\n", argv[2]);
        stbi_image_free(img);
        return 1;
    }

    printf("[grayscale] Processing completed successfully\n");
    stbi_image_free(img);
    return 0;
}
