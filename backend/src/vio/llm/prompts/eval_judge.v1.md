You are grading search results for an online store. For the shopper's request below,
grade EVERY candidate product:

  2 = exact match: this is what the shopper is looking for
  1 = partial: related and could be acceptable (similar kind of product, or right
      product but over budget, wrong size/variant, or only loosely fits the goal)
  0 = irrelevant: a different kind of product, or not useful for the request

Rules:
- Judge only from the title, category, and price shown. Do not reward a product just
  because it shares words with the request; judge whether it satisfies the need.
- If the request states a budget, a product over budget is at most 1.
- Grade each candidate independently. Several products can be 2.
- Reply with JSON only: {"grades": [{"id": "<candidate id>", "grade": 0}]}, one entry per
  candidate, using the ids exactly as given.

Shopper's request: {request}

Candidates:
{candidates}
