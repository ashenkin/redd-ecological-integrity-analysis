"""
Dot plot: Project start date (x) vs ecological outcome quality (y).

Y-axis options:
  A) mean_rv_q — mean robustness value across metrics (proxy from sensitivity data,
     available now from Zenodo Extended Data Table 4).
     Higher = effect harder to explain away = stronger evidence of benefit.

  B) mean_effect — mean standardized effect size across metrics (preferred).
     Requires source data from the paper (Source Data Fig. 1 / LinearModels output).
     Drop a CSV at data/source_data/effect_sizes.csv with columns:
       uid, metric, estimate, std_error, p_value, comparison
     and re-run with --use-effect-sizes.

Usage:
  python plot_outcomes_over_time.py                    # uses rv_q proxy
  python plot_outcomes_over_time.py --use-effect-sizes # uses real effect estimates

Output: results/outcomes_over_time.png
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

METADATA_CSV = DATA_DIR / "registry_metadata" / "project_metadata.csv"
SENSITIVITY_CSV = DATA_DIR / "registry_metadata" / "sensitivity_data.csv"
EFFECT_SIZE_CSV = DATA_DIR / "source_data" / "effect_sizes.csv"


# ── helpers ──────────────────────────────────────────────────────────────────

def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def parse_date(date_str):
    """Parse DD/MM/YYYY or YYYY-MM-DD or YYYY → datetime."""
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    # Try extracting a 4-digit year
    m = re.search(r"\b(19|20)\d{2}\b", date_str)
    if m:
        try:
            return datetime.strptime(m.group(0), "%Y")
        except ValueError:
            pass
    return None


# ── load data ─────────────────────────────────────────────────────────────────

def load_metadata():
    rows = read_csv(METADATA_CSV)
    meta = {}
    for r in rows:
        uid = r["uid"]
        dt = parse_date(r.get("start_date", ""))
        meta[uid] = {
            "start_year": dt.year if dt else None,
            "start_date_dt": dt,
            "registry": r.get("registry", ""),
            "country": r.get("gid0_shapefile") or r.get("country", ""),
            "methodology": r.get("methodology", ""),
        }
    return meta


def load_sensitivity_proxy():
    """Returns {uid: mean_rv_q} for primary comparison."""
    rows = read_csv(SENSITIVITY_CSV)
    from collections import defaultdict
    uid_rvq = defaultdict(list)
    for r in rows:
        # Primary comparison: unprotected REDD vs unprotected controls
        if "no REDD" in r.get("comparison", "") and "PA" not in r.get("comparison", "").replace("no REDD", ""):
            try:
                uid_rvq[r["uid"]].append(float(r["rv_q"]))
            except (ValueError, TypeError):
                pass
    return {uid: sum(v) / len(v) for uid, v in uid_rvq.items() if v}


def load_effect_sizes():
    """Returns {uid: mean_estimate} for primary comparison."""
    if not EFFECT_SIZE_CSV.exists():
        print(f"ERROR: {EFFECT_SIZE_CSV} not found.")
        print("Download Source Data Fig. 1 from https://doi.org/10.1038/s41558-026-02657-2")
        print("and save as data/source_data/effect_sizes.csv with columns:")
        print("  uid, metric, estimate, std_error, p_value, comparison")
        sys.exit(1)
    rows = read_csv(EFFECT_SIZE_CSV)
    from collections import defaultdict
    uid_effects = defaultdict(list)
    for r in rows:
        if "no REDD, No PA" in r.get("comparison", ""):
            try:
                uid_effects[r["uid"]].append(float(r["estimate"]))
            except (ValueError, TypeError):
                pass
    return {uid: sum(v) / len(v) for uid, v in uid_effects.items() if v}


# ── plot ───────────────────────────────────────────────────────────────────────

REGISTRY_COLORS = {
    "VCS":     "#2196F3",  # blue
    "ACCU":    "#4CAF50",  # green
    "ACR":     "#FF9800",  # orange
    "CAR":     "#9C27B0",  # purple
    "UNKNOWN": "#9E9E9E",  # grey
}


def make_plot(uid_years, uid_outcomes, meta, outcome_label, out_path):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
    except ImportError:
        print("matplotlib + numpy required: pip install matplotlib numpy")
        sys.exit(1)

    # Build arrays
    points = []
    for uid, year in uid_years.items():
        if uid in uid_outcomes and year is not None:
            points.append({
                "uid": uid,
                "year": year,
                "outcome": uid_outcomes[uid],
                "registry": meta.get(uid, {}).get("registry", "UNKNOWN"),
                "country": meta.get(uid, {}).get("country", ""),
            })

    if not points:
        print("No data to plot — missing start dates or outcome values.")
        return

    x = np.array([p["year"] for p in points])
    y = np.array([p["outcome"] for p in points])
    colors = [REGISTRY_COLORS.get(p["registry"], "#9E9E9E") for p in points]

    fig, ax = plt.subplots(figsize=(11, 7))

    ax.scatter(x, y, c=colors, alpha=0.75, s=60, edgecolors="white", linewidths=0.5, zorder=3)

    # Trend line
    if len(points) >= 5:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        xfit = np.linspace(x.min(), x.max(), 200)
        ax.plot(xfit, p(xfit), color="#333333", linewidth=1.5, linestyle="--",
                alpha=0.6, zorder=2, label=f"Trend (slope={z[0]:.2f}/yr)")

    ax.axhline(0, color="#777777", linewidth=0.8, linestyle="-", alpha=0.4, zorder=1)

    # Labels
    ax.set_xlabel("Project start year", fontsize=13)
    ax.set_ylabel(outcome_label, fontsize=13)
    ax.set_title(
        "REDD+ project ecological outcomes over time\n"
        "Ong et al. 2026, Nature Climate Change (n={})".format(len(points)),
        fontsize=14,
    )

    # Legend — registries
    handles = [
        mpatches.Patch(color=c, label=reg)
        for reg, c in REGISTRY_COLORS.items()
        if any(p["registry"] == reg for p in points)
    ]
    trend_handles = [h for h in ax.get_lines() if "Trend" in h.get_label()]
    ax.legend(handles=handles + trend_handles, title="Registry", fontsize=9, title_fontsize=9)

    ax.grid(True, alpha=0.25, zorder=0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved plot → {out_path}")

    # Print quick stats
    print(f"\nn = {len(points)} projects plotted")
    print(f"Year range: {int(x.min())} – {int(x.max())}")
    print(f"Outcome range: {y.min():.2f} – {y.max():.2f}")
    if len(points) >= 5:
        slope = np.polyfit(x, y, 1)[0]
        print(f"Trend slope: {slope:.3f} per year ({'improving' if slope > 0 else 'worsening'} over time)")


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-effect-sizes", action="store_true",
                        help="Use real standardized effect sizes instead of rv_q proxy")
    args = parser.parse_args()

    if not METADATA_CSV.exists():
        print(f"Project metadata not found at {METADATA_CSV}")
        print("Run: python fetch_project_metadata.py")
        sys.exit(1)

    if not SENSITIVITY_CSV.exists():
        print(f"Sensitivity data not found at {SENSITIVITY_CSV}")
        print("Run: python load_sensitivity_data.py")
        sys.exit(1)

    meta = load_metadata()

    if args.use_effect_sizes:
        uid_outcomes = load_effect_sizes()
        outcome_label = "Mean standardized effect size (5 ecological indicators)\nPositive = better ecological integrity than matched controls"
        out_path = RESULTS_DIR / "outcomes_over_time_effect_sizes.png"
    else:
        uid_outcomes = load_sensitivity_proxy()
        outcome_label = (
            "Mean robustness value rv_q across metrics [%]\n"
            "(proxy for effect strength; higher = harder to explain away)"
        )
        out_path = RESULTS_DIR / "outcomes_over_time_rvq_proxy.png"

    uid_years = {uid: info["start_year"] for uid, info in meta.items()}

    make_plot(uid_years, uid_outcomes, meta, outcome_label, out_path)


if __name__ == "__main__":
    main()
