"""Label-noise detection with confident learning (Northcutt et al., 2021; cleanlab).

A title -> category classifier produces out-of-fold probabilities, so every product is
scored by a model that never saw it. Per-class threshold t_k = mean predicted
probability of class k over products labeled k. A product is flagged (*category
disagreement*) when, for every category it is listed under, p(category) < t_category,
while some other class j has p_j >= t_j. That is, the model is confidently elsewhere.

Runs on merged products (ADR-0002) with canonical categories, so multi-listed items
and alias pairs are not counted as noise. Brand-only titles are excluded: the model
has no text to judge them by.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from vio.quality.core import Dimension, Measurement, check

N_FOLDS = 5
SEED = 0
# Below this many scorable products the classifier is too weak for its disagreements to
# mean anything (on the 501-row sample it flagged 30%), so the check reports itself skipped.
MIN_PRODUCTS = 2_000


@dataclass
class LabelNoiseResult:
    flagged: pd.DataFrame  # one row per flagged product
    cv_accuracy: float
    cv_macro_f1: float
    n_scored: int
    per_category: pd.DataFrame  # category, n, flagged, rate


def _products_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Raw rows -> merged products with canonical category sets."""
    from pydantic import ValidationError

    from vio.ingest.normalize import normalize
    from vio.models import Product

    products = []
    for rec in df.to_dict("records"):
        try:
            products.append(Product.model_validate(rec))
        except ValidationError:
            continue  # invalid rows are reported by validity.rows_parse
    merged, _ = normalize(products)
    return pd.DataFrame(
        {
            "product_id": [p.product_id for p in merged],
            "merged_ids": [p.merged_ids for p in merged],
            "name": [p.name for p in merged],
            "category": [p.category for p in merged],
            "categories": [p.categories for p in merged],
            "subcategory": [p.subcategory for p in merged],
        }
    )


def detect_label_noise(df: pd.DataFrame) -> LabelNoiseResult:
    from scipy.sparse import hstack
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import SGDClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    items = _products_frame(df)
    if not items.empty:
        items = items[items["name"].astype(str).str.count(r"\S+") > 2]
        # classes need at least N_FOLDS members for stratified CV
        counts = items["category"].value_counts()
        items = items[items["category"].isin(counts[counts >= N_FOLDS].index)]
    items = items.reset_index(drop=True)
    if len(items) < MIN_PRODUCTS or items["category"].nunique() < 2:
        empty = pd.DataFrame(columns=[*items.columns, "suggested", "p_given", "p_suggested"])
        return LabelNoiseResult(empty, float("nan"), float("nan"), 0, pd.DataFrame())

    names = items["name"].tolist()
    x = hstack(
        [
            TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True).fit_transform(names),
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=3,
                sublinear_tf=True,
                max_features=200_000,
            ).fit_transform(names),
        ]
    ).tocsr()
    y = items["category"].to_numpy()
    clf = SGDClassifier(loss="log_loss", alpha=2e-6, max_iter=30, tol=None, random_state=SEED)
    cv = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    proba = cross_val_predict(clf, x, y, cv=cv, method="predict_proba")
    classes = np.unique(y)
    col = {c: i for i, c in enumerate(classes)}

    pred = classes[proba.argmax(axis=1)]
    label_idx = np.array([col[c] for c in y])
    thresholds = np.array([proba[label_idx == k, k].mean() for k in range(len(classes))])

    # a product is fine if ANY of its listed categories is above its class threshold
    given_ok = np.array(
        [
            any(proba[i, col[c]] >= thresholds[col[c]] for c in cats if c in col)
            for i, cats in enumerate(items["categories"])
        ]
    )
    confident_elsewhere = proba >= thresholds  # (n, k)
    for i, cats in enumerate(items["categories"]):
        for c in cats:
            if c in col:
                confident_elsewhere[i, col[c]] = False
    suspect = ~given_ok & confident_elsewhere.any(axis=1)

    p_given = proba[np.arange(len(y)), label_idx]
    masked = np.where(confident_elsewhere, proba, -1)
    alt = masked.argmax(axis=1)
    flagged = items.assign(
        suggested=classes[alt],
        p_given=p_given.round(3),
        p_suggested=proba[np.arange(len(y)), alt].round(3),
        margin=(proba[np.arange(len(y)), alt] - p_given).round(3),
    )[suspect].sort_values("margin", ascending=False)

    per_cat = (
        items.assign(flagged=suspect)
        .groupby("category")
        .agg(n=("flagged", "size"), flagged=("flagged", "sum"))
        .assign(rate=lambda d: (d["flagged"] / d["n"]).round(4))
        .sort_values("rate", ascending=False)
        .reset_index()
    )
    return LabelNoiseResult(
        flagged=flagged,
        cv_accuracy=float(accuracy_score(y, pred)),
        cv_macro_f1=float(f1_score(y, pred, average="macro")),
        n_scored=len(items),
        per_category=per_cat,
    )


@check(
    "labels.category_disagreement",
    Dimension.LABELS,
    "Share of products whose title confidently points to a category they are not listed in "
    "(confident learning, 5-fold out-of-fold). A manual audit found most are taxonomy "
    "overlap, not errors: see data/reports/label_noise_audit.csv",
    flag="category_disagreement",
)
def category_disagreement(df: pd.DataFrame) -> Measurement:
    r = detect_label_noise(df)
    if r.n_scored == 0:
        return Measurement(
            metric=0.0,
            details={"skipped": f"fewer than {MIN_PRODUCTS:,} scorable products; too few to train"},
        )
    ids = [pid for ids in r.flagged["merged_ids"] for pid in ids]
    examples = (
        r.flagged[["product_id", "name", "category", "suggested", "p_given", "p_suggested"]]
        .head(8)
        .to_dict("records")
    )
    annotations = {
        pid: {"suggested_category": sug, "p_suggested": float(p)}
        for ids_, sug, p in zip(
            r.flagged["merged_ids"], r.flagged["suggested"], r.flagged["p_suggested"], strict=True
        )
        for pid in ids_
    }
    return Measurement(
        metric=len(r.flagged) / max(r.n_scored, 1),
        n_affected=len(r.flagged),
        affected_ids=ids,
        annotations=annotations,
        examples=[{str(k): v for k, v in e.items()} for e in examples],
        details={
            "classifier": "TF-IDF word 1-2 + char 3-5 -> SGD logistic, 5-fold out-of-fold",
            "cv_accuracy": round(r.cv_accuracy, 3),
            "cv_macro_f1": round(r.cv_macro_f1, 3),
            "products_scored": r.n_scored,
            "rate_by_category": {
                str(c): float(rate)
                for c, rate in zip(
                    r.per_category.get("category", []), r.per_category.get("rate", []), strict=True
                )
            },
            "highest_noise_categories": {
                str(c): float(rate)
                for c, rate in zip(
                    r.per_category.get("category", [])[:5],
                    r.per_category.get("rate", [])[:5],
                    strict=True,
                )
            },
        },
    )


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return (centre - half, centre + half)


def audit_section(audit_csv: Path, n_flags: int) -> str:
    """Summarize the manual review of a random sample of flags (precision estimate)."""
    a = pd.read_csv(audit_csv)
    n = len(a)
    counts = a["verdict"].value_counts()
    k = int(counts.get("error", 0))
    lo, hi = wilson_interval(k, n)
    rows = "\n".join(f"| {v} | {int(c)} | {c / n:.1%} |" for v, c in counts.items())
    errors = a[a["verdict"] == "error"]
    ex = "\n".join(
        f"- *{str(name)[:70]}*: listed under **{cat} > {sub}** ({note})"
        for name, cat, sub, note in zip(
            errors["name"], errors["category"], errors["subcategory"], errors["note"], strict=True
        )
    )
    return f"""
A random sample of {n} flags (seed 7) was reviewed by hand
(`data/reports/label_noise_audit.csv`; reviewer: {a["reviewer"].iloc[0]}).

| Verdict | Count | Share |
|---|---|---|
{rows}

- **error**: the listing is wrong. **taxonomy_overlap**: the listing is valid in the source
  taxonomy and the suggested category is also valid. **model_wrong**: the listing is
  correct and the suggestion is not.
- **Precision for real errors: {k / n:.1%}** (Wilson 95% CI {lo:.1%} to {hi:.1%}), so about
  **{k / n * n_flags:.0f}** ({lo * n_flags:.0f} to {hi * n_flags:.0f}) of the {n_flags:,} flags
  are genuinely mislabeled, around {k / n * n_flags / 35_736:.1%} of products.
- The dominant pattern is **overlapping departments** in the source taxonomy (sunscreen
  under both Camping and Beauty; chairs under Furniture, Office, and Gaming). Real errors
  look like **keyword collisions in the original scrape**:

{ex}

**Policy (T085):** flagged products keep their listed categories and **gain the suggested
category** (valid in about {(k + int(counts.get("taxonomy_overlap", 0))) / n:.0%} of
reviewed cases), so category filters stop missing them. Nothing is relabeled or dropped.
"""
