#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo_inspector.py
----------------
GEO 数据集元数据嗅探、平台探针关系推导、远程文件清单与体积预检模块。
支持 E-utilities 文献自动反查与 RAW.tar 大文件预警判定。
"""

import re
import urllib.parse
from typing import Dict, Any, List, Optional
import requests

NCBI_BASE = "https://ftp.ncbi.nlm.nih.gov/geo"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

GB_THRESHOLD_BYTES = 1024 * 1024 * 1024  # 1.0 GB


def get_geo_prefix(acc: str) -> str:
    """
    计算 NCBI GEO 的三位 nnn 分区前缀
    例如:
      GSE245825 -> GSE245nnn
      GSE42955  -> GSE42nnn
      GSE89632  -> GSE89nnn
      GSE500    -> GSEnnn
      GPL18573  -> GPL18nnn
    """
    acc = acc.strip()
    prefix_type = acc[:3].upper()
    digits = acc[3:]
    if len(digits) <= 3:
        return f"{prefix_type}nnn"
    return f"{prefix_type}{digits[:-3]}nnn"


def probe_remote_file_size(url: str, timeout: int = 10) -> Optional[int]:
    """
    通过 HEAD 请求获取远程文件 Content-Length 字节数
    """
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                return int(cl)
        elif resp.status_code == 404:
            return None
    except Exception:
        pass
    return None


def fetch_pubmed_summary(pmid: str, timeout: int = 10) -> Dict[str, str]:
    """
    通过 NCBI E-utilities 抓取 PubMed 文章标题、期刊与发表年份
    """
    info = {"title": "未知文献", "journal": "未知期刊", "year": "未知年份"}
    if not pmid or not pmid.isdigit():
        return info
    try:
        url = f"{EUTILS_BASE}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            doc = data.get("result", {}).get(pmid, {})
            title = doc.get("title", "").strip().rstrip(".")
            journal = doc.get("source", "").strip()
            pubdate = doc.get("pubdate", "").strip()
            year_match = re.search(r"\b(19\d\d|20\d\d)\b", pubdate)
            year = year_match.group(1) if year_match else pubdate[:4]
            if title:
                info["title"] = title
            if journal:
                info["journal"] = journal
            if year:
                info["year"] = year
    except Exception:
        pass
    return info


def list_supplementary_files(gse: str, timeout: int = 10) -> List[Dict[str, Any]]:
    """
    抓取 GSE 对应 suppl/ 目录下的全部补充文件及其实际体积
    """
    gse_prefix = get_geo_prefix(gse)
    suppl_url = f"{NCBI_BASE}/series/{gse_prefix}/{gse}/suppl/"
    results = []
    try:
        resp = requests.get(suppl_url, timeout=timeout)
        if resp.status_code == 200:
            # 匹配网页中的 href 链接
            links = re.findall(r'href=[\"\']([^\"]+)[\"\']', resp.text)
            for link in links:
                if link.startswith("?") or link.startswith("/") or link == "../" or "vulnerability-disclosure-policy" in link:
                    continue
                file_url = urllib.parse.urljoin(suppl_url, link)
                size_bytes = probe_remote_file_size(file_url, timeout=timeout)
                results.append({
                    "name": link,
                    "url": file_url,
                    "size_bytes": size_bytes,
                    "size_mb": round(size_bytes / (1024 * 1024), 2) if size_bytes else None,
                    "size_gb": round(size_bytes / (1024 * 1024 * 1024), 3) if size_bytes else None,
                })
    except Exception:
        pass
    return results


def inspect_gse_plan(
    gse: str,
    gpl: Optional[str] = None,
    modality: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    全面探测 GSE 下载计划与文件清点：
    - Series Matrix URL 与大小
    - Family SOFT URL 与大小
    - GPL SOFT / Table URL 与大小
    - 补充原始文件分析（判断是否为 count 矩阵，或 RAW.tar）
    - 是否触发 > 1GB 拦截阈值
    """
    gse = gse.strip().upper()
    gse_prefix = get_geo_prefix(gse)

    # 1. 核心系列文件
    matrix_name = f"{gse}_series_matrix.txt.gz"
    matrix_url = f"{NCBI_BASE}/series/{gse_prefix}/{gse}/matrix/{matrix_name}"
    matrix_size = probe_remote_file_size(matrix_url, timeout)

    soft_name = f"{gse}_family.soft.gz"
    soft_url = f"{NCBI_BASE}/series/{gse_prefix}/{gse}/soft/{soft_name}"
    soft_size = probe_remote_file_size(soft_url, timeout)

    # 2. 平台文件
    gpl_info = None
    if gpl:
        gpl = gpl.strip().upper()
        gpl_prefix = get_geo_prefix(gpl)
        gpl_soft_name = f"{gpl}_family.soft.gz"
        gpl_soft_url = f"{NCBI_BASE}/platforms/{gpl_prefix}/{gpl}/soft/{gpl_soft_name}"
        gpl_soft_size = probe_remote_file_size(gpl_soft_url, timeout)

        gpl_annot_name = f"{gpl}.annot.gz"
        gpl_annot_url = f"{NCBI_BASE}/platforms/{gpl_prefix}/{gpl}/annot/{gpl_annot_name}"
        gpl_annot_size = probe_remote_file_size(gpl_annot_url, timeout)

        gpl_info = {
            "gpl": gpl,
            "soft": {
                "name": gpl_soft_name,
                "url": gpl_soft_url,
                "size_bytes": gpl_soft_size
            },
            "annot": {
                "name": gpl_annot_name,
                "url": gpl_annot_url,
                "size_bytes": gpl_annot_size
            }
        }

    # 3. 补充文件探测与 RAW.tar
    suppl_files = list_supplementary_files(gse, timeout)

    # 判定原始测序文件选型策略
    chosen_raw_file = None
    is_count_matrix = False

    # 若为 Bulk RNA-seq，优先寻找 count / raw 文本文件
    norm_modality = (modality or "").lower()
    if "bulk" in norm_modality or "rnaseq" in norm_modality or not norm_modality:
        for f in suppl_files:
            fn = f["name"].lower()
            if any(k in fn for k in ["count", "raw_count", "read_count"]) and any(fn.endswith(ext) for ext in [".txt.gz", ".tsv.gz", ".csv.gz"]):
                chosen_raw_file = f
                is_count_matrix = True
                break

    # 若未找到独立 count 矩阵，寻找 RAW.tar
    if not chosen_raw_file:
        for f in suppl_files:
            if f["name"].endswith("_RAW.tar") or f["name"].endswith(".tar"):
                chosen_raw_file = f
                break

    # 4. 判断 1GB 阈值
    exceeds_1gb = False
    raw_size_bytes = chosen_raw_file["size_bytes"] if chosen_raw_file else None
    if raw_size_bytes and raw_size_bytes >= GB_THRESHOLD_BYTES:
        exceeds_1gb = True

    return {
        "gse": gse,
        "gse_prefix": gse_prefix,
        "modality": modality,
        "matrix": {
            "name": matrix_name,
            "url": matrix_url,
            "size_bytes": matrix_size
        },
        "series_soft": {
            "name": soft_name,
            "url": soft_url,
            "size_bytes": soft_size
        },
        "gpl_info": gpl_info,
        "suppl_files": suppl_files,
        "chosen_raw_file": chosen_raw_file,
        "is_count_matrix": is_count_matrix,
        "raw_exceeds_1gb": exceeds_1gb,
        "raw_size_bytes": raw_size_bytes,
        "raw_size_mb": round(raw_size_bytes / (1024 * 1024), 2) if raw_size_bytes else None,
        "raw_size_gb": round(raw_size_bytes / (1024 * 1024 * 1024), 3) if raw_size_bytes else None,
    }


if __name__ == "__main__":
    import sys
    test_gse = sys.argv[1] if len(sys.argv) > 1 else "GSE245825"
    print(f"[*] Probing {test_gse}...")
    plan = inspect_gse_plan(test_gse, gpl="GPL18573", modality="bulk_rnaseq")
    print(f"Matrix: {plan['matrix']}")
    print(f"Chosen RAW: {plan['chosen_raw_file']}")
    print(f"Exceeds 1GB: {plan['raw_exceeds_1gb']} (Size: {plan['raw_size_mb']} MB / {plan['raw_size_gb']} GB)")
