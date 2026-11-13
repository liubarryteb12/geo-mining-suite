---
name: geo-mining-download
description: >-
  NCBI GEO 数据集自动化下载、规范命名重构与五章节元数据建档（承接 geo-mining-workflow）。
  Use when 用户已筛选出目标 GSE，需要拉取 series_matrix、family.soft、GPL 平台注释与原始 counts；
  Use when 需要把 GEO 数据整理成 L1_Bulk_RNAseq、L2_scRNA_snRNAseq、L3_Spatial_Visium 标准目录；
  Use when 需要自动生成包含样本映射表与设计矩阵建议的 info.md 和 grouping.txt。
metadata:
  version: "1.1.0"
  role: "GEO Dataset Downloader and Structured Archival Engine"
  upstream_skill: "geo-mining-workflow"
  downstream_bridge_skill: "geo-workbench-bridge"
---

# GEO 数据下载与结构化建档 (geo-mining-download)

本技能负责流水线第二段：**把上游选中的 GSE 从 NCBI 拉下来，整理成人和下游流程都能直接用的目录**。

它解决三个具体问题：

1. 目录命名不统一，导致 L1、L2、L3 数据混在一起无法批量处理。
2. 只拿到表达矩阵，少了平台注释或临床字段，下游无法复现。
3. 大文件长时间挂起，磁盘和网络被拖死。

## 执行红线

### 1. 输出目录必须由用户明确提供

脚本没有默认下载目录，`--output-dir` 必填。Agent 在触发下载前必须先向用户确认目标根目录，不得自行写到临时目录。

### 2. 单个文件大于等于 1GB 默认拦截

GEO 的 `RAW.tar` 常见数 GB。默认行为是跳过并显式说明原因，同时在 `info.md` 里记录跳过项与恢复命令。

用户确认需要大文件时，加 `--force-download-raw`。

### 3. 只处理公开数据

不写入任何本地私有临床数据。若用户提供自有数据，走工作台上传通道，不走本技能。

## 目录规范

文件夹命名规则：

```text
{Line}_{Modality}_{GSE_ACCESSION}
```

| 模态 | 目录示例 |
| :--- | :--- |
| Bulk RNA-seq | `L1_Bulk_RNAseq_GSE245825` |
| 芯片 | `L1_Microarray_GSE12345` |
| 靶向或 NanoString | `L1_Targeted_NanoString_GSE12345` |
| 单细胞或单核 | `L2_scRNA_snRNAseq_GSE12345` |
| 空间转录组 | `L3_Spatial_Visium_GSE12345` |

目录内容：

```text
L1_Bulk_RNAseq_GSE245825/
├── GSE245825_series_matrix.txt.gz
├── GSE245825_family.soft.gz
├── GPL18573_family.soft.gz
├── GSE245825_raw_counts.txt.gz
├── grouping.txt
└── info.md
```

## 命令行

### 承接上游报告，下载排名第一的数据集

```bash
python scripts/download_geo.py \
  --output-dir "/data/geo" \
  --report-json eval_results/geo_evaluation_report.json \
  --top-rank 1 \
  --disease-zh "糖尿病肾病" \
  --dry-run
```

确认预检结果后去掉 `--dry-run` 正式执行。

### 指定单个数据集

```bash
python scripts/download_geo.py \
  --output-dir "/data/geo" \
  --gse GSE245825 \
  --gpl GPL18573 \
  --modality bulk_rnaseq \
  --disease-zh "示例疾病"
```

### 大文件与轻量模式

```bash
# 强制下载超过 1GB 的原始包
python scripts/download_geo.py --output-dir "/data/geo" --gse GSE233814 --modality spatial --force-download-raw

# 只拉矩阵与元数据
python scripts/download_geo.py --output-dir "/data/geo" --gse GSE233814 --skip-raw
```

参数说明：

| 参数 | 说明 |
| :--- | :--- |
| `--output-dir`, `-o` | 必填，下载根目录 |
| `--report-json` | 上游评估报告路径 |
| `--top-rank` | 取报告中的第几名，默认 1 |
| `--gse` | 显式指定 GSE，与 `--report-json` 二选一 |
| `--gpl` | 显式指定平台，缺省时从 SOFT 自动推断 |
| `--modality` | `bulk_rnaseq`、`microarray`、`targeted`、`scrna`、`spatial` |
| `--disease-zh` | 写入 info.md 的中文疾病名 |
| `--dry-run` | 只探查远程文件大小并打印计划 |
| `--skip-raw` | 跳过原始 counts 与 RAW 包 |
| `--force-download-raw` | 解除 1GB 拦截 |

## info.md 五个章节

1. 数据集基本信息：GSE、标题、疾病、物种、平台、模态、文献、组织来源。
2. 实验设计与分组：Overall Design 原文、组间样本数、GSM 范围、样本量是否达到单组 4 例与总数 8 例。
3. 本地文件说明：每个文件的大小与用途，大文件跳过原因与恢复命令。
4. 全量样本映射表：矩阵列名、GSM 号、原始标题、分组、组织部位。
5. 推荐设计矩阵：参考水平、`design = ~ Group` 公式、差异分析阈值建议。

## 下游衔接

下载完成后，目录本身不是最终产物。把 `info.md` 里的分组与 GSM 信息交给 `geo-workbench-bridge`，即可生成可导入分析工作台的需求单。

如果目标系统不使用本套件的目录规范，可以只使用本技能的下载与建档能力，把 `--output-dir` 指向你自己的目录结构。

## 边界

- 不做质量评估与排序，引用上游分数即可。
- 不做表达矩阵标准化与差异分析。
- 不替用户决定下载哪个数据集。
