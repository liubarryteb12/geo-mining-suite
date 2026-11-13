# 生信工作台全契约需求单规格指南 (Workbench Manifest Specification)

本文档定义了生信分析工作台需求单的 JSON 数据结构，可作为自建系统的对接基准。
任何从上游挖掘（如 `geo-mining-workflow`）进入工作台建项的需求单，**必须 100% 符合本规范**，杜绝界面漏选、字段报错及参数降级。

---

## 一、 顶层 20 大契约模块总览

| 模块序号 | 顶层键名 (CamelCase / Snake_case) | 作用与消费方 | 漏填后果 / 常见痛点 |
| :---: | :--- | :--- | :--- |
| 1 | `manifest_version` / `schema_version` | 版本声明 (目前固定为 `"1.0"` / `"2.0"`) | 无法识别协议版本 |
| 2 | `id` / `projectId` / `project_id` | 项目唯一标识符（只允许字母、数字、下划线） | 触发 `项目 ID 非法` 拦截 |
| 3 | `lineId` / `line_id` / `seriesId` | 分析线枚举：`line1_bulk` / `line2_scrna` / `line3_spatial` | 触发 `line_id 缺失或不在三线枚举` 报错 |
| 4 | `basicInfo` / `basic_info` | 课题名称、简介、领域、疾病、物种、合规声明 | 前端表单基本信息栏显示为空 |
| 5 | `dataSource` / `data_source` | GSE号、GPL平台、样本总数、角色、组织来源 | 触发 `样本总数与各数据集不符` 或无法预下载 |
| 6 | `groupingDesign` / `grouping_design` | 对照组与疾病组分组名、GSM 样本编号列表、对比对 | 触发 `样本编号格式非法（只接受GSM开头）` |
| 7 | `pipelineDag` / `pipeline_dag` | 包含 `order`、`stepId`、`mod_id` 的有序执行 DAG 队列 | **生信功能选择复选框全部为空，无法自动勾选** |
| 8 | `steps` / `modIds` / `mod_ids` | 便捷步骤字符串数组（向前向后兼容） | 兼容轻量级移动端 / Web 端反查 |
| 9 | `biologicalPriors` / `biological_priors` | 重点基因 `focusGenes`、敲除靶点 `targetKoGene` | **含虚拟敲除步骤却未提供靶基因，导致强行拦截** |
| 10 | `phenotypeModules` / `phenotype_modules` | 表型模块（如屏障功能、代谢重编程） | 缺失富集分析与打分的生物学背景注释 |
| 11 | `analysisCutoffs` / `analysis_cutoffs` | 阈值档位、`use_adj_p`、`adj_p_threshold`、`log2fc` | 无法判定显著差异基因红蓝着色 |
| 12 | `plotLayoutConfig` / `plot_layout_config` | 画幅比例 (`template_4x3` / `template_16x9`) | 出图版式异常错乱 |
| 13 | `experimentalDesign` / `experimental_design` | 是否配对设计、批次效应协变量 `covariates` | 无法执行同供体配对分析与批次矫正 |
| 14 | `validationGroupMapping` | 独立验证集样本配对映射表 | 外部验证步骤无法正确读取验证组标签 |
| 15 | `wgcnaConfig` / `wgcna_config` | WGCNA 软阈值、最小模块大小、剪切高度 | 无法自动构建加权共表达网络 |
| 16 | `references` (含 `path`, `name`, `size`) | 参考文献元数据与收件箱相对路径 | **前端文献列表被过滤丢弃显示为 0 篇** |
| 17 | `aclAndOutput` / `acl_and_output` | 成果交付格式 (`png_300dpi`, `tsv_tables`, etc.) | 导出报告缺少高清矢量图或 Rds 检查点 |
| 18 | `figure_templates` / `figure_tasks` | 图级模板容器 | 图模板选择器无法匹配候选图件 |
| 19 | `dataFiles` / `data_files` | 本地上传文件映射 | 自有数据导入模式路径丢失 |
| 20 | `notes` | 自由文本备注与课题背景补充 | 缺少非肿瘤合规与实验背景留档 |

---

## 二、 三线生信功能（Pipeline DAG）全选规范

为保证用户进入工作台界面的“模块 C · 分析线与步骤”时**所有功能均已自动高亮勾选**，必须按照以下标准步骤写入 `pipelineDag`：

### 1. Line 1 (Bulk RNA-seq / 芯片) · 15 步全量 DAG
```json
[
  { "order": 1, "stepId": "prep_matrix", "mod_id": "l1_qc_ingest" },
  { "order": 2, "stepId": "qc_matrix", "mod_id": "l1_qc_matrix" },
  { "order": 3, "stepId": "pca_matrix", "mod_id": "l1_pca_matrix" },
  { "order": 4, "stepId": "deg_limma", "mod_id": "l1_deg_limma" },
  { "order": 5, "stepId": "wgcna_modules", "mod_id": "l1_wgcna_modules" },
  { "order": 6, "stepId": "enrichment_bulk", "mod_id": "l1_enrich_bulk" },
  { "order": 7, "stepId": "enrichment_figures", "mod_id": "l1_enrich_figures" },
  { "order": 8, "stepId": "ppi_string", "mod_id": "l1_ppi_string" },
  { "order": 9, "stepId": "key_genes", "mod_id": "l1_key_genes" },
  { "order": 10, "stepId": "ml_model", "mod_id": "l1_ml_model" },
  { "order": 11, "stepId": "ml_hub_analysis", "mod_id": "l1_ml_hub" },
  { "order": 12, "stepId": "ml_diagnostics", "mod_id": "l1_ml_diag" },
  { "order": 13, "stepId": "external_validation", "mod_id": "l1_ext_val" },
  { "order": 14, "stepId": "cox_analysis", "mod_id": "l1_cox_analysis" },
  { "order": 15, "stepId": "bulk_figures", "mod_id": "l1_bulk_figures" }
]
```

### 2. Line 2 (单细胞 scRNA-seq) · 22 步全量 DAG
```json
[
  { "order": 1, "stepId": "ingest_counts", "mod_id": "l2_ingest_counts" },
  { "order": 2, "stepId": "qc_cells", "mod_id": "l2_qc_cells" },
  { "order": 3, "stepId": "normalize_hvg", "mod_id": "l2_normalize_hvg" },
  { "order": 4, "stepId": "integrate_harmony", "mod_id": "l2_integrate_harmony" },
  { "order": 5, "stepId": "cluster_umap", "mod_id": "l2_cluster_umap" },
  { "order": 6, "stepId": "annotate_celltypes", "mod_id": "l2_annotate_celltypes" },
  { "order": 7, "stepId": "scrna_composition", "mod_id": "l2_composition" },
  { "order": 8, "stepId": "deg_groups", "mod_id": "l2_deg_groups" },
  { "order": 9, "stepId": "subcluster", "mod_id": "l2_subcluster" },
  { "order": 10, "stepId": "enrichment", "mod_id": "l2_enrichment" },
  { "order": 11, "stepId": "enrichment_figures", "mod_id": "l2_enrich_figures" },
  { "order": 12, "stepId": "pseudotime", "mod_id": "l2_pseudotime" },
  { "order": 13, "stepId": "cell_communication", "mod_id": "l2_communication" },
  { "order": 14, "stepId": "gsva_pathways", "mod_id": "l2_gsva_pathways" },
  { "order": 15, "stepId": "scenic_tf", "mod_id": "l2_tf_scenic" },
  { "order": 16, "stepId": "scenic_figures", "mod_id": "l2_scenic_figures" },
  { "order": 17, "stepId": "tf_activity", "mod_id": "l2_tf_activity" },
  { "order": 18, "stepId": "virtual_knockout", "mod_id": "l2_ko_virtual" },
  { "order": 19, "stepId": "summarize_dr", "mod_id": "l2_summarize_dr" },
  { "order": 20, "stepId": "target_gene_localization", "mod_id": "l2_target_localization" },
  { "order": 21, "stepId": "dr_post_analysis", "mod_id": "l2_dr_post" },
  { "order": 22, "stepId": "scrna_figures", "mod_id": "l2_figures_scrna" }
]
```

### 3. Line 3 (Visium 空间转录组) · 17 步标准 DAG (含虚拟扰动) / 15 步无偏探索 DAG
- **标准闭环模式（17 步）**：包含 `spatial_knockout` 与 `dr_post_analysis`，必须指定具体的 `targetKoGene`（如已进入细胞转染验证的 `GENE_A`）。
- **无偏探索模式（15 步）**：若属于“不预设结论、从 5 个特征基因中筛选排位”的场景，必须移除 `spatial_knockout` 与 `dr_post_analysis` 两步，避免因缺少单一靶基因而被校验拦截。

---

## 三、 文件名命名与项目 ID 自动派生规则

工作台前端（`OnboardingView.tsx`）在导入文件时，通过以下正则自动提取文件名中的时间戳以派生项目 ID：
```javascript
const stamp = /(\d{4})-(\d{2})-(\d{2})_(\d{6})/.exec(file);
const derivedId = stamp ? `proj_${stamp[1]}${stamp[2]}${stamp[3]}_${stamp[4]}` : '';
```
- **合规文件名范例**：
  `2026-11-05_153500_L3_空间转录组探索需求.json`
- **自动派生效果**：进入页面后自动将项目 ID 填为 `proj_20261105_153500`，绝不会留空报错。
