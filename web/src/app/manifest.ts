import type { MetadataRoute } from 'next'

// Install metadata ("Add to home screen"). Icons come from scripts/make_icons.py.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Fathom: product search that understands the request',
    short_name: 'Fathom',
    description:
      'Search 35K products by text or photo: hybrid retrieval, reranking, and LLM query understanding.',
    start_url: '/',
    display: 'standalone',
    background_color: '#F5F8F7',
    theme_color: '#0F2A3D',
    icons: [
      { src: '/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
