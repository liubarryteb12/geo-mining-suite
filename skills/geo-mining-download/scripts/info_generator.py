#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
info_generator.py
-----------------
自动解析下载后的 Series Matrix、平台与元数据，
严格按生信工作台 5 章节规范渲染输出 info.md 与 grouping.txt。
"""

import os
import gzip
import re
from typing import Dict, Any, List, Tuple
from geo_inspector import fetch_pubmed_summary

CONTROL_KEYWORDS = ["control", "ctrl", "normal", "healthy", "sham", "naive", "baseline", "young", "c", "nc", "non-failing", "nf"]


def parse_series_matrix(matrix_path: str) -> Dict[str, Any]:
    """
    深度解析 series_matrix.txt.gz，提取基本信息、设计描述及每个样本的明细属性
    """
    meta = {
        "title": "",
        "gse": "",
        "pubmed_id": "",
        "summary": "",
        "overall_design": [],
        "platform_id": "",
        "organism": "Homo sapiens",
        "samples": []
    }

    if not os.path.exists(matrix_path):
        return meta

    titles = []
    gsms = []
    sources = []
    chars_dict = {}  # index -> list of chars
    organisms = []

    with gzip.open(matrix_path, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str.startswith("!"):
                if line_str.startswith('"ID_REF"') or line_str.startswith("ID_REF"):
                    break
                continue

            parts = [p.strip().strip('"') for p in line.strip().split("\t")]
            tag = parts[0]
            vals = parts[1:]

            if tag == "!Series_title" and vals:
                meta["title"] = vals[0]
            elif tag == "!Series_geo_accession" and vals:
                meta["gse"] = vals[0]
            elif tag == "!Series_pubmed_id" and vals:
                meta["pubmed_id"] = vals[0]
            elif tag == "!Series_summary" and vals:
                meta["summary"] += ("\n" + vals[0] if meta["summary"] else vals[0])
            elif tag == "!Series_overall_design" and vals:
                meta["overall_design"].append(vals[0])
            elif tag == "!Series_platform_id" and vals:
                meta["platform_id"] = vals[0]

            elif tag == "!Sample_title":
                titles = vals
            elif tag == "!Sample_geo_accession":
                gsms = vals
            elif tag == "!Sample_source_name_ch1":
                sources = vals
            elif tag.startswith("!Sample_characteristics_ch1"):
                for idx, c_val in enumerate(vals):
                    chars_dict.setdefault(idx, []).append(c_val)
            elif tag == "!Sample_organism_ch1" and vals:
                organisms = vals

    if organisms:
        meta["organism"] = organisms[0]

    # 装配解析样本对象
    n_samples = max(len(gsms), len(titles))
    for i in range(n_samples):
        gsm = gsms[i] if i < len(gsms) else f"GSM_UNKNOWN_{i+1}"
        title = titles[i] if i < len(titles) else f"Sample_{i+1}"
        source = sources[i] if i < len(sources) else ""
        c_list = chars_dict.get(i, [])

        meta["samples"].append({
            "gsm": gsm,
            "title": title,
            "source": source,
            "characteristics": c_list
        })

    # 检查整体设计中是否有重新比对或外部引用的样本清单（例如 PRJNA477855 / Ctrl_1 ~ Ctrl_12）
    re_analysed_samples = []
    design_full_text = "\n".join(meta["overall_design"])
    re_matches = re.findall(r"(Ctrl[_\s]\d+|Control[_\s]\d+|NF[_\s]\d+)\s+(GSM\d+)", design_full_text, re.IGNORECASE)
    existing_gsms = {s["gsm"] for s in meta["samples"]}
    for label, re_gsm in re_matches:
        if re_gsm not in existing_gsms:
            re_analysed_samples.append({
                "gsm": re_gsm,
                "title": label,
                "source": "外部基线重分析样本 (Re-analysed)",
                "characteristics": ["re-analysed: external control", "condition: Control"],
                "is_external": True
            })

    meta["external_reanalysed"] = re_analysed_samples
    return meta


def infer_group_and_tissue(sample: Dict[str, Any], default_disease: str = "Disease") -> Tuple[str, str, str]:
    """
    返回 (group_name, tissue_str, desc_str)
    """
    title = sample.get("title", "")
    source = sample.get("source", "")
    chars = " ; ".join(sample.get("characteristics", []))
    combined = f"{title} {source} {chars}".lower()

    # 1. 组织提取
    tissue = source if source else "未知部位"
    for c in sample.get("characteristics", []):
        if c.lower().startswith("tissue:") or c.lower().startswith("organ:") or c.lower().startswith("source:"):
            parts = c.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                tissue = parts[1].strip()
                break

    # 2. 判断对照 vs 疾病
    is_ctrl = False
    for kw in CONTROL_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", combined, re.IGNORECASE):
            is_ctrl = True
            break
        # 兼容标题形式如 Ctrl_1, con_2, C1
        if re.search(rf"^{re.escape(kw)}[_\-\d]", title, re.IGNORECASE):
            is_ctrl = True
            break

    if is_ctrl:
        group_name = "Control"
        desc = "正常/对照基线标本"
    else:
        group_name = default_disease
        desc = "临床/疾病模型标本"

    return group_name, tissue, desc


def read_count_matrix_columns(count_matrix_path: str) -> List[str]:
    """
    若存在原始 count 矩阵文件，尝试读取其第一行表头列名
    """
    if not os.path.exists(count_matrix_path):
        return []
    try:
        if count_matrix_path.endswith(".gz"):
            with gzip.open(count_matrix_path, "rt", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()
        else:
            with open(count_matrix_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()
        cols = [c.strip().strip('"') for c in first_line.split("\t") if c.strip()]
        # 如果第一列是 gene/symbol/ID 等，则跳过首列
        if cols and any(cols[0].lower() == k for k in ["gene", "symbol", "gene_id", "id", "ensembl", "probe"]):
            cols = cols[1:]
        return cols
    except Exception:
        return []


def generate_info_and_grouping(
    target_dir: str,
    meta: Dict[str, Any],
    plan: Dict[str, Any],
    download_results: Dict[str, Any],
    disease_zh: str = "目标疾病",
    modality_label: str = "Bulk RNA-seq"
) -> Tuple[str, str]:
    """
    合成标准 info.md 与 grouping.txt
    返回 (info_md_path, grouping_txt_path)
    """
    gse = meta.get("gse") or plan.get("gse", "GSE_UNKNOWN")
    title = meta.get("title") or plan.get("title", "未命名研究")
    gpl_plan = plan.get("gpl_info") or {}
    gpl = meta.get("platform_id") or gpl_plan.get("gpl") or "GPL_UNKNOWN"
    species = meta.get("organism", "Homo sapiens")
    pmid = meta.get("pubmed_id", "")

    # 获取文献摘要
    pubmed_info = fetch_pubmed_summary(pmid) if pmid else {"title": "文献待关联", "journal": "未索引", "year": "2026"}

    # 整合主样本与重分析外部样本
    all_samples = list(meta.get("samples", []))
    if meta.get("external_reanalysed"):
        all_samples.extend(meta["external_reanalysed"])

    # 检查本地 count 矩阵列名
    count_cols = []
    count_file_item = download_results.get("raw")
    if count_file_item and count_file_item.get("status") in ["success", "skipped_exists"]:
        count_file_path = count_file_item.get("dest_path")
        if count_file_path and count_file_path.endswith((".txt.gz", ".tsv.gz", ".csv.gz", ".txt", ".tsv", ".csv")):
            count_cols = read_count_matrix_columns(count_file_path)

    # 样本分组推断
    disease_group_code = "DCM" if "dcm" in title.lower() or "dilated cardiomyopathy" in title.lower() else "Disease"
    ctrl_samples = []
    dis_samples = []
    sample_rows = []

    grouping_lines = ["sample\tgroup"]

    for idx, s in enumerate(all_samples):
        group_name, tissue, desc = infer_group_and_tissue(s, default_disease=disease_group_code)
        gsm = s.get("gsm", "")
        s_title = s.get("title", "")

        # 映射矩阵列名：优先使用 count 矩阵的对应列名
        col_name = count_cols[idx] if idx < len(count_cols) else s_title

        if group_name == "Control":
            ctrl_samples.append(s)
        else:
            dis_samples.append(s)

        grouping_lines.append(f"{gsm}\t{group_name}")

        sample_rows.append(
            f"| **{col_name}** | `{gsm}` | {s_title} | **{group_name}** | {tissue} | {desc} |"
        )

    n_ctrl = len(ctrl_samples)
    n_dis = len(dis_samples)
    n_total = len(all_samples)

    # 质检标准判定
    if n_total >= 8 and n_ctrl >= 4 and n_dis >= 4:
        criteria_text = "完全满足 $N \\ge 8$ 且单组 $\\ge 4$ 的严格统计检验要求"
    else:
        criteria_text = f"总样本数 {n_total} 例 (对照 {n_ctrl} vs 疾病 {n_dis})，需注意组样本量统计效能"

    # GSM 范围
    gsm_ctrl_start = ctrl_samples[0]["gsm"] if ctrl_samples else "N/A"
    gsm_ctrl_end = ctrl_samples[-1]["gsm"] if ctrl_samples else "N/A"
    gsm_dis_start = dis_samples[0]["gsm"] if dis_samples else "N/A"
    gsm_dis_end = dis_samples[-1]["gsm"] if dis_samples else "N/A"

    # 设计段落
    design_str = "\n".join(meta.get("overall_design", []))
    if not design_str.strip():
        design_str = meta.get("summary", "本数据集针对疾病转录组重塑与特征分子表达开展差异与分子网络挖掘。")

    # 本地文件清单渲染
    local_files_breakdown = []
    for k, item in download_results.items():
        if not item:
            continue
        fn = os.path.basename(item.get("dest_path", ""))
        size_mb = item.get("size_mb", 0)
        status = item.get("status", "")
        if status in ["success", "skipped_exists"]:
            local_files_breakdown.append(f"- **`{fn}`**：已成功下载校验（体积约 {size_mb} MB）。")
        elif status == "skipped_exceeds_1gb":
            local_files_breakdown.append(
                f"- **`{fn}`**：\n"
                f"  > ⚠️ **大文件安全跳过说明**：该原始文件体积为 **{item.get('size_gb')} GB ({size_mb} MB)**，已超出 1GB 安全阈值，系统默认跳过自动拉取。\n"
                f"  > 如需分析该原始测序数据，请使用 `--force-download-raw` 重新运行命令拉取。"
            )
        elif status == "failed":
            local_files_breakdown.append(f"- **`{fn}`**：拉取失败 ({item.get('message')})。")

    local_files_str = "\n".join(local_files_breakdown) if local_files_breakdown else "- 暂无本地文件记录。"

    # 组装 info.md 内容
    info_md_content = f"""# {gse} 数据集详细信息与样本分组对照表 (info.md)

## 一、 数据集基本信息

- **GEO Accession**：[{gse}](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse})
- **数据集标题**：{title}
- **目标疾病**：{disease_zh}
- **研究物种**：*{species}*
- **测序平台**：`{gpl}`
- **数据模态**：{modality_label}
- **官方文献证实**：
  - **PubMed ID**：[{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)
  - **论文题目**：*{pubmed_info['title']}*
  - **发表期刊**：*{pubmed_info['journal']}* ({pubmed_info['year']})
- **标本组织来源**：
  - 取样与分析：涵盖疾病与基线对照组临床/活检标本。

---

## 二、 实验设计与样本分组方案 (Overall Design)

{design_str}

1. **疾病组 ({disease_group_code})**：共 **{n_dis} 例**。样本 GSM 范围：`{gsm_dis_start}` 至 `{gsm_dis_end}`。
2. **对照组 (Control)**：共 **{n_ctrl} 例**。样本 GSM 范围：`{gsm_ctrl_start}` 至 `{gsm_ctrl_end}`。
3. **样本量总计**：**{n_total} 例**（疾病={n_dis} 例，对照={n_ctrl} 例），{criteria_text}。

---

## 三、 本地原始数据文件说明

在当前目录下已存储并校验的原始文件如下：
{local_files_str}

---

## 四、 全量样本与分组映射明细表 ({n_total} 例)

| 矩阵列名 (Count Matrix) | GEO 样本号 (GSM) | 原始标题 (Title) | 疾病/生物学分组 | 取样组织部位 | 样本来源/说明 |
| :--- | :--- | :--- | :---: | :--- | :--- |
{chr(10).join(sample_rows)}

---

## 五、 推荐设计矩阵与下游分析参数

- **对比分组**：`Control` (n={n_ctrl}) vs `{disease_group_code}` (n={n_dis})
- **基线参考水平 (Reference Level)**：设置为 `Control`，使得差异表达结果中 $\\log_2\\text{{FC}} > 0$ 表示在 `{disease_group_code}` 状态下上调。
- **推荐设计公式**：`design = ~ Group`
- **差异检验阈值建议**：$|\\log_2\\text{{FC}}| \\ge 1.0$，$adj.P.Val < 0.05$ (Benjamini-Hochberg 校正)。
"""

    info_path = os.path.join(target_dir, "info.md")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write(info_md_content)

    grouping_path = os.path.join(target_dir, "grouping.txt")
    with open(grouping_path, "w", encoding="utf-8") as f:
        f.write("\n".join(grouping_lines) + "\n")

    return info_path, grouping_path
