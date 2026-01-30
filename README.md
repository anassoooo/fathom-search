# VIO Shop - AI-Powered E-Commerce Platform

> **Vectors In Orbit**: An intelligent e-commerce platform using vector embeddings for semantic product search and recommendations.

## 🚀 Project Overview

**VIO Shop** is a next-generation "FinCommerce" discovery engine designed to bridge the gap between vague user intent and strict financial reality. 

Existing e-commerce search is broken: it fails at vague queries ("summer wedding guest") and ignores financial context (budget, value constraint). VIO Shop solves this with an **AI-First capabilities layer**:

- **Context-Aware Assistant**: Detects vague queries and proactively asks for clarification (e.g., "What is your budget?" or "Which product type?").
- **Hybrid Semantic Search**: Combines **Text Embeddings (Ollama)** and **Visual Embeddings (CLIP)** to find "vibes" that keyword search misses.
- **Strict Constraint Filtering**: Respects hard financial constraints (Price < $X) while maintaining fuzzy semantic relevance.
- **Premium Discovery UI**: Features horizontal momentum carousels, glassmorphism aesthetics, and "boutique" curation layouts.

### Key Features

1.  **Smart Clarification Loop**
    *   *Problem*: Users often search vaguley ("I want a laptop").
    *   *Solution*: Our LLM-based intent classifier identifies missing entities (Price, Category) and halts the search to request specific details, ensuring higher-quality results.

2.  **Visual & Text Compatibility**
    *   Uses **CLIP** to project text and images into the same 512-dimensional vector space.
    *   Allows searching for images using text descriptions (e.g., "red floral dress" matches an image of a red floral dress even without text tags).

3.  **Financial Value Scoring**
    *   Calculates `value_score` and `bayes_rating` to surface "Great Value" items, not just cheap ones.

### Tech Stack

**Frontend & Backend**:
- Next.js 16.0 with TypeScript
- Radix UI + Tailwind CSS (Glassmorphism UI)
- Prisma ORM with SQLite (dev) / PostgreSQL (production)
- Vercel AI SDK

**AI & Data Pipeline**:
- **Ollama (Llama 3 / Qwen)**: Intent extraction & entity recognition
- **OpenAI CLIP**: Multimodal embeddings
- **Qdrant**: Vector Similarity Search + Payload Filtering
- Python 3.x with PyTorch & Jupyter Notebooks

## 📂 Repository Structure

```
vio-shop-organized/
├── app/                    # Next.js web application
│   ├── src/               # Application source code
│   ├── public/            # Static assets
│   ├── prisma/            # Database schema
│   └── package.json       # App dependencies
│
├── data-pipeline/         # Product data processing & embeddings
│   ├── notebooks/         # Jupyter notebooks (01-03)
│   ├── scripts/           # Production Python scripts
│   ├── data/              # Data storage (gitignored)
│   │   ├── sample/        # Sample dataset (500 products)
│   │   ├── raw/           # Raw product data
│   │   └── processed/     # Processed datasets
│   └── docs/              # Pipeline documentation
│
├── docs/                  # Project-wide documentation
└── .github/               # CI/CD workflows (optional)
```

## 🛠️ Quick Start

### Prerequisites

- Node.js 18+ and npm/yarn
- Python 3.8+
- Qdrant Cloud account (or local instance)

### 1. Web Application Setup

```bash
cd app
npm install
cp .env.example .env.local
# Edit .env.local with your credentials
npx prisma generate
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000)

### 2. Data Pipeline Setup

```bash
cd data-pipeline
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Qdrant credentials

# Run notebooks in order:
jupyter notebook notebooks/01_preprocessing.ipynb
```

## 🗄️ Database

**Product Collection**: ~42,000 Amazon products with:
- Text embeddings (product title + description + category)
- Image embeddings (product images)
- Metadata (price, ratings, category, etc.)

**Vector Dimensions**: 512 (CLIP embeddings)
**Distance Metric**: Cosine similarity

## 📊 Data Pipeline Workflow

1. **Preprocessing** (`01_preprocessing.ipynb`): Clean raw data, handle missing values
2. **EDA** (`02_eda.ipynb`): Calculate Bayesian ratings and value scores
3. **Embedding** (`03_embedding.ipynb`): Generate CLIP embeddings and upload to Qdrant

## 🔐 Environment Variables

### App (`.env.local`)
```env
QDRANT_API_KEY=your_api_key
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_COLLECTION=vio_products
DATABASE_URL=postgresql://user:pass@host/db
AUTH_SECRET=your_secret
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### Data Pipeline (`.env`)
```env
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_api_key
CSV_PATH=/path/to/vio_EDA.csv
IMG_ROOT=/path/to/images/
CLIP_MODEL=openai/clip-vit-base-patch32
DEVICE=cuda  # or cpu
```

## 🧪 Testing

```bash
# App tests
cd app
npm test

# Data pipeline tests
cd data-pipeline
pytest tests/
```

## 📝 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Data Pipeline Details](data-pipeline/README.md)
- [API Documentation](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Dataset: Amazon Product Data
- Model: OpenAI CLIP
- Vector Database: Qdrant
- Framework: Next.js by Vercel

---

**Built with ❤️ using AI and vector embeddings**
