"""Static figures for the data-quality report (PNG, light surface).

Follows the dataviz method: one series per chart in the reference blue (validated:
contrast >= 3:1 on the surface), text in ink tokens, hairline recessive grid, thin
bars, 2px lines, >= 8px markers with a surface ring, selective direct labels.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from vio.catalog import canonical_category
from vio.quality.core import AuditReport
from vio.quality.derived import PriorEstimate

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e6e5e1"
SERIES = "#2a78d6"  # reference categorical slot 1 (blue)
DPI = 160


HEADER_IN = 0.85  # space reserved above the plot for title + subtitle, in inches


def _style(ax: Axes, title: str, subtitle: str) -> None:
    fig = ax.figure
    assert isinstance(fig, Figure)
    h = fig.get_figheight()
    ax.set_facecolor(SURFACE)
    fig.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    # Fixed offsets in inches so short and tall figures lay out the same way.
    fig.text(0.01, 1 - 0.12 / h, title, fontsize=12.5, color=INK, weight="bold", va="top")
    fig.text(0.01, 1 - 0.45 / h, subtitle, fontsize=9.5, color=INK_2, va="top")
    fig.subplots_adjust(top=1 - HEADER_IN / h)


def rating_variance(prior: PriorEstimate, out: Path) -> Path:
    bins = pd.DataFrame(prior.bins)
    reviews = 1 / bins["inv_v"]
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=DPI)
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.13)
    v = np.logspace(np.log10(reviews.min()), np.log10(reviews.max()), 200)
    ax.plot(v, prior.tau2 + prior.sigma2 / v, color=MUTED, linewidth=2, solid_capstyle="round")
    ax.scatter(reviews, bins["var"], s=64, color=SERIES, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.set_xscale("log")
    ax.set_xlabel("Average review count in bin (log scale)", color=INK_2, fontsize=9.5)
    ax.set_ylabel("Variance of rating around category mean", color=INK_2, fontsize=9.5)
    ax.grid(axis="y", color=GRID, linewidth=1)
    x_lab = reviews.iloc[len(reviews) // 3]
    ax.annotate(
        f"model τ² + σ²/v   (σ = {prior.sigma2**0.5:.2f}, τ = {prior.tau2**0.5:.2f}, m = {prior.m:.0f})",
        xy=(x_lab, prior.tau2 + prior.sigma2 / x_lab),
        xytext=(12, 22),
        textcoords="offset points",
        color=INK_2,
        fontsize=9,
    )
    _style(
        ax,
        "Ratings get less noisy as reviews accumulate",
        "Each dot is one of 20 review-count bins. The fitted curve gives the empirical-Bayes prior (ADR-0003).",
    )
    path = out / "rating_variance.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def _hbar(
    labels: list[str],
    values: list[float],
    out: Path,
    name: str,
    title: str,
    subtitle: str,
    fmt: str,
    label_top: int | None = None,
    xlabel: str = "",
) -> Path:
    n = len(labels)
    fig, ax = plt.subplots(figsize=(8, 1.5 + 0.27 * n), dpi=DPI)
    fig.subplots_adjust(left=0.3, right=0.93, bottom=0.6 / (1.5 + 0.27 * n))
    y = np.arange(n)[::-1]
    ax.barh(y, values, height=0.62, color=SERIES)
    ax.set_yticks(y, labels, color=INK, fontsize=9)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9.5)
    top = n if label_top is None else label_top
    for yi, v in list(zip(y, values, strict=True))[:top]:
        ax.text(v, yi, "  " + fmt.format(v), va="center", color=INK_2, fontsize=8.5)
    ax.set_xlim(0, max(values) * 1.15)
    _style(ax, title, subtitle)
    path = out / name
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def disagreement_by_category(report: AuditReport, out: Path) -> Path | None:
    res = next((r for r in report.results if r.name == "labels.category_disagreement"), None)
    rates = res.measurement.details.get("rate_by_category", {}) if res else {}
    if not rates:
        return None
    items = sorted(rates.items(), key=lambda kv: -kv[1])
    return _hbar(
        [k for k, _ in items],
        [v * 100 for _, v in items],
        out,
        "category_disagreement.png",
        "Where titles disagree with their category",
        "Share of products whose title confidently points to another category. "
        "Mostly overlapping departments, not errors.",
        "{:.1f}%",
        label_top=3,
        xlabel="Products flagged (%)",
    )


def flag_counts(report: AuditReport, out: Path) -> Path:
    counts: dict[str, int] = {}
    for fl in report.flags().values():
        for f in fl:
            counts[f] = counts.get(f, 0) + 1
    items = sorted(counts.items(), key=lambda kv: -kv[1])
    return _hbar(
        [k for k, _ in items],
        [float(v) for _, v in items],
        out,
        "quality_flags.png",
        "Row-level quality flags",
        f"Rows carrying each flag (of {report.n_rows:,}). Flagged rows are kept; see the policy in data/README.md.",
        "{:,.0f}",
        xlabel="Rows",
    )


def price_by_category(df: pd.DataFrame, out: Path) -> Path:
    cats = df["category"].map(canonical_category)
    groups = df.assign(cat=cats).groupby("cat")["price"]
    order = groups.median().sort_values().index.tolist()
    data = [np.log10(groups.get_group(c).astype(float)) for c in order]
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.27 * len(order)), dpi=DPI)
    fig.subplots_adjust(left=0.3, right=0.96, bottom=0.07)
    ax.boxplot(
        data,
        vert=False,
        widths=0.55,
        patch_artist=True,
        showfliers=True,
        boxprops={"facecolor": SERIES, "edgecolor": SERIES, "alpha": 0.9},
        medianprops={"color": SURFACE, "linewidth": 2},
        whiskerprops={"color": MUTED},
        capprops={"color": MUTED},
        flierprops={
            "marker": "o",
            "markersize": 2,
            "markerfacecolor": MUTED,
            "markeredgecolor": "none",
            "alpha": 0.5,
        },
    )
    ax.set_yticks(range(1, len(order) + 1), order, color=INK, fontsize=9)
    ticks = [-1, 0, 1, 2, 3, 4]
    ax.set_xticks(ticks, [f"${10**t:,.0f}" if t >= 0 else "$0.1" for t in ticks])
    ax.set_xlabel("Price (log scale)", color=INK_2, fontsize=9.5)
    _style(
        ax,
        "Price spread by category",
        "Box = middle 50% of prices; dots beyond the whiskers include the flagged outliers.",
    )
    path = out / "price_by_category.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def make_figures(
    df: pd.DataFrame, report: AuditReport, prior: PriorEstimate, out: Path
) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [rating_variance(prior, out), flag_counts(report, out), price_by_category(df, out)]
    d = disagreement_by_category(report, out)
    return paths + ([d] if d else [])
