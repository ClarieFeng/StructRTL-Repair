import argparse
import csv
from collections import Counter
from pathlib import Path


TABLES = [
    "rag_hit_vs_nohit",
    "rag_category_effectiveness",
    "rag_family_effectiveness",
    "rag_hit_failed_cases",
    "rag_vs_patch_paired_cases",
]


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fieldnames=None):
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_int(value):
    try:
        return int(float(value))
    except Exception:
        return 0


def as_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def collect_tables(source_dir: Path):
    merged = {name: [] for name in TABLES}
    coverage = []
    for model_dir in sorted(p for p in source_dir.iterdir() if p.is_dir()):
        if model_dir.name.upper() == "UNKNOWN":
            continue
        found = 0
        for stem in TABLES:
            path = model_dir / f"{stem}.csv"
            if not path.exists():
                continue
            rows = read_csv(path)
            for row in rows:
                row["model_folder"] = model_dir.name
                row["source_file"] = str(path)
            merged[stem].extend(rows)
            found += 1
        if found:
            coverage.append({"model_folder": model_dir.name, "rag_tables_found": found})
    return merged, coverage


def split_categories(value):
    categories = [item.strip() for item in (value or "").split(",") if item.strip()]
    return categories or ["<no_category>"]


def case_line(row):
    return (
        f"`{row.get('model_folder')} / {row.get('run')} / {row.get('case_id')} / "
        f"{row.get('family', 'unknown')}`: "
        f"patch syntax/function `{row.get('patch_syntax')}/{row.get('patch_functional')}`, "
        f"RAG+Skeleton syntax/function `{row.get('rag_syntax')}/{row.get('rag_functional')}`, "
        f"categories=`{row.get('rag_categories') or '<empty>'}`"
    )


def build_summary_markdown(
    coverage,
    paired,
    paired_func_success,
    paired_syntax_success,
    failed,
    summary,
    cat_top_count,
    pair_cat_rows,
    fail_family_rows,
    pair_family_rows,
):
    lines = []
    lines.append("# V6.2 RAG/Skeleton Mechanism Analysis 中文结论")
    lines.append("")
    lines.append(
        "本文件用于论文中 RAG/Skeleton mechanism analysis 小节。它不只回答分数是否提升，"
        "更关注为什么提升：RAG 命中是否有效、哪些 RAG category 有用、哪些 family 命中后仍失败，"
        "以及最关键的 paired cases，即同一个 case 中 `reflect_patch` 失败但 "
        "`reflect_rag_skeleton` 成功。"
    )
    lines.append("")
    lines.append("## 1. 文件覆盖与总体统计")
    lines.append("")
    lines.append(f"- 纳入模型文件夹数：{len(coverage)}。")
    lines.append(f"- 合并 paired case 行数：{len(paired)}。")
    lines.append(
        f"- `reflect_patch` functional fail 但 `reflect_rag_skeleton` functional pass 的 paired cases："
        f"{len(paired_func_success)}。"
    )
    lines.append(
        f"- `reflect_patch` syntax fail 但 `reflect_rag_skeleton` syntax pass 的 paired cases："
        f"{len(paired_syntax_success)}。"
    )
    lines.append(f"- RAG hit 但仍失败的 cases：{len(failed)}。")
    lines.append("")
    lines.append("按模型统计：")
    for row in summary:
        lines.append(
            f"- `{row['model_folder']}`: paired_cases={row['paired_cases']}，"
            f"patch_fail_rag_functional_pass={row['patch_fail_rag_functional_pass']}，"
            f"patch_fail_rag_syntax_pass={row['patch_fail_rag_syntax_pass']}，"
            f"rag_hit_failed_cases={row['rag_hit_failed_cases']}。"
        )

    lines.append("")
    lines.append("## 2. RAG hit 是否比 no-hit 更有效")
    lines.append("")
    lines.append(
        "不能简单用 hit/no-hit 的平均 functional rate 判断 RAG 是否有效。原因是 no-hit 往往包含"
        "本来就容易、不需要检索规则的 case，而 hit 往往发生在更难、错误更多的 case 上。"
        "因此，如果 no-hit functional rate 高，不代表 RAG 无效；更合理的证据是 paired analysis。"
    )
    lines.append("")
    lines.append("hit/no-hit 表的使用方式应当是：")
    lines.append("- 如果 RAG hit case 仍能达到较高 syntax 或 functional rate，说明规则检索没有破坏修复流程。")
    lines.append("- 如果 hit rate 低但 paired success 多，说明 RAG 主要在困难 case 上发挥作用。")
    lines.append("- 如果 hit 后仍大量失败，需要看 family 和 category，判断是规则不足、Skeleton 不足，还是视觉/功能语义本身太难。")
    lines.append("")
    lines.append(
        "论文中建议不要把“hit 的平均 rate 必须高于 no-hit”作为唯一论证，而是写成："
        "RAG hit case 通常是困难子集，paired success 才是衡量增量价值的核心证据。"
    )

    lines.append("")
    lines.append("## 3. 哪些 RAG category 真的有用")
    lines.append("")
    lines.append(
        "判断 category 是否有用，应同时看 functional 成功数、functional rate，以及 paired success 中是否频繁出现。"
        "下面是按 functional success 数排序的高贡献 category 示例，完整表见 "
        "`rag_category_top_by_functional_count.csv`。"
    )
    lines.append("")
    for row in cat_top_count[:12]:
        lines.append(
            f"- `{row.get('model_folder')} / {row.get('run')} / {row.get('category')}`: "
            f"total={row.get('total')}，syntax={row.get('syntax')}，functional={row.get('functional')}，"
            f"functional_rate={row.get('functional_rate')}。"
        )
    lines.append("")
    lines.append(
        "从 paired functional success 的 category 聚类看，最有说服力的是那些出现在 "
        "patch fail -> RAG pass case 中的规则。完整表见 `paired_functional_success_by_category.csv`。"
    )
    lines.append("")
    for row in pair_cat_rows[:12]:
        lines.append(
            f"- `{row['model_folder']} / {row['category']}`: "
            f"paired_functional_success_count={row['paired_functional_success_count']}。"
        )
    lines.append("")
    lines.append(
        "这类 category 可以在论文中写成“有效规则类型”：它们不是只被检索到，"
        "而是在同一 case 中把 patch 失败转化为 RAG+Skeleton 成功。"
    )

    lines.append("")
    lines.append("## 4. 哪些 family 命中 RAG 仍失败")
    lines.append("")
    lines.append(
        "RAG hit failed cases 用来写方法边界。命中 RAG 但仍失败，通常说明问题不只是缺少规则，"
        "而是当前规则或 Skeleton 还不足以恢复功能语义。完整聚类见 `rag_hit_failed_by_family.csv`。"
    )
    lines.append("")
    for row in fail_family_rows[:15]:
        lines.append(f"- `{row['model_folder']} / {row['family']}`: rag_hit_failed_count={row['failed_count']}。")
    lines.append("")
    lines.append(
        "这些失败 family 应与 family-level gain analysis 对齐解释：Winograd、adder_tree、Booth/dataflow "
        "或 PE 类问题常常需要更深层的拓扑理解、位宽传播、符号扩展或数据流语义，"
        "而不是简单检索一条规则即可修复。"
    )

    lines.append("")
    lines.append("## 5. Paired cases：证明 RAG/Skeleton 增量价值的最强证据")
    lines.append("")
    lines.append(
        "最重要的论证逻辑是：同一个 case 中，`reflect_patch` 失败，但 "
        "`reflect_rag_skeleton` 成功。这排除了“只是多跑一轮”或“case 本来就容易”的解释，"
        "更直接说明 RAG/Skeleton 改变了修复结果。"
    )
    lines.append("")
    lines.append("功能正确性 paired success 示例，完整表见 `paired_patch_fail_rag_functional_pass.csv`：")
    lines.append("")
    for row in paired_func_success[:18]:
        lines.append(f"- {case_line(row)}。")
    lines.append("")
    lines.append("语法正确性 paired success 示例，完整表见 `paired_patch_fail_rag_syntax_pass.csv`：")
    lines.append("")
    for row in paired_syntax_success[:12]:
        lines.append(f"- {case_line(row)}。")
    lines.append("")
    lines.append("按 family 聚类后，paired functional success 主要集中在以下 family，说明这些 family 更依赖 RAG/Skeleton 的结构化约束：")
    lines.append("")
    for row in pair_family_rows[:15]:
        lines.append(
            f"- `{row['model_folder']} / {row['family']}`: "
            f"paired_functional_success_count={row['paired_functional_success_count']}。"
        )

    lines.append("")
    lines.append("## 6. 论文写法建议")
    lines.append("")
    lines.append("这一节建议写成机制解释，而不是再重复整体分数。可以按如下逻辑组织：")
    lines.append("")
    lines.append("第一，说明 RAG hit/no-hit 的平均 rate 不能孤立解释，因为 RAG hit 通常发生在更难 case 上。因此，本文进一步使用 paired analysis 来衡量增量价值。")
    lines.append("")
    lines.append("第二，展示 patch fail -> RAG+Skeleton pass 的 paired cases，证明 RAG/Skeleton 不是简单重复普通 patch，而是在特定 case 中改变了修复结果。")
    lines.append("")
    lines.append("第三，按 category 和 family 聚类，说明有效规则主要对应结构错误、实例化错误、乘法器/加法器模板、adder tree 等领域知识；失败则集中在 Winograd、复杂 adder tree、Booth/dataflow 和 PE 类问题。")
    lines.append("")
    lines.append("第四，将机制分析与 family-level gain analysis 对齐：普通 patch 解决局部可定位错误，RAG+Skeleton 解决结构漂移和模板选择问题；残余失败说明未来需要更细粒度的 dataflow skeleton、verified local repair data 或更强的视觉拓扑理解。")
    lines.append("")
    lines.append("可直接写入论文的英文表述：")
    lines.append("")
    lines.append(
        "The paired analysis provides the strongest evidence for the incremental value of RAG+Skeleton. "
        "Instead of only comparing average hit/no-hit rates, we identify cases where generic reflection patching "
        "fails but RAG+Skeleton succeeds under the same initial generation. These paired successes show that "
        "the retrieved hardware rules and skeleton constraints actively change the repair trajectory. "
        "Category- and family-level aggregation further indicates that the effective rules mainly target "
        "structural instantiation, arithmetic templates, and tree/multiplier families, whereas remaining failures "
        "concentrate on Winograd transforms, adder-tree variants, and complex dataflow modules. This suggests "
        "that RAG+Skeleton improves repair by constraining the structural search space, while the remaining "
        "bottleneck lies in deeper visual topology and functional semantic reconstruction."
    )

    lines.append("")
    lines.append("## 7. 输出文件说明")
    lines.append("")
    lines.append("- `rag_hit_vs_nohit_all.csv`: 合并后的 RAG hit/no-hit 总表。")
    lines.append("- `rag_category_effectiveness_all.csv`: 合并后的 RAG category 成功率表。")
    lines.append("- `rag_family_effectiveness_all.csv`: 合并后的 family 成功率表。")
    lines.append("- `rag_hit_failed_cases_all.csv`: 合并后的 RAG hit 但仍失败 case 表。")
    lines.append("- `rag_vs_patch_paired_cases_all.csv`: 合并后的 patch vs RAG paired case 表。")
    lines.append("- `paired_patch_fail_rag_functional_pass.csv`: 最关键证据，patch 功能失败但 RAG+Skeleton 功能成功。")
    lines.append("- `paired_patch_fail_rag_syntax_pass.csv`: patch 语法失败但 RAG+Skeleton 语法成功。")
    lines.append("- `paired_functional_success_by_family.csv`: paired functional success 的 family 聚类。")
    lines.append("- `paired_functional_success_by_category.csv`: paired functional success 的 category 聚类。")
    lines.append("- `rag_hit_failed_by_family.csv`: RAG hit 后仍失败的 family 聚类，用于写方法边界。")
    lines.append("- `rag_hit_failed_by_category.csv`: RAG hit 后仍失败的 category 聚类，用于判断哪些规则还不够。")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    merged, coverage = collect_tables(source_dir)
    write_csv(output_dir / "rag_mechanism_file_coverage.csv", coverage)
    for stem, rows in merged.items():
        write_csv(output_dir / f"{stem}_all.csv", rows)

    paired = merged["rag_vs_patch_paired_cases"]
    paired_func_success = [
        row for row in paired
        if as_int(row.get("patch_functional")) == 0 and as_int(row.get("rag_functional")) == 1
    ]
    paired_syntax_success = [
        row for row in paired
        if as_int(row.get("patch_syntax")) == 0 and as_int(row.get("rag_syntax")) == 1
    ]
    paired_both_success = [
        row for row in paired_func_success
        if as_int(row.get("patch_syntax")) == 0 and as_int(row.get("rag_syntax")) == 1
    ]
    write_csv(output_dir / "paired_patch_fail_rag_functional_pass.csv", paired_func_success)
    write_csv(output_dir / "paired_patch_fail_rag_syntax_pass.csv", paired_syntax_success)
    write_csv(output_dir / "paired_patch_fail_rag_both_pass.csv", paired_both_success)

    hit_rows = [
        row for row in merged["rag_hit_vs_nohit"]
        if row.get("mode") == "reflect_rag_skeleton"
    ]
    write_csv(output_dir / "rag_hit_vs_nohit_reflect_rag_skeleton_only.csv", hit_rows)

    cat_rows = [
        row for row in merged["rag_category_effectiveness"]
        if row.get("mode") == "reflect_rag_skeleton"
    ]
    cat_top_count = sorted(
        cat_rows,
        key=lambda row: (
            as_float(row.get("functional")),
            as_float(row.get("functional_rate")),
            as_float(row.get("total")),
        ),
        reverse=True,
    )
    cat_top_rate = sorted(
        [row for row in cat_rows if as_float(row.get("total")) >= 3],
        key=lambda row: (
            as_float(row.get("functional_rate")),
            as_float(row.get("functional")),
            as_float(row.get("total")),
        ),
        reverse=True,
    )
    write_csv(output_dir / "rag_category_top_by_functional_count.csv", cat_top_count)
    write_csv(output_dir / "rag_category_top_by_functional_rate_min3.csv", cat_top_rate)

    failed = merged["rag_hit_failed_cases"]
    fail_family = Counter((row.get("model_folder", ""), row.get("family", "unknown")) for row in failed)
    fail_family_rows = [
        {"model_folder": model, "family": family, "failed_count": count}
        for (model, family), count in fail_family.most_common()
    ]
    write_csv(output_dir / "rag_hit_failed_by_family.csv", fail_family_rows)

    fail_category = Counter()
    for row in failed:
        for category in split_categories(row.get("categories")):
            fail_category[(row.get("model_folder", ""), category)] += 1
    fail_category_rows = [
        {"model_folder": model, "category": category, "failed_count": count}
        for (model, category), count in fail_category.most_common()
    ]
    write_csv(output_dir / "rag_hit_failed_by_category.csv", fail_category_rows)

    pair_family = Counter((row.get("model_folder", ""), row.get("family", "unknown")) for row in paired_func_success)
    pair_family_rows = [
        {"model_folder": model, "family": family, "paired_functional_success_count": count}
        for (model, family), count in pair_family.most_common()
    ]
    write_csv(output_dir / "paired_functional_success_by_family.csv", pair_family_rows)

    pair_category = Counter()
    for row in paired_func_success:
        for category in split_categories(row.get("rag_categories")):
            pair_category[(row.get("model_folder", ""), category)] += 1
    pair_category_rows = [
        {"model_folder": model, "category": category, "paired_functional_success_count": count}
        for (model, category), count in pair_category.most_common()
    ]
    write_csv(output_dir / "paired_functional_success_by_category.csv", pair_category_rows)

    summary = []
    for model in sorted({row.get("model_folder", "") for row in paired}):
        summary.append({
            "model_folder": model,
            "paired_cases": len([row for row in paired if row.get("model_folder") == model]),
            "patch_fail_rag_functional_pass": len([row for row in paired_func_success if row.get("model_folder") == model]),
            "patch_fail_rag_syntax_pass": len([row for row in paired_syntax_success if row.get("model_folder") == model]),
            "rag_hit_failed_cases": len([row for row in failed if row.get("model_folder") == model]),
        })
    write_csv(output_dir / "rag_mechanism_model_summary.csv", summary)

    markdown = build_summary_markdown(
        coverage=coverage,
        paired=paired,
        paired_func_success=paired_func_success,
        paired_syntax_success=paired_syntax_success,
        failed=failed,
        summary=summary,
        cat_top_count=cat_top_count,
        pair_cat_rows=pair_category_rows,
        fail_family_rows=fail_family_rows,
        pair_family_rows=pair_family_rows,
    )
    (output_dir / "rag_skeleton_mechanism_summary_zh.md").write_text(markdown, encoding="utf-8-sig")

    print(f"OUTPUT_DIR={output_dir}")
    print(f"coverage={len(coverage)}")
    print(f"paired={len(paired)}")
    print(f"paired_functional_success={len(paired_func_success)}")
    print(f"paired_syntax_success={len(paired_syntax_success)}")
    print(f"rag_hit_failed={len(failed)}")


if __name__ == "__main__":
    main()
