# VIO Shop Data Pipeline

Complete data processing pipeline for generating and uploading product embeddings to Qdrant vector database.

## Overview

This pipeline processes ~42K Amazon products through three stages:
1. **Preprocessing**: Clean and prepare raw data
2. **EDA**: Calculate Bayesian ratings and value scores
3. **Embedding**: Generate CLIP embeddings and upload to Qdrant

## Setup

### Prerequisites

- Python 3.8+
- CUDA-capable GPU (recommended for faster embedding generation)
- Qdrant Cloud account or local instance

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

Copy `.env.example` to `.env` and configure:

```env
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your_api_key_here
CSV_PATH=/path/to/vio_EDA.csv
IMG_ROOT=/path/to/images/
CLIP_MODEL=openai/clip-vit-base-patch32
DEVICE=cuda  # or cpu
```

## Jupyter Notebooks

### 01_preprocessing.ipynb
- **Input**: `amazon_products_cleaned.csv`
- **Output**: `vectors_in_orbit.csv`
- **Purpose**: Clean data, handle missing values, assign Product IDs

### 02_eda.ipynb
- **Input**: `vectors_in_orbit.csv`
- **Output**: `vio_EDA.csv`
- **Purpose**: 
  - Exploratory data analysis
  - Calculate Bayesian ratings (weighted by category)
  - Compute value scores (quality/price ratio)

### 03_embedding.ipynb
- **Input**: `vio_EDA.csv` + product images
- **Output**: Qdrant collection `vio_products`
- **Purpose**:
  - Generate text embeddings (title + description + category)
  - Generate image embeddings from product photos
  - Batch upload to Qdrant with retry logic

## Running the Pipeline

### Option 1: Jupyter Notebooks (Recommended for exploration)

```bash
jupyter notebook
# Open notebooks in order: 01 → 02 → 03
```

### Option 2: Python Scripts (Production)

```bash
# Run preprocessing
python scripts/prepare_data.py --input data/raw/amazon_products_cleaned.csv --output data/processed/vectors_in_orbit.csv

# Run EDA and feature calculation
python scripts/calculate_features.py --input data/processed/vectors_in_orbit.csv --output data/processed/vio_EDA.csv

# Generate embeddings and upload to Qdrant
python scripts/embed_and_upload.py --csv data/processed/vio_EDA.csv --images data/images/
```

## Data Files

### Sample Data (Included in repo)
- `data/sample/sample_products.csv` - 500 products for testing

### Full Data (Not in repo - too large)
- `data/raw/amazon_products_cleaned.csv` (37.6 MB) - Raw Amazon data
- `data/processed/vectors_in_orbit.csv` (37.7 MB) - Preprocessed
- `data/processed/vio_EDA.csv` (12.2 MB) - Final dataset
- `data/images/` - 42K+ product images (not committed)

## Qdrant Collection Schema

**Collection Name**: `vio_products`

**Vectors**:
- `text`: 512-dimensional CLIP text embedding
- `image`: 512-dimensional CLIP image embedding (optional)

**Distance Metric**: Cosine similarity

**Payload Fields**:
- `product_id`: Unique product identifier
- `title`: Product name
- `price`: Product price
- `rating`: Average rating (0-5)
- `total_ratings`: Number of ratings
- `category`: Product category
- `subcategory`: Product subcategory
- `bayes_rating`: Bayesian-adjusted rating
- `value_score`: Quality/price score

## Performance

- **Preprocessing**: ~2 minutes
- **EDA**: ~5 minutes
- **Embedding Generation**: ~3-4 hours on GPU, ~12-15 hours on CPU
- **Upload to Qdrant**: ~30 minutes (batched with retries)

## Troubleshooting

**Out of Memory Error**: Reduce batch size in `03_embedding.ipynb`
```python
ROWS_PER_CHUNK = 100  # Default: 500
IMG_BATCH = 8         # Default: 16
```

**Qdrant Upload Fails**: Check API key and URL, verify collection exists

**Missing Images**: Some products may not have images; embeddings will only include text vectors

## References

- [CLIP Model Documentation](https://huggingface.co/openai/clip-vit-base-patch32)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Original Report](docs/report.pdf)
