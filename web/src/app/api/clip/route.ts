export const runtime = 'nodejs'
export const maxDuration = 60

import { pipeline, env } from '@xenova/transformers'

// Configure for server-side
env.useBrowserCache = false
env.allowLocalModels = false

// Singleton pipelines
// Legacy route: removed in T051 when CLIP moves to the Python backend.
// The library's pipeline union type is too broad, so narrow it to what we use.
type FeaturePipeline = (input: string, options?: Record<string, unknown>) => Promise<{ data: Float32Array }>

let textPipeline: FeaturePipeline | null = null
let imagePipeline: FeaturePipeline | null = null

const MODEL_NAME = 'Xenova/clip-vit-base-patch32'

async function getTextPipeline() {
  if (!textPipeline) {
    textPipeline = (await pipeline('feature-extraction', MODEL_NAME, {
      quantized: false,
    })) as unknown as FeaturePipeline
  }
  return textPipeline
}

async function getImagePipeline() {
  if (!imagePipeline) {
    imagePipeline = (await pipeline('image-feature-extraction', MODEL_NAME, {
      quantized: false,
    })) as unknown as FeaturePipeline
  }
  return imagePipeline
}

function l2Normalize(vector: number[]): number[] {
  const norm = Math.sqrt(vector.reduce((sum, val) => sum + val * val, 0))
  if (norm === 0) return vector
  return vector.map(val => val / norm)
}

export async function POST(request: Request) {
  try {
    const { text, imageBase64 } = await request.json()

    let textVector: number[] | null = null
    let imageVector: number[] | null = null

    // Generate text embedding
    if (text) {
      const extractor = await getTextPipeline()
      const output = await extractor(text, { pooling: 'mean', normalize: true })
      textVector = l2Normalize(Array.from(output.data))
    }

    // Generate image embedding
    if (imageBase64) {
      const extractor = await getImagePipeline()

      // Handle base64 format
      let imageData = imageBase64
      if (imageBase64.includes(',')) {
        imageData = imageBase64.split(',')[1]
      }
      const dataUrl = `data:image/jpeg;base64,${imageData}`

      const output = await extractor(dataUrl)
      imageVector = l2Normalize(Array.from(output.data))
    }

    return Response.json({ textVector, imageVector })
  } catch (error) {
    console.error('[CLIP API] Error:', error)
    return Response.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    )
  }
}
