from __future__ import annotations

import base64
import io
import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

_DARK_BG = "#161b22"
_DARK_TEXT = "#e6edf3"
_ACCENT_GREEN = "#3fb950"
_ACCENT_RED = "#f85149"
_ACCENT_BLUE = "#58a6ff"
_GRID_COLOR = "#30363d"


def _apply_dark_theme(ax: plt.Axes, fig: plt.Figure) -> None:
    fig.patch.set_facecolor(_DARK_BG)
    ax.set_facecolor(_DARK_BG)
    ax.tick_params(colors=_DARK_TEXT)
    ax.xaxis.label.set_color(_DARK_TEXT)
    ax.yaxis.label.set_color(_DARK_TEXT)
    ax.title.set_color(_DARK_TEXT)
    ax.grid(True, color=_GRID_COLOR, alpha=0.3)
    for spine in ax.spines.values():
        spine.set_color(_GRID_COLOR)


def render_chart_to_html(fig: plt.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (
        f'<html><body style="background:{_DARK_BG};margin:0;padding:20px;'
        f'display:flex;justify-content:center">'
        f'<img src="data:image/png;base64,{b64}" style="max-width:100%">'
        f"</body></html>"
    )


def portfolio_value_chart(
    dates: list[str],
    values: list[float],
    title: str = "Portfolio Value",
) -> str:
    fig, ax = plt.subplots(figsize=(12, 5))
    _apply_dark_theme(ax, fig)
    color = _ACCENT_GREEN if values[-1] >= values[0] else _ACCENT_RED
    ax.plot(dates, values, color=color, linewidth=2)
    ax.fill_between(dates, values, alpha=0.1, color=color)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Value (₹)")
    tick_step = max(1, len(dates) // 8)
    ax.set_xticks(range(0, len(dates), tick_step))
    ax.set_xticklabels([dates[i] for i in range(0, len(dates), tick_step)], rotation=45)
    return render_chart_to_html(fig)


def allocation_pie_chart(allocation: dict[str, float]) -> str:
    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor(_DARK_BG)
    labels = list(allocation.keys())
    sizes = list(allocation.values())
    colors = [_ACCENT_BLUE, _ACCENT_GREEN, "#d29922", _ACCENT_RED, "#a371f7", "#8b949e"]
    ax.pie(
        sizes,
        labels=labels,
        colors=colors[: len(labels)],
        autopct="%1.1f%%",
        textprops={"color": _DARK_TEXT, "fontsize": 12},
        startangle=90,
    )
    ax.set_title("Asset Allocation", fontsize=14, fontweight="bold", color=_DARK_TEXT)
    return render_chart_to_html(fig)


def gold_price_chart(
    dates: list[str],
    prices: list[float],
    sma_values: list[float | None] | None = None,
    title: str = "Gold Price — India 22K",
) -> str:
    fig, ax = plt.subplots(figsize=(12, 5))
    _apply_dark_theme(ax, fig)
    ax.plot(dates, prices, color="#d29922", linewidth=2, label="Price")
    if sma_values:
        valid_sma = [(d, v) for d, v in zip(dates, sma_values, strict=False) if v is not None]
        if valid_sma:
            sma_dates, sma_vals = zip(*valid_sma, strict=False)
            ax.plot(
                sma_dates,
                sma_vals,
                color=_ACCENT_BLUE,
                linewidth=1.5,
                linestyle="--",
                label="20-day SMA",
            )
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Price (₹/gram)")
    ax.legend(facecolor=_DARK_BG, edgecolor=_GRID_COLOR, labelcolor=_DARK_TEXT)
    tick_step = max(1, len(dates) // 8)
    ax.set_xticks(range(0, len(dates), tick_step))
    ax.set_xticklabels([dates[i] for i in range(0, len(dates), tick_step)], rotation=45)
    return render_chart_to_html(fig)
