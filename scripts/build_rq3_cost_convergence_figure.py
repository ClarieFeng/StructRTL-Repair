"""Build the manuscript RQ3 cost and convergence figures.

The figure uses frozen derived evidence under paper_evidence_private and writes
publication assets into submission/figures. It does not recompute experiment
results.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "paper_single_agent_workflow" / "paper_evidence_private" / "RQ3_robustness_cost" / "runtime"
OUT_DIR = ROOT / "paper_single_agent_workflow" / "submission" / "figures"


MODE_LABELS = {
    "origin": "Origin",
    "reflect_patch": "Patch",
    "reflect_rag_skeleton": "Complete",
}

MODEL_LABELS = {
    "MGEMMV-Qwen-7B": "MGEMMV Qwen",
    "MGEMMV-Llama-11B": "MGEMMV Llama",
    "Qwen2.5-VL-7B-Instruct": "Qwen2.5 VL",
    "Qwen3-VL-8B-Instruct": "Qwen3 VL",
    "MiniCPM-V-4.5-8B": "MiniCPM",
    "Llama-3.2-11B-Vision-Instruct": "Llama 3.2",
    "InternVL3.5-8B-Instruct": "InternVL3.5",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_aggregates(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        mode = row["mode"]
        total = int(row["total_cases"])
        out[mode]["total"] += total
        out[mode]["functional"] += int(row["functional_pass"])
        out[mode]["round_sum"] += float(row["avg_iterations"]) * total
        coverage = int(row["elapsed_coverage"].split("/")[0])
        out[mode]["elapsed_sum"] += float(row["avg_elapsed_seconds"]) * coverage
        out[mode]["elapsed_n"] += coverage
    return out


def build_success_distribution(rows: list[dict[str, str]]) -> dict[str, Counter]:
    out: dict[str, Counter] = {m: Counter() for m in MODE_LABELS}
    for row in rows:
        mode = row["mode"]
        if mode not in out:
            continue
        out[mode]["total"] += int(row["success_total"])
        out[mode]["round1"] += int(row["success_iter1"])
        out[mode]["round2"] += int(row["success_iter2"])
        out[mode]["round3"] += int(row["success_iter3"])
    return out


def build_run_pairs(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        grouped[(row["model"], row["dataset"])][row["mode"]] = row
    pairs = []
    for (model, dataset), modes in grouped.items():
        if "reflect_patch" not in modes or "reflect_rag_skeleton" not in modes:
            continue
        patch = modes["reflect_patch"]
        full = modes["reflect_rag_skeleton"]
        pairs.append(
            {
                "model": model,
                "dataset": dataset,
                "patch_sec": float(patch["avg_elapsed_seconds"]),
                "full_sec": float(full["avg_elapsed_seconds"]),
                "patch_rounds": float(patch["avg_iterations"]),
                "full_rounds": float(full["avg_iterations"]),
                "case_gain": int(full["functional_pass"]) - int(patch["functional_pass"]),
                "rate_gain": (float(full["functional_rate"]) - float(patch["functional_rate"])) * 100.0,
            }
        )
    order = {name: i for i, name in enumerate(MODEL_LABELS)}
    pairs.sort(key=lambda r: (order.get(str(r["model"]), 999), str(r["dataset"])))
    return pairs


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.size": 10.0,
            "axes.titlesize": 11.5,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.2,
            "legend.fontsize": 9.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def color_map() -> dict[str, str]:
    return {
        "origin": "#8F969E",
        "reflect_patch": "#4C78A8",
        "reflect_rag_skeleton": "#3A9D63",
        "round1": "#3A9D63",
        "round2": "#E0A53A",
        "round3": "#C95F5F",
    }


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(OUT_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight")
    print(OUT_DIR / f"{stem}.pdf")


def draw_round_distribution(success: dict[str, Counter], colors: dict[str, str]) -> None:
    modes = ["origin", "reflect_patch", "reflect_rag_skeleton"]
    fig, ax1 = plt.subplots(figsize=(7.2, 3.8))
    fig.subplots_adjust(left=0.16, right=0.89, top=0.84, bottom=0.34)

    y = np.arange(len(modes))
    round_keys = [("round1", "Round 1"), ("round2", "Round 2"), ("round3", "Round 3")]
    left = np.zeros(len(modes))
    for key, label in round_keys:
        vals = np.array([
            success[m][key] / success[m]["total"] if success[m]["total"] else 0
            for m in modes
        ])
        bars = ax1.barh(y, vals, left=left, color=colors[key], label=label, height=0.62)
        for i, (bar, val) in enumerate(zip(bars, vals)):
            if val < 0.035:
                continue
            txt = f"{val * 100:.1f}%"
            ax1.text(
                left[i] + val / 2,
                bar.get_y() + bar.get_height() / 2,
                txt,
                ha="center",
                va="center",
                fontsize=8.8,
                color="white" if key != "round2" else "#1F2328",
            )
        left += vals
    for i, m in enumerate(modes):
        ax1.text(1.025, i, f"n={success[m]['total']}", va="center", fontsize=9)
    ax1.set_yticks(y, [MODE_LABELS[m] for m in modes])
    ax1.invert_yaxis()
    ax1.set_xlim(0, 1.16)
    ax1.set_xlabel("Share of successful cases")
    ax1.set_title("Successful workflow round")
    ax1.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=3)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="x", color="#D8DDE3", linewidth=0.6)
    ax1.set_axisbelow(True)

    save_figure(fig, "figure_rq3_round_distribution")
    plt.close(fig)


def draw_model_cost_benefit(pairs: list[dict[str, object]]) -> None:
    rows = sorted(pairs, key=lambda r: float(r["rate_gain"]))
    labels = [f"{MODEL_LABELS.get(str(r['model']), str(r['model']))} / {r['dataset']}" for r in rows]
    gains = np.array([float(r["rate_gain"]) for r in rows])
    case_gains = [int(r["case_gain"]) for r in rows]
    delta_sec = np.array([float(r["full_sec"]) - float(r["patch_sec"]) for r in rows])
    delta_rounds = np.array([float(r["full_rounds"]) - float(r["patch_rounds"]) for r in rows])

    fig, ax = plt.subplots(figsize=(7.6, 5.7))
    fig.subplots_adjust(left=0.34, right=0.96, top=0.91, bottom=0.14)
    y = np.arange(len(rows))
    colors = np.where(delta_sec <= 0, "#3A9D63", "#C95F5F")

    ax.hlines(y, 0, gains, color="#CDD3DA", linewidth=2.2, zorder=1)
    ax.scatter(gains, y, s=72, color=colors, edgecolor="#222222", linewidth=0.5, zorder=3)
    for yi, gain, cases, dsec, dround in zip(y, gains, case_gains, delta_sec, delta_rounds):
        label = f"+{cases}, Δt {dsec:+.0f}s, Δr {dround:+.2f}"
        ax.text(gain + 1.6, yi, label, va="center", fontsize=8.7)

    ax.axvline(0, color="#838B95", linewidth=0.8)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Functional pass@1 gain over feedback patching (percentage points)")
    ax.set_title("Model level cost benefit of the complete workflow")
    ax.set_xlim(0, max(gains) + 17)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#D8DDE3", linewidth=0.6)
    ax.set_axisbelow(True)
    save_figure(fig, "figure_rq3_model_cost_benefit")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mode_rows = read_csv(EVIDENCE / "runtime_cost_by_mode.csv")
    success_rows = read_csv(EVIDENCE / "iteration_distribution_success.csv")

    configure_matplotlib()
    colors = color_map()
    success = build_success_distribution(success_rows)
    pairs = build_run_pairs(mode_rows)

    draw_round_distribution(success, colors)
    draw_model_cost_benefit(pairs)


if __name__ == "__main__":
    main()
