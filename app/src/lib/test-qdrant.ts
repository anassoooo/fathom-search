import dotenv from 'dotenv'
import path from 'path'

dotenv.config({ path: path.join(__dirname, '../../.env') })

const QDRANT_URL = process.env.QDRANT_URL
const QDRANT_API_KEY = process.env.QDRANT_API_KEY
const COLLECTION_NAME = process.env.QDRANT_COLLECTION || 'vio_products'

async function test() {
    console.log('Testing Qdrant connection...')
    console.log('URL:', QDRANT_URL)
    console.log('Collection:', COLLECTION_NAME)

    if (!QDRANT_URL || !QDRANT_API_KEY) {
        console.error('Missing QDRANT_URL or QDRANT_API_KEY')
        process.exit(1)
    }

    const url = `${QDRANT_URL}/collections/${COLLECTION_NAME}/points/count`
    console.log('Fetching:', url)

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'api-key': QDRANT_API_KEY,
            },
            body: JSON.stringify({ exact: true }),
        })

        console.log('Status:', response.status)
        const data = await response.json()
        console.log('Data:', JSON.stringify(data, null, 2))
    } catch (error) {
        console.error('Fetch error:', error)
    }
}

test()
