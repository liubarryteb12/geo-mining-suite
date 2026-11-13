# 数据集文件夹命名与文件组织规约 (folder_naming_rules.md)

本规约严格参照生信分析流程工作台的原始数据规范（`reference/06.测试用原始数据/`）。

---

## 1. 文件夹命名规则 (Folder Naming Convention)

每个数据集的根目录必须严格遵循三段式命名：

$$\text{\{Line\}\_\{\text{Modality}\}\_\{\text{GSE\_ACCESSION}\}}$$

### 模态映射矩阵与推荐命名：

| 分析线 (Line) | 数据模态 (Modality) | 推荐文件夹命名格式 | 示例 |
| :--- | :--- | :--- | :--- |
| **Line 1 (L1)** | Bulk RNA-seq | `L1_Bulk_RNAseq_{GSE}` | `L1_Bulk_RNAseq_GSE245825` |
| **Line 1 (L1)** | 基因芯片 (Microarray) | `L1_Microarray_{GSE}` | `L1_Microarray_GSE42955` |
| **Line 1 (L1)** | 靶向/面板测序 (NanoString) | `L1_Targeted_NanoString_{GSE}` | `L1_Targeted_NanoString_GSE316126` |
| **Line 2 (L2)** | 单细胞/单核转录组 (sc/snRNA-seq) | `L2_scRNA_snRNAseq_{GSE}` | `L2_scRNA_snRNAseq_GSE185100` |
| **Line 3 (L3)** | 空间转录组 (Visium / ST) | `L3_Spatial_Visium_{GSE}` | `L3_Spatial_Visium_GSE218759` |

---

## 2. 目录内文件清单规范 (Directory File Inventory)

在生成的每个数据集目录下，必须包含以下标准文件：

```text
L1_Bulk_RNAseq_GSE245825/
├── GSE245825_series_matrix.txt.gz      # [必需] 系列矩阵与样本临床特征
├── GSE245825_family.soft.gz            # [必需] GEO 家族完整 SOFT 文件
├── GPL18573_family.soft.gz             # [必需] 对应测序/芯片平台注释 SOFT
├── GSE245825_raw_counts.txt.gz         # [必需*] 原始测序表达矩阵或补充文件
├── grouping.txt                        # [推荐] 样本 ID 与 分组名对照表
└── info.md                             # [必需] 标准化 5 章节数据集档案
```

---

## 3. RAW.tar 保护性安全阈值机制 (> 1GB 拦截规约)

> [!WARNING]
> **1GB 安全保护阈值规则**：
> - GEO 原始补充文件（特别是 `RAW.tar`）常包含几十例高分辨率芯片扫描图（.CEL）或单细胞测序原始 FASTQ/BAM，体积往往达数 GB 至几十 GB。
> - **默认行为**：当探测到 `RAW.tar`（或单一大文件）尺寸 **$\ge 1.0\text{ GB}$ (1,073,741,824 字节)** 时，**默认不自动下载该文件**。
> - **显式原因通知**：必须在终端、日志及 `info.md` 中醒目标注跳过原因及文件真实体积（例如：`RAW.tar 体积为 1.76 GB，超过 1GB 安全阈值，默认跳过以避免耗尽磁盘或网络超时`）。
> - **用户接管开关**：若用户明确需要拉取完整大文件，可通过添加参数 `--force-download-raw` 强制下载。
