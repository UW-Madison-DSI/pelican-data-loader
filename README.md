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
    dataset = load_dataset("csv", data_files="pelican://uwdf-director.chtc.wisc.edu/dsi/pytorch/bird_migration_data.csv")
    torch_dataset = dataset.with_format("torch")
    ```

For more detailed example, see this [notebook](https://colab.research.google.com/drive/1vQKS5p-Ykc5hLnFSV4sZjiiuc_z8OkuF?usp=sharing)

## Features

- Uses `Croissant` to store / validate metadata
- Uses `pelicanfs` to locate/cache dataset
- Uses `datasets` to convert to different ML data format (e.g., pytorch, tensorflow, jax, polars, pyarrow...)
- Provided dataset storage via UW–Madison's S3

### Future features (Pending)

- `doi` minting via [DataCite](https://datacite.org/)
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

## Demo app

The demo at [datasets.services.dsi.wisc.edu](https://datasets.services.dsi.wisc.edu/) lives in
`app/`. It is FastAPI + Jinja2 + [htmx](https://htmx.org/), styled with
[Tailwind CSS 4](https://tailwindcss.com/) and [daisyUI 5](https://daisyui.com/) and
built with [Bun](https://bun.com/).

- **Discover** — card grid with live search, license/keyword facets, and a detail
  page per dataset with copy-able load snippets.
- **Publish** — four steps: describe, upload the CSV to S3, generate and validate
  Croissant metadata, record the dataset.

The look follows the official [UW–Madison Design System](https://brand.wisc.edu/): the
red global bar and charcoal footer are the university's standard page chrome, the
palette is the exact brand hex (Badger Red `#c5050c`), and Red Hat Display/Text are
self-hosted from `app/static/fonts/` rather than the wisc.edu CDN so the container has
no external asset dependency. The theme is light only — the design system reserves red
for light backgrounds, since Badger Red on charcoal fails contrast.

### Running it locally

Needs [Bun](https://bun.com/docs/installation) for the front-end build.

```sh
uv sync --group demo              # the web app's dependencies
bun install && bun run build      # builds app/static/css/app.css and vendors htmx
uv run uvicorn app.main:app --reload --port 8000
```

Then open <http://localhost:8000>. Run `bun run watch:css` alongside if you are
editing templates — Tailwind only emits classes it can see in the template source.

Without Postgres, point the app at SQLite and initialize it once:

```sh
export APP_DATABASE_URL=sqlite:///./dev.db
uv run python -c "from pelican_data_loader import initialize_database; initialize_database('sqlite:///./dev.db')"
APP_FAKE_S3=1 uv run uvicorn app.main:app --reload --port 8000
```

`APP_FAKE_S3=1` skips every S3 call, so the publish flow and its progress bar work
with no credentials.

Every command above is also a VS Code task (`Ctrl+Shift+P` → *Run Task*). Run
**demo: install** once after cloning, then **demo: dev** — the default build task,
which starts the SQLite server and the CSS watcher together.

`uv run python app/smoke_test.py` renders every route and compiles every template;
it needs neither a database nor credentials, and the Docker build runs it so a
broken app fails the build rather than the deployment.

### App settings

All `APP_`-prefixed, read from `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_SECRET_KEY` | random | Signs the session cookie. Unset means every restart drops in-progress publish drafts. |
| `APP_DATABASE_URL` | from `POSTGRES_*` | Overrides the metadata database, e.g. `sqlite:///./dev.db`. |
| `APP_FAKE_S3` | `false` | Skip S3 uploads and deletes. |
| `APP_DRAFT_DIR` | `./var/drafts` | Where in-progress publish drafts are stored. |
| `APP_DRAFT_TTL_SECONDS` | `86400` | How long an abandoned draft survives. |
| `APP_MAX_UPLOAD_MB` | `512` | Upload size limit. |
| `APP_PAGE_SIZE` | `12` | Datasets per page. |
| `APP_HTTPS_ONLY` | `false` | Set behind TLS so the session cookie gets `Secure`. |

## Dev notes

- Licenses data: pull from [SPDX](https://spdx.org/licenses/) with `scripts/pull_licenses.py`.
- Croissant generation for a CSV: `pelican_data_loader.build_croissant_metadata`; per-column
  field mapping is `pelican_data_loader.utils.parse_col`.
- `@parcel/watcher` is listed in `trustedDependencies`. Bun blocks lifecycle scripts by default,
  and without its postinstall `bun run watch:css` exits after the first build instead of watching.
- For copying data to S3, use `rclone`, it is way faster than python client. Also it support rsync-like functions.
- `METADATA_DB_ENGINE_URL` in `.env` is **ignored**: `SystemConfig.metadata_db_engine_url` is a
  computed property built from `POSTGRES_*`, and `extra="allow"` silently swallows the unused key.
  Use `APP_DATABASE_URL` to point the demo somewhere else.
