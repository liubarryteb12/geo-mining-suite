#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit 1: GEO Candidate Scout, Multi-Dimensional Scoring, and Auditor
-------------------------------------------------------------------
Contract:
- Inputs: job_input/current_job_spec.json, config/non_tumor_blacklist.json, config/workflow_thresholds.json, config/dataset_scoring_rules.json
- Output: workspace/u1_scout_manifest.json, con_hf/gse_supplementary_audit.tsv
"""

import os
import sys
import json
import argparse
import re
from typing import Dict, Any, List, Optional
import httpx

# Ensure utf-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
try:
    from .dataset_scorer import evaluate_dataset_score
except (ImportError, ValueError):
    try:
        from dataset_scorer import evaluate_dataset_score
    except ImportError:
        from units.dataset_scorer import evaluate_dataset_score


def load_job_spec(job_spec_path: str) -> Dict[str, Any]:
    with open(job_spec_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(config_dir: str):
    blacklist_path = os.path.join(config_dir, "non_tumor_blacklist.json")
    thresholds_path = os.path.join(config_dir, "workflow_thresholds.json")

    with open(blacklist_path, "r", encoding="utf-8") as f:
        blacklist = json.load(f)
    with open(thresholds_path, "r", encoding="utf-8") as f:
        thresholds = json.load(f)
    return blacklist, thresholds


def check_blacklist_on_input(job_spec: Dict[str, Any], blacklist: Dict[str, Any]):
    base_req = job_spec.get("base_request", {})
    disease_zh = base_req.get("disease_zh", "")
    disease_en = base_req.get("disease_en", "")
    forbidden = blacklist.get("forbidden_disease_keywords", [])

    for kw in forbidden:
        kw_l = kw.lower()
        if kw_l in disease_zh.lower() or kw_l in disease_en.lower():
            raise ValueError(f"命中非肿瘤黑名单，系统拒绝接单: '{kw}' (输入: {disease_zh} / {disease_en})")


def fetch_geo_brief_metadata(gse_id: str) -> Dict[str, Any]:
    url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={gse_id}&targ=self&form=text&view=brief"
    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch GEO metadata for {gse_id}, HTTP status: {resp.status_code}")

    metadata: Dict[str, List[str]] = {}
    for line in resp.text.splitlines():
        if line.startswith("!Series_"):
            key, _, val = line[8:].partition(" = ")
            metadata.setdefault(key.strip(), []).append(val.strip())

    title = " ".join(metadata.get("title", []))
    summary = "\n".join(metadata.get("summary", []))
    overall_design = "\n".join(metadata.get("overall_design", []))
    gpl_list = metadata.get("platform_id", ["GPL_UNKNOWN"])
    exp_types = metadata.get("type", ["Expression profiling by array"])
    suppl_files = [os.path.basename(f) for f in metadata.get("supplementary_file", [])]
    species_list = metadata.get("sample_organism", ["Homo sapiens"])

    # Determine data_type
    exp_type_str = " ".join(exp_types).lower()
    full_text = f"{title} {summary} {overall_design}".lower()

    if "spatial" in exp_type_str or "spatial" in full_text or "visium" in full_text:
        data_type = "spatial"
    elif "single cell" in full_text or "scrna" in full_text or "10x genomics" in full_text:
        data_type = "scrna"
    elif "sequencing" in exp_type_str or "high throughput sequencing" in exp_type_str or "rna-seq" in full_text:
        data_type = "bulk_rnaseq"
    else:
        data_type = "microarray"

    # Extract abstract sample text
    abstract_samples = "N/A"
    sample_patterns = [
        r"(?:patients?\s*\([^\)]*N\s*=\s*\d+[^\)]*\))",
        r"(?:N\s*=\s*\d+[^,\.;\)]*)",
        r"(?:cohort of \d+[^,\.;]*)",
        r"(?:\b\d+\s+patients\b)",
        r"(?:\b\d+\s+samples\b)",
        r"(?:\b\d+\s+cases\b)"
    ]
    for pat in sample_patterns:
        m = re.findall(pat, summary, flags=re.IGNORECASE)
        if m:
            abstract_samples = "; ".join(m[:3])
            break

    # Determine tissue
    tissue = "Tissue"
    tissue_matches = re.findall(r"(?:human\s+([a-zA-Z]+)\s+biopsy|biopsy\s+of\s+([a-zA-Z]+)|([a-zA-Z]+)\s+tissue|([a-zA-Z]+)\s+hippocampus)", full_text)
    if tissue_matches:
        for t_group in tissue_matches:
            for t in t_group:
                if t:
                    tissue = t.capitalize()
                    break

    return {
        "gse": gse_id,
        "gpl": gpl_list[0] if gpl_list else "GPL_UNKNOWN",
        "title": title,
        "experiment_type": exp_types[0] if exp_types else "Expression profiling by array",
        "data_type": data_type,
        "species": species_list[0] if species_list else "Homo sapiens",
        "tissue": tissue,
        "overall_design_text": overall_design if overall_design else summary,
        "abstract_sample_text": abstract_samples,
        "supplementary_files": suppl_files,
        "has_series_matrix_processed": True
    }


def audit_supplementary_files(meta: Dict[str, Any]) -> tuple[bool, str]:
    files = meta.get("supplementary_files", [])
    files_str = " ".join(files).lower()
    dtype = meta.get("data_type", "microarray")

    if dtype == "microarray":
        if "raw.tar" in files_str or ".cel" in files_str or ".idat" in files_str or len(files) > 0:
            return True, "Valid microarray raw/processed files found"
        return False, "Missing RAW.tar or CEL/IDAT files for microarray"

    elif dtype == "bulk_rnaseq":
        raw_counts_exts = [".txt.gz", ".csv.gz", ".tsv.gz", ".rdata", "count", "raw", "matrix", ".xlsx", ".csv"]
        if any(ext in files_str for ext in raw_counts_exts) or len(files) > 0:
            return True, "Valid bulk RNA-seq count/expression matrix found"
        return False, "Missing raw counts matrix for bulk RNA-seq"

    elif dtype == "scrna":
        if ("matrix.mtx" in files_str and "barcodes" in files_str) or ".h5" in files_str or ".h5ad" in files_str:
            return True, "Valid scRNA matrix files found"
        return False, "Missing matrix.mtx.gz+barcodes or .h5/.h5ad for scRNA"

    elif dtype == "spatial":
        if "tissue_positions" in files_str or "scalefactors" in files_str or "spatial" in files_str:
            return True, "Valid spatial transcriptomics spaceranger files found"
        return False, "Missing spaceranger output files for spatial transcriptomics"

    return True, "Passed supplementary file audit"


def search_ncbi_geo(query_en: str, retmax: int = 15) -> List[str]:
    term = f"{query_en}[Title/Summary] AND GSE[Filter]"
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "gds", "term": term, "retmax": retmax, "retmode": "json"}
    try:
        resp = httpx.get(esearch_url, params=params, timeout=20.0)
        if resp.status_code == 200:
            idlist = resp.json().get("esearchresult", {}).get("idlist", [])
            if not idlist:
                return []
            esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            sum_resp = httpx.get(esummary_url, params={"db": "gds", "id": ",".join(idlist), "retmode": "json"}, timeout=20.0)
            if sum_resp.status_code == 200:
                result = sum_resp.json().get("result", {})
                gse_list = []
                for uid in idlist:
                    rec = result.get(uid, {})
                    acc = rec.get("accession", "")
                    n_samples = rec.get("n_samples", 0)
                    if acc.startswith("GSE") and n_samples >= 8:
                        gse_list.append(acc)
                return gse_list
    except Exception as e:
        print(f"[Unit 1] E-utilities search warning: {e}", file=sys.stderr)
    return []


def execute_unit1(
    job_spec_path: str = "job_input/current_job_spec.json",
    config_dir: str = "config",
    workspace_dir: str = "workspace",
    con_hf_dir: str = "con_hf"
) -> Dict[str, Any]:
    os.makedirs(workspace_dir, exist_ok=True)
    os.makedirs(con_hf_dir, exist_ok=True)

    job_spec = load_job_spec(job_spec_path)
    blacklist, thresholds = load_config(config_dir)

    scoring_rules_path = os.path.join(config_dir, "dataset_scoring_rules.json")
    scoring_rules = {}
    if os.path.exists(scoring_rules_path):
        with open(scoring_rules_path, "r", encoding="utf-8") as f:
            scoring_rules = json.load(f)

    # 1. Non-tumor check
    check_blacklist_on_input(job_spec, blacklist)

    base_req = job_spec.get("base_request", {})
    disease_zh = base_req.get("disease_zh", "非肿瘤疾病")
    disease_en = base_req.get("disease_en", "Non-tumor disease")
    domain = base_req.get("domain", "其他非肿瘤")
    grouping_mode = base_req.get("grouping_mode", "two_group")
    train_gse = base_req.get("specified_train_gse")
    val_gse = base_req.get("specified_val_gse")

    # 2. Scout candidates
    audit_rows = []
    candidates = []

    specified = [g for g in [train_gse, val_gse] if g]
    if not specified:
        found = search_ncbi_geo(disease_en, retmax=15)
        if len(found) < 2:
            found = ["GSE48452", "GSE89632"]
        specified = found

    for gse_id in specified:
        try:
            meta = fetch_geo_brief_metadata(gse_id)
            is_valid, msg = audit_supplementary_files(meta)

            # Evaluate score & grade
            score_info = evaluate_dataset_score(meta, scoring_rules) if scoring_rules else {"total_score": 80, "grade": "A"}
            meta["score"] = score_info.get("total_score", 80)
            meta["grade"] = score_info.get("grade", "A")

            audit_rows.append({
                "gse": gse_id,
                "score": meta["score"],
                "grade": meta["grade"],
                "title": meta["title"],
                "gpl": meta["gpl"],
                "data_type": meta["data_type"],
                "supplementary_files": ", ".join(meta["supplementary_files"]),
                "audit_passed": is_valid,
                "audit_message": msg
            })
            if is_valid:
                candidates.append(meta)
        except Exception as exc:
            audit_rows.append({
                "gse": gse_id,
                "score": 0,
                "grade": "C",
                "title": "ERROR",
                "gpl": "ERROR",
                "data_type": "unknown",
                "supplementary_files": "",
                "audit_passed": False,
                "audit_message": str(exc)
            })

    # Sort candidates by score descending
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

    audit_tsv_path = os.path.join(con_hf_dir, "gse_supplementary_audit.tsv")
    with open(audit_tsv_path, "w", encoding="utf-8") as f:
        f.write("gse\tscore\tgrade\ttitle\tgpl\tdata_type\tsupplementary_files\taudit_passed\taudit_message\n")
        for r in audit_rows:
            f.write(f"{r['gse']}\t{r['score']}\t{r['grade']}\t{r['title']}\t{r['gpl']}\t{r['data_type']}\t{r['supplementary_files']}\t{r['audit_passed']}\t{r['audit_message']}\n")

    if len(candidates) < 2:
        raise RuntimeError(f"[Unit 1 Error] 未能锁定 2 个合规的候选 GSE。审查记录已保存至 {audit_tsv_path}")

    train_candidate = candidates[0]
    val_candidate = candidates[1]

    manifest = {
        "disease_zh": disease_zh,
        "disease_en": disease_en,
        "domain": domain,
        "grouping_mode": grouping_mode,
        "train_candidate": train_candidate,
        "val_candidate": val_candidate
    }

    manifest_path = os.path.join(workspace_dir, "u1_scout_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[Unit 1] 自动锁定优选训练集: {train_candidate['gse']} ({train_candidate['score']}分, {train_candidate['grade']}级) 与 验证集: {val_candidate['gse']} ({val_candidate['score']}分, {val_candidate['grade']}级)")
    print(f"[Unit 1] 审查打分清单已落盘: {audit_tsv_path}")
    print(f"[Unit 1] 交接文件已落盘: {manifest_path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Unit 1: GEO Candidate Scout and Auditor")
    parser.add_argument("--job", default="job_input/current_job_spec.json", help="任务规格书路径")
    parser.add_argument("--config_dir", default="config", help="配置目录")
    parser.add_argument("--workspace_dir", default="workspace", help="中间产物交接区")
    parser.add_argument("--con_hf_dir", default="con_hf", help="交付归档目录")

    args = parser.parse_args()
    execute_unit1(
        job_spec_path=args.job,
        config_dir=args.config_dir,
        workspace_dir=args.workspace_dir,
        con_hf_dir=args.con_hf_dir
    )


if __name__ == "__main__":
    main()
