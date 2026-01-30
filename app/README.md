# VIO Shop - Web Application

AI-powered e-commerce platform built with Next.js 16, featuring semantic product search using vector embeddings.

## Tech Stack

- **Framework**: Next.js 16.0 with TypeScript
- **UI**: Radix UI + Tailwind CSS
- **Database**: Prisma ORM (SQLite dev, PostgreSQL production)
- **Vector DB**: Qdrant Cloud
- **Auth**: NextAuth.js (via AUTH_SECRET)
- **Deployment**: Vercel recommended

## Setup

### Install Dependencies

```bash
npm install
```

### Environment Configuration

Create `.env.local` from the template:

```env
# Qdrant Vector Database
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_COLLECTION=vio_products

# Database (SQLite for local dev)
DATABASE_URL="file:./dev.db"

# Auth
AUTH_SECRET=your_secret_key_here

# App URL
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### Database Setup

```bash
# Generate Prisma client
npx prisma generate

# Run migrations (if applicable)
npx prisma migrate dev

# Open Prisma Studio to view data
npx prisma studio
```

### Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Project Structure

```
app/
├── src/
│   ├── app/           # Next.js 16 app directory
│   ├── components/    # React components
│   ├── lib/          # Utilities and helpers
│   └── styles/       # Global styles
├── public/           # Static assets
├── prisma/
│   └── schema.prisma # Database schema
└── package.json
```

## Key Features

- **Vector Search**: Semantic product search using CLIP embeddings
- **Product Catalog**: Browse 42K+ products with filters
- **Smart Recommendations**: AI-driven suggestions
- **Responsive Design**: Mobile-first UI with Tailwind CSS

## Available Scripts

```bash
npm run dev      # Start development server
npm run build    # Build for production
npm run start    # Start production server
npm run lint     # Run ESLint
npm run format   # Format code with Prettier
```

## Qdrant Integration

The app connects to Qdrant for vector similarity search. Products have both text and image embeddings (512-dimensional CLIP vectors).

Example query:
```typescript
// Search products by text similarity
const results = await qdrantClient.search(collection, {
  vector: textEmbedding,
  limit: 10
});
```

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

Set environment variables in Vercel dashboard.

### Other Platforms

Ensure the following:
- Node.js 18+
- PostgreSQL database for production
- Environment variables configured

## Troubleshooting

**Issue**: Database connection error
**Solution**: Check `DATABASE_URL` in `.env.local`

**Issue**: Qdrant connection timeout
**Solution**: Verify `QDRANT_URL` and `QDRANT_API_KEY`

**Issue**: Build fails
**Solution**: Run `npm ci` to clean install dependencies

## License

MIT
