You write realistic search queries that shoppers would type into an online store's
search box. You will receive a list of products. For EACH product write three queries
that this product would be a good answer to:

1. "specific": names the kind of product precisely; may include the brand. 3-8 words.
2. "descriptive": describes the NEED or use case in everyday words, the way someone who
   does not know the product name would search. Do NOT copy distinctive words from the
   title (no brand, no model numbers, no long title phrases). 4-10 words.
3. "constrained": a descriptive query plus a budget, e.g. "... under $40". Pick a budget
   the product satisfies, between 1.1x and 2x its price, rounded to a natural number.
   Return the budget as "price_max".

Rules:
- Write like a real shopper: lowercase is fine, no marketing language, no quotes.
- Never mention the product ID.
- Reply with JSON only, in exactly this shape:
{"items": [{"product_id": "...", "specific": "...", "descriptive": "...",
            "constrained": {"query": "...", "price_max": 40}}]}

Products:
{products}
