---
name: geo-mining-workflow
description: >-
  NCBI GEO 数据集检索与五维客观质量评估（GEO-Score-100）。
  Use when 用户需要按疾病或表型检索 GEO 公共数据集；
  需要对候选 GSE 做 0 到 100 分量化评估（样本规模、原始数据、临床表型、平台成熟度、文献可信度）；
  需要执行单组不少于 4 例、总数不少于 8 例的硬性红线审查与非肿瘤黑名单过滤；
  或需要导出可直接进入下游下载与建项流程的 TSV、JSON、Markdown 评估清单。
metadata:
  version: "1.5.0"
  role: "GEO Dataset Scout and Quality Evaluator"
  downstream_download_skill: "geo-mining-download"
  downstream_bridge_skill: "geo-workbench-bridge"
  companion_skills:
    - name: "geo-mining-download"
      path: "../geo-mining-download"
      purpose: "规范化下载、目录构建、1GB 安全拦截、五章节 info.md 自动生成"
    - name: "geo-workbench-bridge"
      path: "../geo-workbench-bridge"
      purpose: "全契约需求单生成、步骤 DAG 装配、HTML 全景报告"
    - name: "agent-reach"
      repo: "https://github.com/Panniantong/agent-reach"
      purpose: "抓取作者配套 GitHub 代码与社区讨论，可选"
    - name: "BrowserSkill"
      repo: "https://github.com/Tencent/BrowserSkill"
      purpose: "借用已登录浏览器访问收费文献或接管人机验证，可选"
---

# GEO 数据集检索与质量评估 (geo-mining-workflow)

本技能负责流水线第一段：**从 NCBI GEO 找出值得做的数据集，并用确定性规则给出可复核的分数**。

设计原则：

- 规则驱动，所有扣分项都能追溯到元数据字段，不依赖主观印象。
- 先做硬性红线，再做分数排序，避免高分掩盖致命缺陷。
- 只读取公开元数据与补充文件清单，不下载表达矩阵，默认秒级返回。

## 评分模型 (GEO-Score-100)

| 维度 | 权重 | 判定基准 |
| :--- | :---: | :--- |
| 样本规模 | 25 | 60 例及以上 25 分；30 到 59 例 22 分；15 到 29 例 18 分；8 到 14 例 10 分；少于 8 例 0 分 |
| 原始数据 | 30 | 含 CEL、IDAT、raw counts、10x 三件套或 h5 得 30 分；仅 FPKM/TPM 得 20 分；仅 series matrix 得 15 分；无补充文件得 0 分 |
| 临床表型 | 20 | 对照与疾病二分类 8 分；年龄性别 BMI 加 5 分；分期或生化指标加 5 分；组织来源细节加 2 分 |
| 平台成熟度 | 15 | 主流平台 15 分；标准 GPL 10 分；冷门或非标平台 5 分 |
| 文献可信度 | 10 | 有 PubMed ID 得 8 分；有完整 Overall Design 得 2 分 |

硬性一票否决：总数少于 8 例，或原始数据项为 0 分，总分强制压到 45 分并判为 C 级。

分级：S 级 85 分及以上，A 级 70 到 84 分，B 级 55 到 69 分，C 级 55 分以下。

## 执行流程

1. 解析疾病关键词，先过非肿瘤黑名单，命中即拒绝并说明原因。
2. 调用 NCBI E-utilities 检索 GSE，拉取标题、摘要、样本数、平台、PubMed 关联。
3. 逐个审计 supplementary 文件清单，识别原始数据形态。
4. 按五维规则打分，应用红线压制，排序并标注分级。
5. 导出 Markdown 质检卡、TSV 长表、JSON 结构化字典。

## 命令行

脚本位于本技能目录下，可独立运行，无需项目根目录：

```bash
python scripts/search_geo.py \
  --query "Diabetic Nephropathy" \
  --disease_zh "糖尿病肾病" \
  --species "Homo sapiens" \
  --retmax 15 \
  --export_dir eval_results
```

常用参数：

| 参数 | 说明 |
| :--- | :--- |
| `--query` | 必填，英文疾病或表型关键词 |
| `--disease_zh` | 中文疾病名，用于报告标题与文件名 |
| `--species` | 默认 `Homo sapiens`，小鼠用 `Mus musculus` |
| `--retmax` | 候选数量，默认 15 |
| `--min_samples` | 最低样本数，默认 8 |
| `--export_dir` | 报告输出目录，默认 `eval_results` |
| `--config_dir` | 规则目录，默认自动定位本技能 `config/` |
| `--no_export` | 只打印结果，不落盘 |

输出三件套：

- `geo_evaluation_report.md`：按分数排序的质检卡，含推荐理由与风险提示。
- `geo_evaluation_report.tsv`：一行一个数据集，可直接进 Excel 或 R。
- `geo_evaluation_report.json`：全量字段，含 `gse`、`gpl`、`score`、`grade`、`sample_count`、`raw_data_level`，作为下游 `--report-json` 的输入。

## 与下游的衔接

第一步的 JSON 里每个候选都带 `accession` 与 `gpl`，第二步用 `--report-json <path> --top-rank N` 直接承接，不需要手工抄 GSE 号。

如果用户已经有明确 GSE，可以跳过本技能，直接进入 `geo-mining-download`。

## 可选协同

两项外部能力都是可选增强，缺失时自动降级，不阻断主流程：

- `agent-reach`：当元数据里出现作者 GitHub 链接时，抓取未上传 GEO 的细胞类型标注或分析脚本，作为表型丰度的补充证据。
- `BrowserSkill`：当需要核对收费期刊的补充表，或 NCBI 触发人机验证时，借用户已登录的浏览器完成读取。

降级行为：未安装时只在质检卡里保留原始链接，并提示用户自行核对，不改变分数。

## 边界

- 不下载表达矩阵与原始测序文件，那是 `geo-mining-download` 的职责。
- 不生成分析代码，不推断生物学结论。
- 分数是筛选辅助，不能替代人工读原文。
