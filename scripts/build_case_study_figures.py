#!/usr/bin/env python3
"""Build versioned code evidence figures for the case study section."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission" / "figures"


INK = "#111418"
MUTED = "#5C6670"
BORDER = "#C8D0D8"
PANEL = "#FFFFFF"
CODE_BG = "#F7F9FC"

BLUE = "#1F5EA8"
BLUE_BG = "#EAF2FF"
GREEN = "#167A3A"
GREEN_BG = "#EAF7EE"
RED = "#B23A3A"
RED_BG = "#FCECEC"
AMBER = "#8A6400"
AMBER_BG = "#FFF6D8"
PURPLE = "#6E4AA8"
PURPLE_BG = "#F1ECFA"


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=260, bbox_inches="tight")
    plt.close(fig)


def arrow(ax, x0, y0, x1, y1, color=BLUE) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x0, y0),
            (x1, y1),
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.4,
            color=color,
        )
    )


def pill(ax, x, y, text, edge, fill, width=None) -> None:
    width = width or max(0.12, 0.012 * len(text) + 0.035)
    box = FancyBboxPatch(
        (x, y),
        width,
        0.046,
        boxstyle="round,pad=0.006,rounding_size=0.018",
        linewidth=1.0,
        edgecolor=edge,
        facecolor=fill,
    )
    ax.add_patch(box)
    ax.text(
        x + width / 2,
        y + 0.023,
        text,
        ha="center",
        va="center",
        fontsize=8.4,
        color=edge,
        fontweight="bold",
    )


def code_panel(
    ax,
    x,
    y,
    w,
    h,
    title,
    subtitle,
    lines,
    highlights=(),
    highlight_color=AMBER_BG,
    title_color=INK,
) -> None:
    outer = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.006,rounding_size=0.012",
        linewidth=1.1,
        edgecolor=BORDER,
        facecolor=PANEL,
    )
    ax.add_patch(outer)
    ax.text(
        x + 0.014,
        y + h - 0.030,
        title,
        ha="left",
        va="top",
        fontsize=10.8,
        fontweight="bold",
        color=title_color,
    )
    code_x = x + 0.014
    code_y = y + 0.026
    code_w = w - 0.028
    code_h = h - 0.074
    ax.add_patch(Rectangle((code_x, code_y), code_w, code_h, facecolor=CODE_BG, edgecolor="#E3E8EF", linewidth=0.8))

    n = len(lines)
    line_h = code_h / max(n + 0.3, 1)
    top = code_y + code_h - 0.012
    for i, line in enumerate(lines, start=1):
        yy = top - i * line_h + line_h * 0.22
        if i in highlights:
            ax.add_patch(Rectangle((code_x + 0.004, yy - 0.004), code_w - 0.008, line_h * 0.82, facecolor=highlight_color, edgecolor="none"))
        ax.text(
            code_x + 0.010,
            yy + line_h * 0.12,
            f"{i:02d}",
            ha="left",
            va="center",
            fontsize=7.1,
            color="#6D7783",
            family="DejaVu Sans Mono",
        )
        ax.text(
            code_x + 0.044,
            yy + line_h * 0.12,
            line.replace("$", r"\$"),
            ha="left",
            va="center",
            fontsize=7.9,
            color=INK,
            family="DejaVu Sans Mono",
        )


def evidence_panel(ax, x, y, w, h, title, entries, color=BLUE) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        linewidth=1.1,
        edgecolor=color,
        facecolor="#FFFFFF",
    )
    ax.add_patch(box)
    ax.text(x + 0.014, y + h - 0.030, title, ha="left", va="top", fontsize=9.7, fontweight="bold", color=color)
    yy = y + h - 0.072
    for label, body in entries:
        ax.text(x + 0.014, yy, label, ha="left", va="top", fontsize=8.2, fontweight="bold", color=INK)
        yy -= 0.028
        wrapped = textwrap.wrap(body, width=31, break_long_words=False)
        for line in wrapped:
            ax.text(x + 0.018, yy, line, ha="left", va="top", fontsize=7.8, color=MUTED)
            yy -= 0.022
        yy -= 0.008


def figure_serial() -> None:
    fig, ax = plt.subplots(figsize=(10.2, 5.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    patch_lines = [
        "module signed_serial_multiplier_9_CLA(...);",
        "  parameter width = 9;",
        "  input wire clk, rst_n, en;",
        "  input wire [width-1:0] A, B;",
        "  output reg valid;",
        "  output reg [width*2:1] S;",
        "  wire [width*2:0] temp_carry;",
        "  reg [width*2:0] temp_carry_reg_next31;",
        "  reg [width*2:0] temp_carry_reg_next32;",
        "  ...",
        "  // module body remains incomplete",
    ]
    full_lines = [
        "module signed_serial_multiplier_9_CLA(...);",
        "  always @(posedge clk or negedge rst_n) begin",
        "    if (!rst_n) begin",
        "      valid <= 1'b0;",
        "      S <= {(width*2){1'b0}};",
        "    end else begin",
        "      valid <= en;",
        "      if (en)",
        "        S <= $signed(A) * $signed(B);",
        "    end",
        "  end",
        "endmodule",
    ]

    code_panel(ax, 0.035, 0.275, 0.435, 0.675, "Patch version, round 3", "", patch_lines, highlights=(7, 8, 9, 11), highlight_color=RED_BG, title_color=RED)
    code_panel(ax, 0.530, 0.275, 0.435, 0.675, "Complete workflow, round 0", "", full_lines, highlights=(2, 3, 5, 7, 9), highlight_color=GREEN_BG, title_color=GREEN)
    arrow(ax, 0.475, 0.595, 0.525, 0.595, BLUE)

    ax.add_patch(
        FancyBboxPatch(
            (0.035, 0.070),
            0.930,
            0.135,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            linewidth=1.1,
            edgecolor=BLUE,
            facecolor=BLUE_BG,
        )
    )
    ax.text(0.055, 0.171, "Repair pivot", fontsize=9.8, fontweight="bold", color=BLUE, ha="left", va="top")
    ax.text(
        0.055,
        0.135,
        "Feedback: incomplete body and invalid module item.  Retrieved serial multiplier rule and Skeleton.\nAction: regenerate the implementation body under the public interface.",
        fontsize=8.6,
        color=INK,
        ha="left",
        va="top",
    )
    pill(ax, 0.100, 0.222, "No executable body", RED, RED_BG, 0.190)
    pill(ax, 0.680, 0.222, "Bounded sequential repair", GREEN, GREEN_BG, 0.230)
    save(fig, "fig6_case_serial_multiplier")


def figure_pe_row() -> None:
    fig, ax = plt.subplots(figsize=(10.2, 5.85))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    patch_lines = [
        "module PE_row #(...)(...);",
        "  input  active_left[a_tile_row_size];",
        "  output active_right[a_tile_row_size];",
        "  ...",
        "  for (row = 0; row < rows; row++) begin",
        "    PE_row row_inst (",
        "      .clk(clk), .rst_n(rst_n),",
        "      .active_left(active_left[row]),",
        "      .active_right(active_right[row])",
        "    );",
        "  end",
        "endmodule",
    ]
    full_lines = [
        "module PE_row #(...)(...);",
        "  input  active_left[data_width-1:0];",
        "  output active_right[data_width-1:0];",
        "  wire [data_width*(N+1)-1:0] active_chain;",
        "  assign active_chain[0] = active_left;",
        "  for (col = 0; col < N; col++) begin",
        "    PE pe_inst (",
        "      .active_left(active_chain[col]),",
        "      .active_right(active_chain[col+1])",
        "    );",
        "  end",
        "  assign active_right = active_chain[N];",
    ]

    code_panel(ax, 0.035, 0.280, 0.435, 0.670, "Patch version, round 2", "", patch_lines, highlights=(2, 3, 5, 6), highlight_color=AMBER_BG, title_color=AMBER)
    code_panel(ax, 0.530, 0.280, 0.435, 0.670, "Complete workflow, round 0", "", full_lines, highlights=(4, 5, 7, 8, 9, 12), highlight_color=GREEN_BG, title_color=GREEN)
    arrow(ax, 0.475, 0.600, 0.525, 0.600, BLUE)

    ax.add_patch(
        FancyBboxPatch(
            (0.035, 0.070),
            0.930,
            0.138,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            linewidth=1.1,
            edgecolor=BLUE,
            facecolor=BLUE_BG,
        )
    )
    ax.text(0.055, 0.176, "Repair pivot", fontsize=9.8, fontweight="bold", color=BLUE, ha="left", va="top")
    ax.text(
        0.055,
        0.140,
        "Feedback: row behavior remains inconsistent after patching.  Skeleton: PE row contains PE cells, not another PE row.\nGate: preserve the top module, required ports, and row dataflow.",
        fontsize=8.6,
        color=INK,
        ha="left",
        va="top",
    )
    pill(ax, 0.115, 0.226, "Recursive row drift", AMBER, AMBER_BG, 0.190)
    pill(ax, 0.680, 0.226, "PE cell chain restored", GREEN, GREEN_BG, 0.210)
    save(fig, "fig7_case_pe_row")


def version_row(ax, y, case, patch_lines, full_lines, outcome, outcome_color) -> None:
    x = 0.030
    w = 0.940
    h = 0.210
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.006,rounding_size=0.010",
            linewidth=1.0,
            edgecolor=BORDER,
            facecolor=PANEL,
        )
    )

    cell_w = 0.445
    gap = 0.020
    ax.text(x + 0.014, y + h - 0.028, case, fontsize=9.4, fontweight="bold", ha="left", va="top", color=INK)
    pill(ax, x + w - 0.125, y + h - 0.050, outcome, outcome_color, "#FFFFFF", 0.110)

    def cell(xx, lines):
        ax.add_patch(Rectangle((xx, y + 0.020), cell_w, h - 0.075, facecolor=CODE_BG, edgecolor="#E3E8EF", linewidth=0.7))
        top = y + h - 0.060
        for j, line in enumerate(lines[:5]):
            ax.text(xx + 0.007, top - j * 0.025, line.replace("$", r"\$"), fontsize=7.8, family="DejaVu Sans Mono", ha="left", va="top", color=INK)

    px = x + 0.014
    fx = px + cell_w + gap
    cell(px, patch_lines)
    cell(fx, full_lines)


def figure_summary() -> None:
    fig, ax = plt.subplots(figsize=(11.4, 7.3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.045, 0.970, "Patch version", fontsize=9.8, fontweight="bold", ha="left", va="top", color=RED)
    ax.text(0.510, 0.970, "Complete workflow version", fontsize=9.8, fontweight="bold", ha="left", va="top", color=GREEN)

    version_row(
        ax,
        0.735,
        "Prefix adder, module2/test2",
        [
            "input wire [ width-1:0] b",
            "wire ( width-1:0] p4;",
            "wire wire cin0, cin1;",
            "assign p0 = a ^ u;",
        ],
        [
            "input wire [width-1:0] A, B,",
            "input wire cin,",
            "output wire [width-1:0] S,",
            "assign {cout, S}=A+B+cin;",
            "endmodule",
        ],
        "rescued",
        GREEN,
    )
    version_row(
        ax,
        0.500,
        "Serial multiplier, module20/test1",
        [
            "reg [width*2:0] temp_carry_next31;",
            "reg [width*2:0] temp_carry_next32;",
            "wire [width*2:0] temp_carry;",
            "// body incomplete",
        ],
        [
            "always @(posedge clk or negedge rst_n)",
            "if (!rst_n) S <= 0;",
            "else if (en)",
            "  S <= $signed(A) * $signed(B);",
        ],
        "rescued",
        GREEN,
    )
    version_row(
        ax,
        0.265,
        "PE row, module26/test1",
        [
            "for (row = 0; row < a_tile_row_size; row++)",
            "begin",
            "  PE_row row_inst (...);",
            "end",
        ],
        [
            "wire active_chain[N+1];",
            "assign active_chain[0] = active_left;",
            "for (col = 0; col < N; col++)",
            "  PE pe_inst (...);",
            "assign active_right = active_chain[N];",
        ],
        "rescued",
        GREEN,
    )
    version_row(
        ax,
        0.030,
        "Winograd transform, module22/test3",
        [
            "dout0 = din0 + din1 - din2 + din3;",
            "dout1 = din4 + din5 - din6 + din7;",
            "dout2 = din8 + din9 - din10 + din11;",
            "0/50 functional checks",
        ],
        [
            "dout0 = din0 + din1 - din2 + din3;",
            "dout1 = din4 + din5 - din6 + din7;",
            "dout2 = din8 + din9 - din10 + din11;",
            "0/50 functional checks",
        ],
        "boundary",
        RED,
    )

    save(fig, "fig8_case_study_summary")


def main() -> None:
    figure_serial()
    figure_pe_row()
    figure_summary()
    print(f"Saved case study figures to {OUT}")


if __name__ == "__main__":
    main()
