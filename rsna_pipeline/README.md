# RSNA Pneumonia Processing Pipeline

This folder contains a small, self-contained set of tools to experiment with different segmentation algorithms on chest radiographs from the **RSNA Pneumonia Detection Challenge**.  The code uses only the Python standard library and the SciPy stack.

Three processing pipelines are currently available:

| ALGO_ID       | Description                                              |
|---------------|----------------------------------------------------------|
| `processing_1` | Medium-inspired: Gaussian smoothing + threshold + CCL   |
| `processing_2` | Windowing + CLAHE + Canny + morphology                  |
| `processing_3` | Otsu thresholding with border and small-object cleanup  |

The command line interface lets you run any algorithm on a single file or on a folder of DICOM images.

```bash
# single DICOM
python main.py --dicom data/ID_0000.dcm --algo processing_1

# batch mode on a folder
python main.py --folder data/rsna_train --algo processing_3 --out results
```

Each run saves an overlay image (`*_overlay.png`) and a JSON file with processing metadata under the output directory.

## Extending the pipeline

To add a new algorithm:

1. Create `processing/my_algo.py` implementing a `Processor` subclass.
2. Set `ALGO_ID = "processing_N"` and implement the `run` method.
3. Import the new class inside `processing/__init__.py` so it registers with `Processor.factory`.
4. Specify the new ID on the command line or in queue messages.

## Running inside Docker

A minimal image is provided under `docker/`.

```bash
docker build -t rsna_proc -f docker/Dockerfile .
docker run --rm -v $(pwd)/data:/data -v $(pwd)/results:/app/output \
           rsna_proc --folder /data --algo processing_2 --out /app/output
```

This builds the container with the required dependencies and executes the chosen algorithm on all DICOM files under `/data`.