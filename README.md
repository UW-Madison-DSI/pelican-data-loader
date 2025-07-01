# pelican-data-loader

Pelican-backed data loader prototype.

## Components

- [Dev S3 bucket](web.s3.wisc.edu/pelican-data-loader)
- [pelicanfs](https://github.com/PelicanPlatform/pelicanfs): Caching and CN
- [mlcroissant](https://github.com/mlcommons/croissant): Add meta-data to dataset, and possibly
- [DataCite](https://datacite.org/): DOI minting

## Notes to self

- Licenses data: pull from [SPDX](https://spdx.org/licenses/) with `pelican_data_loader.data.pull_license`.
- minimal csv file croissant generator: `pelican_data_loader.utils.parse_col`.
