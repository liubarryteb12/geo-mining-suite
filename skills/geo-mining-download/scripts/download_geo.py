#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_geo.py
---------------
GEO 数据集自动下载、规范重命名与元数据结构化建档调度 CLI。
严格遵循「生信分析流程工作台」数据集命名与 1GB 大文件安全防护规约。
"""

import os
import sys

# 兼容 Windows 默认 GBK 终端编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import argparse
from typing import Dict, Any, Optional

from geo_inspector import inspect_gse_plan, get_geo_prefix
from geo_downloader import download_file
from info_generator import parse_series_matrix, generate_info_and_grouping


MODALITY_MAPPING = {
    "bulk_rnaseq": ("Line 1 (L1)", "L1_Bulk_RNAseq", "Bulk RNA-seq"),
    "bulk": ("Line 1 (L1)", "L1_Bulk_RNAseq", "Bulk RNA-seq"),
    "rnaseq": ("Line 1 (L1)", "L1_Bulk_RNAseq", "Bulk RNA-seq"),
    "microarray": ("Line 1 (L1)", "L1_Microarray", "基因芯片 (Microarray)"),
    "array": ("Line 1 (L1)", "L1_Microarray", "基因芯片 (Microarray)"),
    "targeted": ("Line 1 (L1)", "L1_Targeted_NanoString", "Targeted / NanoString"),
    "nanostring": ("Line 1 (L1)", "L1_Targeted_NanoString", "Targeted / NanoString"),
    "scrna": ("Line 2 (L2)", "L2_scRNA_snRNAseq", "单细胞转录组 (sc/snRNA-seq)"),
    "snrna": ("Line 2 (L2)", "L2_scRNA_snRNAseq", "单细胞核转录组 (snRNA-seq)"),
    "spatial": ("Line 3 (L3)", "L3_Spatial_Visium", "原位空间转录组 (Visium)"),
    "visium": ("Line 3 (L3)", "L3_Spatial_Visium", "原位空间转录组 (Visium)"),
}


def derive_folder_name(gse: str, modality: str) -> str:
    """
    按照 {Line}_{Modality}_{GSE} 规则生成规范目录名
    """
    norm = modality.lower().strip()
    prefix = "L1_Bulk_RNAseq"
    for k, v in MODALITY_MAPPING.items():
        if k in norm:
            prefix = v[1]
            break
    return f"{prefix}_{gse.upper()}"


def get_modality_label(modality: str) -> str:
    norm = modality.lower().strip()
    for k, v in MODALITY_MAPPING.items():
        if k in norm:
            return v[2]
    return "Bulk RNA-seq"


def load_candidate_from_report(report_path: str, top_rank: Any) -> Dict[str, Any]:
    """
    从 geo_evaluation_report.json 中读取指定排位的候选集
    """
    if not os.path.exists(report_path):
        raise FileNotFoundError(f"找不到报告文件: {report_path}")

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 兼容两种上游格式：纯数组，或 {candidates: [...]} 包装对象
    if isinstance(data, dict):
        items = data.get("candidates") or data.get("results") or data.get("datasets") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []

    if not isinstance(items, list) or not items:
        raise ValueError("报告 JSON 为空或格式不正确")

    target_rank_str = str(top_rank).strip().lower()
    selected = None

    if target_rank_str.isdigit():
        index = int(target_rank_str) - 1
        if 0 <= index < len(items):
            selected = items[index]
    else:
        for item in items:
            if str(item.get("rank", "")).lower() == target_rank_str:
                selected = item
                break
        if selected is None and target_rank_str.startswith("top_"):
            suffix = target_rank_str.replace("top_", "", 1)
            if suffix.isdigit():
                index = int(suffix) - 1
                if 0 <= index < len(items):
                    selected = items[index]

    if selected is None:
        selected = items[0]

    gse = selected.get("gse") or selected.get("accession") or selected.get("GSE")
    if not gse:
        raise ValueError("候选集缺少 gse 或 accession 字段")

    return {
        "gse": str(gse).strip().upper(),
        "gpl": selected.get("gpl") or selected.get("GPL") or "",
        "modality": selected.get("modality") or selected.get("data_type") or "bulk_rnaseq",
        "title": selected.get("title", ""),
        "samples": selected.get("samples") or selected.get("sampleCount") or selected.get("sample_count"),
    }


def run_download(
    output_dir: str,
    gse: str,
    gpl: Optional[str] = None,
    modality: Optional[str] = None,
    disease_zh: str = "目标疾病",
    force_download_raw: bool = False,
    skip_raw: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    核心执行管线
    """
    gse = gse.strip().upper()
    modality = modality or "bulk_rnaseq"

    folder_name = derive_folder_name(gse, modality)
    target_dir = os.path.join(output_dir, folder_name)
    modality_label = get_modality_label(modality)

    print("=" * 70)
    print(f"[START] 开始执行 GEO 数据集下载与结构化建档任务")
    print(f"   - GEO Accession : {gse}")
    print(f"   - 目标分析线与模态: {modality_label}")
    print(f"   - 规范目标目录   : {folder_name}")
    print(f"   - 根输出路径     : {output_dir}")
    print(f"   - 完整存储路径   : {target_dir}")
    print(f"   - 强制下载大文件 : {force_download_raw}")
    print("=" * 70)

    # 1. 嗅探预检
    print(f"\n[*] 正在探测 NCBI 远程元数据与补充文件清单...")
    plan = inspect_gse_plan(gse, gpl=gpl, modality=modality)

    matrix_info = plan["matrix"]
    series_soft_info = plan["series_soft"]
    gpl_info = plan["gpl_info"]
    chosen_raw = plan["chosen_raw_file"]
    raw_exceeds_1gb = plan["raw_exceeds_1gb"]

    print(f"   [+] 矩阵文件  : {matrix_info['name']} ({round((matrix_info['size_bytes'] or 0)/1024, 1)} KB)")
    print(f"   [+] 家族 SOFT : {series_soft_info['name']} ({round((series_soft_info['size_bytes'] or 0)/1024, 1)} KB)")
    if gpl_info:
        print(f"   [+] 平台 SOFT : {gpl_info['soft']['name']} ({round((gpl_info['soft']['size_bytes'] or 0)/(1024*1024), 2)} MB)")

    if chosen_raw:
        print(f"   [+] 原始数据  : {chosen_raw['name']} ({chosen_raw['size_mb']} MB / {chosen_raw['size_gb']} GB)")
        if raw_exceeds_1gb:
            if force_download_raw:
                print(f"   [WARN] 注意: 原始文件超过 1GB，但用户已指定 --force-download-raw，将执行下载。")
            else:
                print(f"   [STOP] 安全保护触发: 文件超过 1GB ({chosen_raw['size_gb']} GB)，默认不予自动下载！将在 info.md 标注原因。")
    else:
        print(f"   [INFO] 未检测到独立原始 counts 或 RAW.tar 文件。")

    if dry_run:
        print("\n[DRY RUN] 预检完成，退出执行。")
        return {"status": "dry_run", "target_dir": target_dir, "plan": plan}

    os.makedirs(target_dir, exist_ok=True)
    download_results = {}

    # 2. 下载 Series Matrix
    matrix_dest = os.path.join(target_dir, matrix_info["name"])
    download_results["matrix"] = download_file(matrix_info["url"], matrix_dest)

    # 3. 下载 GSE Family SOFT
    soft_dest = os.path.join(target_dir, series_soft_info["name"])
    download_results["series_soft"] = download_file(series_soft_info["url"], soft_dest)

    # 4. 下载 GPL 平台 SOFT (若存在)
    if gpl_info and gpl_info["soft"]["url"]:
        gpl_dest = os.path.join(target_dir, gpl_info["soft"]["name"])
        download_results["gpl_soft"] = download_file(gpl_info["soft"]["url"], gpl_dest)

    # 5. 下载 原始补充文件 / RAW.tar
    if chosen_raw and not skip_raw:
        raw_dest = os.path.join(target_dir, chosen_raw["name"])
        is_tar = chosen_raw["name"].endswith(".tar")
        download_results["raw"] = download_file(
            chosen_raw["url"],
            raw_dest,
            is_raw_archive=is_tar,
            force_download_raw=force_download_raw
        )
    else:
        download_results["raw"] = None

    # 6. 解析 Series Matrix 并自动生成 info.md 与 grouping.txt
    print(f"\n[*] 正在解析元数据并生成 info.md 与 grouping.txt...")
    meta = parse_series_matrix(matrix_dest)
    meta["gse"] = gse
    if gpl:
        meta["platform_id"] = gpl

    # 若初始未指定 GPL，但从矩阵中自动发现了 platform_id，尝试拉取该平台 SOFT
    discovered_gpl = meta.get("platform_id")
    if discovered_gpl and not gpl_info:
        discovered_gpl = discovered_gpl.strip().upper()
        gpl_prefix = get_geo_prefix(discovered_gpl)
        gpl_soft_name = f"{discovered_gpl}_family.soft.gz"
        gpl_soft_url = f"https://ftp.ncbi.nlm.nih.gov/geo/platforms/{gpl_prefix}/{discovered_gpl}/soft/{gpl_soft_name}"
        gpl_dest = os.path.join(target_dir, gpl_soft_name)
        print(f"   [+] 矩阵自发现测序平台: {discovered_gpl}，正在拉取平台注释 SOFT...")
        download_results["gpl_soft"] = download_file(gpl_soft_url, gpl_dest)

    info_path, grouping_path = generate_info_and_grouping(
        target_dir=target_dir,
        meta=meta,
        plan=plan,
        download_results=download_results,
        disease_zh=disease_zh,
        modality_label=modality_label
    )

    print("\n" + "=" * 70)
    print("[SUCCESS] GEO 数据集下载与建档任务全部圆满完成！")
    print(f"  [+] 本地归档目录: {target_dir}")
    print(f"  [+] 数据集档案  : {info_path}")
    print(f"  [+] 样本分组表  : {grouping_path}")
    print("=" * 70)

    return {
        "status": "success",
        "target_dir": target_dir,
        "info_path": info_path,
        "grouping_path": grouping_path,
        "download_results": download_results
    }


def main():
    parser = argparse.ArgumentParser(
        description="geo-mining-download: NCBI GEO 数据集标准化下载与建档工具"
    )
    parser.add_argument(
        "--output-dir", "-o",
        required=True,
        help="【必需参数】数据集存放的根目录路径（请用户明确提供，严禁隐式写死）"
    )
    parser.add_argument(
        "--report-json",
        help="上游 geo-mining-workflow 产出的 geo_evaluation_report.json 路径"
    )
    parser.add_argument(
        "--top-rank",
        default="1",
        help="下载报告中的指定排行（如 1 或 Top_1，默认 1）"
    )
    parser.add_argument(
        "--gse",
        help="显式指定欲下载的 GSE Accession（如 GSE245825）"
    )
    parser.add_argument(
        "--gpl",
        help="显式指定平台号 GPL（如 GPL18573，可选）"
    )
    parser.add_argument(
        "--modality",
        default="bulk_rnaseq",
        help="测序模态: bulk_rnaseq, microarray, targeted, scrna, spatial（默认 bulk_rnaseq）"
    )
    parser.add_argument(
        "--disease-zh",
        default="目标疾病",
        help="目标疾病中文名称（用于 info.md 文档撰写）"
    )
    parser.add_argument(
        "--force-download-raw",
        action="store_true",
        help="若原始文件/RAW.tar 大于 1GB，强制执行下载（默认超过 1GB 则跳过并提醒）"
    )
    parser.add_argument(
        "--skip-raw",
        action="store_true",
        help="跳过原始补充测序数据下载，仅拉取矩阵与元数据"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅探查远程文件大小并打印下载计划，不执行实际下载"
    )

    args = parser.parse_args()

    # 1. 目标输出目录严格校验
    output_dir = os.path.abspath(args.output_dir.strip())

    # 2. 判定 GSE 来源
    gse = args.gse
    gpl = args.gpl
    modality = args.modality
    disease_zh = args.disease_zh

    if args.report_json:
        print(f"[*] 正在从上游报告 {args.report_json} 中提取候选集 (Rank: {args.top_rank})...")
        candidate = load_candidate_from_report(args.report_json, args.top_rank)
        gse = candidate.get("gse", gse)
        gpl = candidate.get("gpl", gpl)
        modality = candidate.get("modality", modality)
        title = candidate.get("title", "")
        print(f"   ✓ 匹配到候选集: {gse} (平台: {gpl}, 模态: {modality})")

    if not gse:
        print("[ERROR] 未指定 GSE 编号。请通过 --gse 指定或通过 --report-json 传入上游评估报告。")
        sys.exit(1)

    run_download(
        output_dir=output_dir,
        gse=gse,
        gpl=gpl,
        modality=modality,
        disease_zh=disease_zh,
        force_download_raw=args.force_download_raw,
        skip_raw=args.skip_raw,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
