export interface ProcessedQuery {
    semantic_expansion: string
    filter?: Record<string, unknown>
}

export interface TaxonomyData {
    categories: string[]
    subcategories: string[]
    priceBuckets: string[]
}

const OLLAMA_URL = 'http://localhost:11434/api/generate'

export async function processQuery(prompt: string, taxonomy: TaxonomyData): Promise<ProcessedQuery> {
    const systemPrompt = `You are an expert e-commerce fashion stylist and search optimizer.
Your task is to transform a user's shopping request into a structured search object.

AVAILABLE CATEGORIES: ${taxonomy.categories.join(', ')}
AVAILABLE SUBCATEGORIES: ${taxonomy.subcategories.join(', ')}
AVAILABLE PRICE BUCKETS: ${taxonomy.priceBuckets.join(', ')}

RULES:
1. "semantic_expansion": Expand query into a rich descriptive phrase. IMPORTANT: Strip specific quantities (e.g., "top 5", "3 items") from the expansion string to avoid diluting the vector search, but use them to understand "quality" intent.
2. "filter": If identifying:
   - CATEGORY/SUBCATEGORY: Match from lists.
   - PRICE RANGE (Numerical): 
     - "under X": {"key": "price", "range": {"lte": X}}
     - "over X": {"key": "price", "range": {"gte": X}}
     - "around X": {"key": "price", "range": {"gte": X*0.9, "lte": X*1.1}}
   - PRICE INTENT (Descriptive): Map "cheap/budget" to {"key": "price_bucket", "match": {"value": "Entry-Level"}}.

EXAMPLES:
- User: "laptops around $1000" -> {"filter": {"must": [{"key": "category", "match": {"value": "Laptops"}}, {"key": "price", "range": {"gte": 900, "lte": 1100}}]}}
- User: "shoes under $50" -> {"filter": {"must": [{"key": "category", "match": {"value": "Shoes"}}, {"key": "price", "range": {"lte": 50}}]}}

3. Output ONLY valid JSON.

JSON SCHEMA:
{
  "semantic_expansion": "string",
  "filter": {
    "must": [
      { "key": "category", "match": { "value": "Name" } },
      { "key": "price", "range": { "lte": 50 } }
    ]
  }
}

USER QUERY: "${prompt}"`

    try {
        const response = await fetch(OLLAMA_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: 'qwen2.5:3b-instruct',
                prompt: systemPrompt,
                stream: false,
                format: 'json'
            }),
        })

        if (!response.ok) {
            throw new Error(`Ollama error: ${response.statusText}`)
        }

        const data = await response.json()
        let rawResponse = data.response || ''

        // Cleanup markdown backticks if present
        if (rawResponse.includes('```')) {
            rawResponse = rawResponse.replace(/```(?:json)?/g, '').replace(/```/g, '').trim()
        }

        const result = JSON.parse(rawResponse)

        return {
            semantic_expansion: result.semantic_expansion || prompt,
            filter: result.filter
        }
    } catch (error) {
        console.error('[Ollama] Extraction failed:', error)
        // Fallback to original prompt if LLM fails
        return { semantic_expansion: prompt }
    }
}
