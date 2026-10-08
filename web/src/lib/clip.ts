const CLIP_API_URL = '/api/clip'

// For server-side calls, we need absolute URL
function getClipUrl() {
  // In server context, use internal URL
  if (typeof window === 'undefined') {
    const baseUrl = process.env.VERCEL_URL 
      ? `https://${process.env.VERCEL_URL}` 
      : 'http://localhost:3000'
    return `${baseUrl}/api/clip`
  }
  return CLIP_API_URL
}

interface ClipResponse {
  textVector: number[] | null
  imageVector: number[] | null
  error?: string
}

/**
 * Get CLIP text embedding
 * @param text - Text to embed
 * @returns 512-dimensional L2-normalized vector
 */
export async function getTextEmbedding(text: string): Promise<number[]> {
  const response = await fetch(getClipUrl(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`CLIP API error: ${response.status} - ${errorText}`)
  }

  const data: ClipResponse = await response.json()
  
  if (data.error) {
    throw new Error(`CLIP API error: ${data.error}`)
  }
  
  if (!data.textVector) {
    throw new Error('No text embedding returned')
  }

  return data.textVector
}

/**
 * Get CLIP image embedding
 * @param imageBase64 - Base64 encoded image
 * @returns 512-dimensional L2-normalized vector
 */
export async function getImageEmbedding(imageBase64: string): Promise<number[]> {
  const response = await fetch(getClipUrl(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ imageBase64 }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`CLIP API error: ${response.status} - ${errorText}`)
  }

  const data: ClipResponse = await response.json()
  
  if (data.error) {
    throw new Error(`CLIP API error: ${data.error}`)
  }
  
  if (!data.imageVector) {
    throw new Error('No image embedding returned')
  }

  return data.imageVector
}

/**
 * Get both text and image embeddings in one call
 */
export async function getBlendedEmbeddings(
  text: string | null,
  imageBase64: string | null
): Promise<{ textVector: number[] | null; imageVector: number[] | null }> {
  const response = await fetch(getClipUrl(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, imageBase64 }),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`CLIP API error: ${response.status} - ${errorText}`)
  }

  const data: ClipResponse = await response.json()
  
  if (data.error) {
    throw new Error(`CLIP API error: ${data.error}`)
  }

  return {
    textVector: data.textVector,
    imageVector: data.imageVector,
  }
}
