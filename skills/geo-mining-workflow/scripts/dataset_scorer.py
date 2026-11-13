#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic Dataset Quality & Fitness Scorer (GEO-Score-100)
--------------------------------------------------------------
Calculates a 0~100 score across 5 objective dimensions:
1. Sample Size (0~25)
2. Raw Data Quality & Completeness (0~30)
3. Clinical Phenotype Metadata Richness (0~20)
4. Platform Maturity & Annotation Feasibility (0~15)
5. Publication & Design Credibility (0~10)
"""

import os
import json
import re
from typing import Dict, Any, Tuple


def evaluate_dataset_score(meta: Dict[str, Any], scoring_rules: Dict[str, Any]) -> Dict[str, Any]:
    dims = scoring_rules.get("dimensions", {})
    n_samples = meta.get("samples") or meta.get("n_samples") or 0
    dtype = meta.get("data_type", "bulk_rnaseq")
    suppl_files = meta.get("supplementary_files", [])
    suppl_str = " ".join(suppl_files).lower()
    full_text = f"{meta.get('title', '')} {meta.get('overall_design_text', '')} {meta.get('abstract_sample_text', '')}".lower()
    gpl = meta.get("gpl", "GPL_UNKNOWN")

    # 1. Sample Size Score (0 ~ 25)
    sample_rules = dims.get("sample_size", {}).get("tiers", [])
    score_samples = 0
    sample_desc = "样本量不足 (<8)"
    for tier in sample_rules:
        if n_samples >= tier["min_samples"]:
            score_samples = tier["score"]
            sample_desc = tier["desc"]
            break

    # 2. Raw Data Quality Score (0 ~ 30)
    raw_data_items = dims.get("raw_data_quality", {}).get("items", {})
    score_raw = 0
    raw_desc = "无有效原始文件"

    if dtype == "microarray":
        if "raw.tar" in suppl_str or ".cel" in suppl_str or ".idat" in suppl_str:
            score_raw = raw_data_items.get("microarray_raw_tar", 30)
            raw_desc = "含原始芯片 RAW.tar / CEL"
        elif len(suppl_files) > 0 or meta.get("has_series_matrix_processed", False):
            score_raw = raw_data_items.get("series_matrix_only", 15)
            raw_desc = "仅含 Series Matrix 归一化矩阵"

    elif dtype == "bulk_rnaseq":
        raw_count_keywords = ["raw", "count", "counts", "salmon", "htseq", "featurecounts"]
        if any(kw in suppl_str for kw in raw_count_keywords) or any(ext in suppl_str for ext in [".txt.gz", ".csv.gz", ".tsv.gz", ".xlsx", ".csv"]):
            score_raw = raw_data_items.get("bulk_raw_counts", 30)
            raw_desc = "含完整原始 Count 矩阵"
        elif any(kw in suppl_str for kw in ["fpkm", "tpm", "rpkm"]):
            score_raw = raw_data_items.get("bulk_normalized_matrix", 20)
            raw_desc = "含 FPKM/TPM 归一化矩阵"
        elif len(suppl_files) > 0:
            score_raw = raw_data_items.get("series_matrix_only", 15)
            raw_desc = "仅含基础表达矩阵"

    elif dtype == "scrna":
        if ("matrix.mtx" in suppl_str and "barcodes" in suppl_str) or ".h5" in suppl_str or ".h5ad" in suppl_str:
            score_raw = raw_data_items.get("scrna_mtx_h5", 30)
            raw_desc = "含 10x 完整三件套或 .h5/.h5ad"
        elif ".rds" in suppl_str or len(suppl_files) > 0:
            score_raw = 20
            raw_desc = "含 Seurat RDS 单细胞对象"

    elif dtype == "spatial":
        if ("tissue_positions" in suppl_str and "scalefactors" in suppl_str) or "spaceranger" in suppl_str:
            score_raw = raw_data_items.get("spatial_complete_ranger", 30)
            raw_desc = "含 Spaceranger 图像+空间坐标+表达三要素"
        elif len(suppl_files) > 0:
            score_raw = 15
            raw_desc = "仅含空间表达矩阵无对齐坐标"

    # 3. Clinical Phenotype Metadata Richness (0 ~ 20)
    pheno_items = dims.get("phenotype_richness", {}).get("items", {})
    score_pheno = pheno_items.get("base_binary_group", 8)  # 基底二分类

    # Demographics (Age / Sex / Gender / BMI)
    if re.search(r"\b(age|sex|gender|bmi|male|female)\b", full_text):
        score_pheno += pheno_items.get("has_demographics_age_sex", 5)

    # Clinical staging / Pathology biomarkers
    if re.search(r"\b(stage|grade|fibrosis|nas|steatosis|inflammation|cirrhosis|alt|ast|egfr|creatinine)\b", full_text):
        score_pheno += pheno_items.get("has_clinical_stage_biomarkers", 5)

    # Tissue biopsy specification
    if re.search(r"\b(biopsy|tissue|histolog|donor|resection)\b", full_text):
        score_pheno += pheno_items.get("has_tissue_biopsy_info", 2)

    score_pheno = min(score_pheno, dims.get("phenotype_richness", {}).get("weight", 20))

    # 4. Platform Maturity (0 ~ 15)
    plat_dim = dims.get("platform_maturity", {})
    majors = plat_dim.get("major_platforms", [])
    if any(gpl_kw.lower() in gpl.lower() for gpl_kw in majors):
        score_platform = plat_dim.get("major_score", 15)
        plat_desc = "主流高引用平台"
    elif gpl.startswith("GPL"):
        score_platform = plat_dim.get("standard_score", 10)
        plat_desc = "标准公共平台"
    else:
        score_platform = plat_dim.get("obscure_score", 5)
        plat_desc = "冷门/非标平台"

    # 5. Publication & Credibility (0 ~ 10)
    cred_dim = dims.get("publication_credibility", {})
    score_cred = 0
    if meta.get("pubmed_id") or "pubmed" in full_text or meta.get("overall_design_text"):
        score_cred += cred_dim.get("has_pubmed_id", 8)
    if meta.get("overall_design_text") and len(meta["overall_design_text"]) > 20:
        score_cred += cred_dim.get("has_overall_design", 2)
    score_cred = min(score_cred, cred_dim.get("weight", 10))

    # Hard veto: if sample < 8 or raw data == 0 -> capped at 45 (Grade C FAIL)
    total_score = score_samples + score_raw + score_pheno + score_platform + score_cred
    if n_samples < 8 or score_raw == 0:
        total_score = min(total_score, 45)

    # Determine Grade
    grades = scoring_rules.get("grade_thresholds", {})
    if total_score >= grades["S"]["min_score"]:
        grade = "S"
        grade_title = grades["S"]["title"]
    elif total_score >= grades["A"]["min_score"]:
        grade = "A"
        grade_title = grades["A"]["title"]
    elif total_score >= grades["B"]["min_score"]:
        grade = "B"
        grade_title = grades["B"]["title"]
    else:
        grade = "C"
        grade_title = grades["C"]["title"]

    return {
        "total_score": total_score,
        "grade": grade,
        "grade_title": grade_title,
        "is_qualified": total_score >= 50,
        "breakdown": {
            "sample_size": score_samples,
            "raw_data_quality": score_raw,
            "phenotype_richness": score_pheno,
            "platform_maturity": score_platform,
            "publication_credibility": score_cred
        },
        "highlights": f"{sample_desc}；{raw_desc}；{plat_desc}"
    }
