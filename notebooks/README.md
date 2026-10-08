# Notebooks

Exploration and one-off GPU jobs. Production ingestion lives in the
`vio ingest` CLI (`backend/`). Notebooks are not part of the runtime system.

These were written for Google Colab and read data from Google Drive.

| Notebook | Input | Output | Purpose |
|---|---|---|---|
| `01_preprocessing.ipynb` / `01_preprocessing_meta.ipynb` | `amazon_products_cleaned.csv` | `vectors_in_orbit.csv` | Clean data, handle missing values, assign product IDs |
| `02_eda.ipynb` / `02_eda_extended.ipynb` | `vectors_in_orbit.csv` | `vio_EDA.csv` | EDA; Bayesian rating per category; value score; price buckets |
| `03_embedding.ipynb` / `04_qdrant_points.ipynb` | `vio_EDA.csv` + images | Qdrant `vio_products` (v1 schema) | Legacy CLIP text+image embedding and upload |

Legacy v1 collection schema: named vectors `text` and `image` (CLIP ViT-B/32,
512-d, cosine). Point IDs are `uuid5(NAMESPACE_URL, "vio:{product_id}")`.
The v2 schema is defined in [PLAN.md §7.3](../PLAN.md).

`requirements.txt` lists the packages these notebooks need when run locally.
