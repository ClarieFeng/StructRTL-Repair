# RQ1 多模态贡献实验汇总

## 研究问题与判据

RQ1 询问：当设计意图分布在文本接口与电路图中时，语义对齐的视觉证据在什么条件下、在多大程度上影响 Verilog 的语法与功能正确性，并且结构化 workflow 能否利用该证据。主要因果对照是同一 case 下 `original` 对 `shuffled_image`；`text_only` 与 `blank_image` 用于区分视觉通道缺失和无结构视觉占位。

## 条件级结果

| Stage | Model | Prompt | Mode | Visual | N | Syntax | Functional |
|---|---|---|---|---|---:|---:|---:|
| single_pass | qwen25_vl_7b | full_description | origin | blank_image | 81 | 17 (21.0%) | 2 (2.5%) |
| single_pass | qwen25_vl_7b | full_description | origin | original | 81 | 18 (22.2%) | 0 (0.0%) |
| single_pass | qwen25_vl_7b | full_description | origin | shuffled_image | 81 | 15 (18.5%) | 1 (1.2%) |
| single_pass | qwen25_vl_7b | full_description | origin | text_only | 81 | 19 (23.5%) | 0 (0.0%) |
| single_pass | qwen25_vl_7b | interface_contract | origin | blank_image | 81 | 47 (58.0%) | 4 (4.9%) |
| single_pass | qwen25_vl_7b | interface_contract | origin | original | 81 | 30 (37.0%) | 0 (0.0%) |
| single_pass | qwen25_vl_7b | interface_contract | origin | shuffled_image | 81 | 31 (38.3%) | 3 (3.7%) |
| single_pass | qwen25_vl_7b | interface_contract | origin | text_only | 81 | 49 (60.5%) | 3 (3.7%) |

## Original 相对视觉对照的配对效应

正的 Delta 表示原图优于对照。功能通过总数少于 5 时标记为 floor，不能据此否定或确认视觉贡献。

| Stage | Model | Prompt | Mode | Control | Metric | N | Original-only / Control-only | Delta | 95% CI | McNemar p | Note |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| single_pass | qwen25_vl_7b | full_description | origin | text_only | syntax | 81 | 11 / 12 | -1.2% | [-12.3%, 9.9%] | 1 |  |
| single_pass | qwen25_vl_7b | full_description | origin | text_only | functional | 81 | 0 / 0 | 0.0% | [0.0%, 0.0%] | 1 | floor |
| single_pass | qwen25_vl_7b | full_description | origin | blank_image | syntax | 81 | 14 / 13 | 1.2% | [-11.1%, 13.6%] | 1 |  |
| single_pass | qwen25_vl_7b | full_description | origin | blank_image | functional | 81 | 0 / 2 | -2.5% | [-6.2%, 0.0%] | 0.5 | floor |
| single_pass | qwen25_vl_7b | full_description | origin | shuffled_image | syntax | 81 | 13 / 10 | 3.7% | [-7.4%, 14.8%] | 0.6776 |  |
| single_pass | qwen25_vl_7b | full_description | origin | shuffled_image | functional | 81 | 0 / 1 | -1.2% | [-3.7%, 0.0%] | 1 | floor |
| single_pass | qwen25_vl_7b | interface_contract | origin | text_only | syntax | 81 | 8 / 27 | -23.5% | [-37.0%, -9.9%] | 0.001878 |  |
| single_pass | qwen25_vl_7b | interface_contract | origin | text_only | functional | 81 | 0 / 3 | -3.7% | [-8.6%, 0.0%] | 0.25 | floor |
| single_pass | qwen25_vl_7b | interface_contract | origin | blank_image | syntax | 81 | 6 / 23 | -21.0% | [-33.3%, -8.6%] | 0.002316 |  |
| single_pass | qwen25_vl_7b | interface_contract | origin | blank_image | functional | 81 | 0 / 4 | -4.9% | [-9.9%, -1.2%] | 0.125 | floor |
| single_pass | qwen25_vl_7b | interface_contract | origin | shuffled_image | syntax | 81 | 14 / 15 | -1.2% | [-14.8%, 12.3%] | 1 |  |
| single_pass | qwen25_vl_7b | interface_contract | origin | shuffled_image | functional | 81 | 0 / 3 | -3.7% | [-8.6%, 0.0%] | 0.25 | floor |

## Prompt 信息量与视觉效应的交互

下表使用差分中的差分：`(interface original - interface shuffled) - (full original - full shuffled)`。正值表示移除文本拓扑后，模型对对齐图像的依赖增强。

| Stage | Model | Mode | Metric | N | Interaction | 95% CI |
|---|---|---|---|---:|---:|---:|
| single_pass | qwen25_vl_7b | origin | syntax | 81 | -4.9% | [-21.0%, 9.9%] |
| single_pass | qwen25_vl_7b | origin | functional | 81 | -2.5% | [-6.2%, 0.0%] |

## 论文结论边界

1. 只有当 `original > shuffled_image` 且配对效应方向稳定时，才能主张模型利用了 case-aligned 的视觉结构；`original > text_only` 单独不足以排除图像 token 或提示格式效应。
2. full-description single-pass 若处于功能 floor，只能记为结果不确定，不能写成图像无效。interface-contract 与 workflow-level 对照用于提高识别能力。
3. 若 workflow 在 interface-contract 下仍表现出原图优势，说明闭环不仅依赖 Error Library 或模块名先验，而能利用视觉证据完成修复。
4. 若 RAG+Skeleton 缩小原图与 shuffled 的差距，应解释为结构知识补偿视觉缺失；不能反向宣称 workflow 更依赖图像。
5. 所有结论限定于本文的电路图输入、Benchmark1 和所测模型，不外推到波形图或 PPA 约束。
