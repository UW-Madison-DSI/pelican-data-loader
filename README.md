# pelican-data-loader

Pelican-backed data loader prototype: [demo](https://datasets.services.dsi.wisc.edu/)

## Quickstart

1. Install `pelican-data-loader` and `pytorch` from pypi

    ```sh
    pip install pelican-data-loader torch
    ```

1. Consume data with [`datasets`](https://huggingface.co/docs/datasets/en/index)

    ```python
    from datasets import load_dataset
    dataset = load_dataset("csv", data_files="pelican://uwdf-director.chtc.wisc.edu/wisc.edu/dsi/pytorch/bird_migration_data.csv")
    torch_dataset = dataset.with_format("torch")
    ```

For more detailed example, see this [notebook](https://colab.research.google.com/drive/1vQKS5p-Ykc5hLnFSV4sZjiiuc_z8OkuF?usp=sharing)

## Features

- Uses `Croissant` to store / validate metadata
- Uses `pelicanfs` to locate/cache dataset
- Uses `datasets` to convert to different ML data format (e.g., pytorch, tensorflow, jax, polars, pyarrow...)
- Provided dataset storage via UW-Madison's S3

### Future features (Pending)

- `doi` minting via [DataCite](https://datacite.org/)
- better frontend for dataset discover and publishing
- backup
- data prefetching? (at pelican layer?)
- private datasets
- telemetry?

## Backend

- [WISC-S3](s3://web.s3.wisc.edu/pelican-data-loader), storing
  - Actual datasets
  - Croissant JSONLD
- [Postgres](postgres://services.dsi.wisc.edu:8787), storing
  - Various metadata
  - Links to pelican data source
  - Links to Croissant JSONLD
- [Pelican](pelican://uwdf-director.chtc.wisc.edu/dsi/pytorch)

## Dev notes

- Licenses data: pull from [SPDX](https://spdx.org/licenses/) with `pelican_data_loader.data.pull_license`.
- minimal csv file croissant generator: `pelican_data_loader.utils.parse_col`.
- For copying data to S3, use `rclone`, it is way faster than python client. Also it support rsync-like functions.
