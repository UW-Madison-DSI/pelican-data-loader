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

## Components

- [Dev S3 bucket](web.s3.wisc.edu/pelican-data-loader)
- [pelicanfs](https://github.com/PelicanPlatform/pelicanfs): Caching and CN
- [mlcroissant](https://github.com/mlcommons/croissant): Add meta-data to dataset, and possibly
- [DataCite](https://datacite.org/): DOI minting

## Notes to self

- Licenses data: pull from [SPDX](https://spdx.org/licenses/) with `pelican_data_loader.data.pull_license`.
- minimal csv file croissant generator: `pelican_data_loader.utils.parse_col`.
