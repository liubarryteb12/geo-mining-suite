# 标准 info.md 报告模板规范 (info_template.md)

本模板为 `geo-mining-download` 生成 `info.md` 的唯一基准规范，完全复刻 `L1_Bulk_RNAseq_GSE245825/info.md` 样式。

---

```markdown
# {GSE} 数据集详细信息与样本分组对照表 (info.md)

## 一、 数据集基本信息

- **GEO Accession**：[{GSE}](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={GSE})
- **数据集标题**：{TITLE}
- **目标疾病**：{DISEASE}
- **研究物种**：*{SPECIES}*
- **测序平台**：`{GPL}` ({PLATFORM_TITLE})
- **数据模态**：{MODALITY_LABEL}
- **官方文献证实**：
  - **PubMed ID**：[{PMID}](https://pubmed.ncbi.nlm.nih.gov/{PMID}/)
  - **论文题目**：*{PUBMED_TITLE}*
  - **发表期刊**：*{JOURNAL}* ({PUB_YEAR})
- **标本组织来源**：
  - 组织/部位：{TISSUE_SUMMARY}

---

## 二、 实验设计与样本分组方案 (Overall Design)

{OVERALL_DESIGN_PARAGRAPH}

1. **疾病组 ({DISEASE_GROUP_NAME})**：共 **{N_DISEASE} 例**。样本 GSM 范围：`{GSM_START_DIS}` 至 `{GSM_END_DIS}`。
2. **对照组 ({CONTROL_GROUP_NAME})**：共 **{N_CONTROL} 例**。样本 GSM 范围：`{GSM_START_CTRL}` 至 `{GSM_END_CTRL}`。
3. **样本量总计**：**{N_TOTAL} 例**（疾病={N_DISEASE} 例，对照={N_CONTROL} 例），{CRITERIA_SATISFACTION_TEXT}。

---

## 三、 本地原始数据文件说明

在当前目录下已存储并校验的原始文件如下：
{LOCAL_FILES_BREAKDOWN}

---

## 四、 全量样本与分组映射明细表 ({N_TOTAL} 例)

| 矩阵列名 (Count Matrix) | GEO 样本号 (GSM) | 原始标题 (Title) | 疾病/生物学分组 | 取样组织部位 | 样本来源/说明 |
| :--- | :--- | :--- | :---: | :--- | :--- |
{SAMPLE_ROWS_MARKDOWN}

---

## 五、 推荐设计矩阵与下游分析参数

- **对比分组**：`{CONTROL_GROUP_NAME}` (n={N_CONTROL}) vs `{DISEASE_GROUP_NAME}` (n={N_DISEASE})
- **基线参考水平 (Reference Level)**：设置为 `{CONTROL_GROUP_NAME}`，使得差异表达结果中 $\log_2\text{FC} > 0$ 表示在 `{DISEASE_GROUP_NAME}` 状态下上调。
- **推荐设计公式**：`{DESIGN_FORMULA}`
- **差异检验阈值建议**：$|\log_2\text{FC}| \ge 1.0$，$\text{adj.P.Val} < 0.05$ (Benjamini-Hochberg 校正)。
```
