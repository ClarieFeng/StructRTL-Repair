"""Paired significance analysis for V6.2 ablation CSV files.

Each comparison is paired by (module_id, test_id) within one run.  The script
reports exact two-sided McNemar tests and paired-bootstrap confidence intervals
for syntax and functional pass-rate deltas.  It deliberately does not pool
different models or datasets unless they are provided as separate --run items.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from pathlib import Path


DEFAULT_COMPARISONS = (
    ("origin", "reflect_patch"),
    ("reflect_patch", "reflect_rag_skeleton"),
    ("origin", "reflect_rag_skeleton"),
)


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--run must use LABEL=PATH")
    label, raw_path = value.split("=", 1)
    path = Path(raw_path).expanduser().resolve()
    if not label.strip() or not path.exists():
        raise argparse.ArgumentTypeError(f"Invalid run: {value}")
    return label.strip(), path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"mode", "module_id", "test_id", "syntax_ok", "functional_ok"}
    missing = required - set(rows[0]) if rows else required
    if missing:
        raise ValueError(f"{path} is not a raw ablation CSV; missing {sorted(missing)}")
    return rows


def exact_mcnemar_pvalue(discordant_forward: int, discordant_reverse: int) -> float:
    """Two-sided exact binomial test for paired binary outcomes."""
    total = discordant_forward + discordant_reverse
    if total == 0:
        return 1.0
    k = min(discordant_forward, discordant_reverse)
    probability = sum(math.comb(total, index) for index in range(k + 1)) / (2**total)
    return min(1.0, 2.0 * probability)


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return float("nan")
    index = (len(values) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def bootstrap_delta(before: list[int], after: list[int], samples: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    count = len(before)
    if count == 0:
        return float("nan"), float("nan")
    deltas: list[float] = []
    for _ in range(samples):
        indices = [rng.randrange(count) for _ in range(count)]
        deltas.append(sum(after[index] - before[index] for index in indices) / count)
    return percentile(deltas, 0.025), percentile(deltas, 0.975)


def paired_rows(rows: list[dict[str, str]], before_mode: str, after_mode: str) -> list[tuple[dict[str, str], dict[str, str]]]:
    by_case: dict[tuple[str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        if row.get("mode") in {before_mode, after_mode}:
            by_case[(row["module_id"], row["test_id"])][row["mode"]] = row
    return [(entry[before_mode], entry[after_mode]) for entry in by_case.values() if before_mode in entry and after_mode in entry]


def one_metric(
    label: str,
    pairs: list[tuple[dict[str, str], dict[str, str]]],
    metric: str,
    before_mode: str,
    after_mode: str,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, object]:
    before = [int(parse_bool(left[metric])) for left, _ in pairs]
    after = [int(parse_bool(right[metric])) for _, right in pairs]
    forward = sum(left == 0 and right == 1 for left, right in zip(before, after))
    reverse = sum(left == 1 and right == 0 for left, right in zip(before, after))
    ci_low, ci_high = bootstrap_delta(before, after, bootstrap_samples, seed)
    return {
        "run": label,
        "comparison": f"{after_mode} - {before_mode}",
        "metric": metric.removesuffix("_ok"),
        "paired_cases": len(pairs),
        "before_passes": sum(before),
        "after_passes": sum(after),
        "before_rate": sum(before) / len(before) if before else 0.0,
        "after_rate": sum(after) / len(after) if after else 0.0,
        "delta_rate": (sum(after) - sum(before)) / len(before) if before else 0.0,
        "improved_only": forward,
        "regressed_only": reverse,
        "mcnemar_exact_p": exact_mcnemar_pvalue(forward, reverse),
        "bootstrap_ci95_low": ci_low,
        "bootstrap_ci95_high": ci_high,
    }


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    lines = [
        "# V6.2 成对显著性检验",
        "",
        "每行只在同一模型、同一数据集、同一 case 内比较两种模式。`improved_only`/`regressed_only` 分别表示仅后者通过/仅前者通过的 case 数；p 值为双侧精确 McNemar 检验；置信区间为 case 级 paired bootstrap 95% CI。",
        "",
        "| Run | Comparison | Metric | Paired cases | Before | After | Delta | Improved / Regressed | McNemar p | Bootstrap 95% CI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {run} | {comparison} | {metric} | {paired_cases} | {before_passes} ({before_rate:.1%}) | "
            "{after_passes} ({after_rate:.1%}) | {delta_rate:+.1%} | {improved_only} / {regressed_only} | "
            "{mcnemar_exact_p:.4g} | [{bootstrap_ci95_low:+.1%}, {bootstrap_ci95_high:+.1%}] |".format(**row)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exact paired significance tests for raw V6.2 ablation CSV files.")
    parser.add_argument("--run", action="append", required=True, type=parse_run, help="Repeat LABEL=RAW_ABLATION_CSV.")
    parser.add_argument("--output-dir", required=True, help="Directory for paired_significance.csv/.md")
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260715)
    parser.add_argument(
        "--comparison",
        action="append",
        default=[],
        help="Optional BEFORE:AFTER comparison; repeatable. Defaults to origin:patch, patch:rag_skeleton, origin:rag_skeleton.",
    )
    args = parser.parse_args()

    comparisons = []
    for value in args.comparison:
        if ":" not in value:
            raise ValueError(f"Invalid --comparison {value}; expected BEFORE:AFTER")
        comparisons.append(tuple(value.split(":", 1)))
    if not comparisons:
        comparisons = list(DEFAULT_COMPARISONS)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_rows: list[dict[str, object]] = []
    for label, path in args.run:
        rows = read_rows(path)
        for before_mode, after_mode in comparisons:
            pairs = paired_rows(rows, before_mode, after_mode)
            if not pairs:
                print(f"[WARN] {label}: no paired rows for {before_mode}:{after_mode}")
                continue
            for metric_index, metric in enumerate(("syntax_ok", "functional_ok")):
                report_rows.append(
                    one_metric(
                        label,
                        pairs,
                        metric,
                        before_mode,
                        after_mode,
                        args.bootstrap_samples,
                        args.seed + metric_index,
                    )
                )

    csv_path = output_dir / "paired_significance.csv"
    md_path = output_dir / "paired_significance_zh.md"
    write_csv(report_rows, csv_path)
    write_markdown(report_rows, md_path)
    print(f"Paired significance rows: {len(report_rows)}")
    print(f"CSV: {csv_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
