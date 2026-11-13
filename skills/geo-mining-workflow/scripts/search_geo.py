#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO Dedicated Search & Multi-Dimensional Scoring Engine: search_geo.py
----------------------------------------------------------------------
Features:
1. Search NCBI GEO series by disease keywords.
2. Non-tumor keyword precheck (strict rejection upon match).
3. Automated Supplementary File auditing.
4. Objective 0~100 scoring (GEO-Score-100) across 5 dimensions:
   - Sample Size (25 pts)
   - Raw Data Completeness (30 pts)
   - Phenotype Metadata Richness (20 pts)
   - Platform Maturity (15 pts)
   - Publication Credibility (10 pts)
5. S / A / B / C Grade Assignment and Ranking.
6. Optional --apply flag to auto-lock the top 2 highest-scoring GSEs
   into a user-specified job spec file.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List

# Ensure utf-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import shutil
import httpx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from .unit1_geo_scout import (
        load_config,
        check_blacklist_on_input,
        fetch_geo_brief_metadata,
        audit_supplementary_files
    )
    from .dataset_scorer import evaluate_dataset_score
except (ImportError, ValueError):
    try:
        from unit1_geo_scout import (
            load_config,
            check_blacklist_on_input,
            fetch_geo_brief_metadata,
            audit_supplementary_files
        )
        from dataset_scorer import evaluate_dataset_score
    except ImportError:
        from units.unit1_geo_scout import (
            load_config,
            check_blacklist_on_input,
            fetch_geo_brief_metadata,
            audit_supplementary_files
        )
        from units.dataset_scorer import evaluate_dataset_score


def resolve_default_config_dir() -> str:
    candidates = [
        os.path.join(SCRIPT_DIR, "..", "config"),
        os.path.join(SCRIPT_DIR, "config"),
        os.path.join(os.getcwd(), "config"),
        os.path.join(os.getcwd(), "geo_mining_workflow", "config")
    ]
    for d in candidates:
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "dataset_scoring_rules.json")):
            return os.path.abspath(d)
    return os.path.abspath(os.path.join(SCRIPT_DIR, "..", "config"))


def check_and_print_ecosystem():
    has_reach = shutil.which("agent-reach") is not None
    has_bsk = any(shutil.which(cmd) is not None for cmd in ["bsk", "bsk.exe", "bsk.cmd", "bsk.ps1"])

    reach_status = "✅ 已就绪 (可抓取 GitHub 配套源码与学术社区讨论)" if has_reach else "⚪ 未安装 (建议: pip install agent-reach)"
    bsk_status = "✅ 已就绪 (可借调浏览器会话破壁收费文献/过验证码)" if has_bsk else "⚪ 未安装 (建议: irm https://raw.githubusercontent.com/Tencent/BrowserSkill/main/install.ps1 | iex)"

    print("\n" + "=" * 90)
    print("【生信调研黄金三角】伴生技能协同生态自检:")
    print(f"  • agent-reach:  {reach_status}")
    print(f"  • BrowserSkill: {bsk_status}")
    print("=" * 90)


def load_scoring_rules(config_dir: str) -> Dict[str, Any]:
    path = os.path.join(config_dir, "dataset_scoring_rules.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_eutils_with_retry(url: str, params: Dict[str, Any], headers: Dict[str, str], max_retries: int = 3, delay: float = 1.5) -> Dict[str, Any]:
    import time
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=25.0)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as je:
                    last_err = f"JSON decode error: {je}, body={resp.text[:200]}"
                    time.sleep(delay * attempt)
                    continue
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                time.sleep(delay * attempt)
                continue
        except Exception as e:
            last_err = e
            time.sleep(delay * attempt)
    raise RuntimeError(f"NCBI E-utilities 请求在重试 {max_retries} 次后失败: {last_err}")


def search_and_score(
    query_en: str,
    species: str = "Homo sapiens",
    disease_zh: str = "目标疾病",
    retmax: int = 15,
    config_dir: str = None,
    min_samples: int = 8
) -> List[Dict[str, Any]]:
    if not config_dir or not os.path.exists(config_dir):
        config_dir = resolve_default_config_dir()

    blacklist, thresholds = load_config(config_dir)
    scoring_rules = load_scoring_rules(config_dir)

    # 1. Non-tumor check
    dummy_job = {
        "base_request": {
            "disease_zh": disease_zh,
            "disease_en": query_en
        }
    }
    check_blacklist_on_input(dummy_job, blacklist)

    print(f"\n[GEO 智能检索与打分] 检索关键词: '{query_en}' | 物种: '{species}' | 上限: {retmax}...")
    term = f"{query_en}[Title/Summary] AND \"{species}\"[Organism] AND GSE[Filter]"
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    params = {
        "db": "gds",
        "term": term,
        "retmax": retmax,
        "retmode": "json",
        "tool": "geo_mining_workflow",
        "email": "geo_scout@local.dev"
    }

    try:
        search_data = fetch_eutils_with_retry(esearch_url, params, headers)
        idlist = search_data.get("esearchresult", {}).get("idlist", [])
        if not idlist:
            print("[GEO 检索] 未检索到匹配的 GSE 记录。")
            return []

        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        sum_params = {
            "db": "gds",
            "id": ",".join(idlist),
            "retmode": "json",
            "tool": "geo_mining_workflow",
            "email": "geo_scout@local.dev"
        }
        sum_data = fetch_eutils_with_retry(esummary_url, sum_params, headers)
        result = sum_data.get("result", {})
    except Exception as e:
        print(f"[GEO 检索失败] E-utilities 请求异常: {e}", file=sys.stderr)
        return []

    scored_candidates: List[Dict[str, Any]] = []

    for uid in idlist:
        rec = result.get(uid, {})
        acc = rec.get("accession", "")
        n_samples = rec.get("n_samples", 0)
        title = rec.get("title", "")

        if not acc.startswith("GSE"):
            continue

        try:
            meta = fetch_geo_brief_metadata(acc)
            meta["samples"] = n_samples
            meta["title"] = title

            # Calculate 0~100 Quality Score & Grade
            score_info = evaluate_dataset_score(meta, scoring_rules)
            is_valid_suppl, suppl_msg = audit_supplementary_files(meta)

            item = {
                "accession": acc,
                "samples": n_samples,
                "gpl": meta["gpl"],
                "data_type": meta["data_type"],
                "total_score": score_info["total_score"],
                "grade": score_info["grade"],
                "grade_title": score_info["grade_title"],
                "is_qualified": score_info["is_qualified"] and is_valid_suppl,
                "breakdown": score_info["breakdown"],
                "highlights": score_info["highlights"],
                "title": title,
                "supplementary_files": meta["supplementary_files"],
                "audit_message": suppl_msg
            }
            scored_candidates.append(item)
        except Exception as exc:
            pass

    # Sort descending by total score
    scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)

    # Print Formatted Ranking Table
    print("\n" + "=" * 125)
    print(f"{'综合排名':<5} | {'得分':<4} | {'评级':<8} | {'GSE 编号':<10} | {'样本量':<6} | {'平台 GPL':<10} | {'模态':<12} | {'细项拆解 (样/数/表/平/文)':<24} | {'数据集标题'}")
    print("-" * 125)

    for rank, c in enumerate(scored_candidates, 1):
        bd = c["breakdown"]
        bd_str = f"{bd['sample_size']:>2}/{bd['raw_data_quality']:>2}/{bd['phenotype_richness']:>2}/{bd['platform_maturity']:>2}/{bd['publication_credibility']:>2}"
        print(f"Top {rank:<2} | {c['total_score']:>3}分 | {c['grade_title']:<8} | {c['accession']:<10} | {c['samples']:<6} | {c['gpl']:<10} | {c['data_type']:<12} | {bd_str:<24} | {c['title'][:32]}...")

    print("=" * 125)
    s_and_a = [c for c in scored_candidates if c["grade"] in ["S", "A"]]
    print(f"打分汇总：共评估 {len(scored_candidates)} 个候选数据集，达到 S/A 级优质数据集 {len(s_and_a)} 个。\n")
    return scored_candidates


def export_evaluation_reports(
    candidates: List[Dict[str, Any]],
    query_en: str,
    disease_zh: str,
    species: str,
    export_dir: str = "eval_results"
):
    os.makedirs(export_dir, exist_ok=True)
    tsv_path = os.path.join(export_dir, "geo_evaluation_report.tsv")
    json_path = os.path.join(export_dir, "geo_evaluation_report.json")
    md_path = os.path.join(export_dir, "geo_evaluation_report.md")

    # 1. Export JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "disease_zh": disease_zh,
            "disease_en": query_en,
            "species": species,
            "total_candidates": len(candidates),
            "candidates": candidates
        }, f, ensure_ascii=False, indent=2)

    # 2. Export TSV
    tsv_headers = [
        "Rank", "GSE_Accession", "Quality_Score", "Quality_Grade", "Qualified_Status",
        "Sample_Size", "Platform_GPL", "Modality",
        "Sample_Score_25", "RawData_Score_30", "Phenotype_Score_20", "Platform_Score_15", "Credibility_Score_10",
        "Assessment_Highlights", "Raw_Supplementary_Files", "Title", "NCBI_GEO_URL"
    ]
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write("\t".join(tsv_headers) + "\n")
        for rank, c in enumerate(candidates, 1):
            bd = c["breakdown"]
            suppl_str = "; ".join(c.get("supplementary_files", []))
            row = [
                f"Top_{rank}",
                c["accession"],
                str(c["total_score"]),
                c["grade_title"],
                "QUALIFIED" if c["is_qualified"] else "DISQUALIFIED",
                str(c["samples"]),
                c["gpl"],
                c["data_type"],
                str(bd["sample_size"]),
                str(bd["raw_data_quality"]),
                str(bd["phenotype_richness"]),
                str(bd["platform_maturity"]),
                str(bd["publication_credibility"]),
                c["highlights"].replace("\t", " "),
                suppl_str.replace("\t", " "),
                c["title"].replace("\t", " "),
                f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={c['accession']}"
            ]
            f.write("\t".join(row) + "\n")

    # 3. Export Markdown
    s_and_a = [c for c in candidates if c["grade"] in ["S", "A"]]
    md_lines = [
        f"# GEO 候选数据集客观质量评估报告 (GEO-Score-100)",
        f"",
        f"- **目标疾病**：{disease_zh} ({query_en})",
        f"- **研究物种**：{species}",
        f"- **候选集总数**：{len(candidates)} 个",
        f"- **S/A 级优质数据集**：{len(s_and_a)} 个",
        f"",
        f"---",
        f"",
        f"## 一、 综合评级排行总表",
        f"",
        f"| 排名 | 得分 | 评级 | GSE 编号 | 样本量 | 测序平台 | 模态 | 细项拆解 (样/数/表/平/文) | 质检建议 |",
        f"| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    for rank, c in enumerate(candidates, 1):
        bd = c["breakdown"]
        bd_str = f"{bd['sample_size']}/{bd['raw_data_quality']}/{bd['phenotype_richness']}/{bd['platform_maturity']}/{bd['publication_credibility']}"
        md_lines.append(f"| Top {rank} | **{c['total_score']}** | {c['grade_title']} | [{c['accession']}](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={c['accession']}) | {c['samples']} | `{c['gpl']}` | {c['data_type']} | `{bd_str}` | {c['highlights']} |")

    md_lines.extend([
        f"",
        f"---",
        f"",
        f"## 二、 重点数据集详尽质检卡",
        f""
    ])

    for rank, c in enumerate(candidates, 1):
        bd = c["breakdown"]
        status_tag = "✅ 合格推荐" if c["is_qualified"] else "❌ 淘汰剔除"
        md_lines.extend([
            f"### Top {rank}：[{c['accession']}](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={c['accession']}) —— {c['grade_title']} ({status_tag})",
            f"- **数据集标题**：{c['title']}",
            f"- **总分与评级**：`{c['total_score']}分` ({c['grade']} 级) | **模态**：`{c['data_type']}` | **样本量**：`{c['samples']} 例` | **平台**：`{c['gpl']}`",
            f"- **五维评分拆解**：",
            f"  - 样本规模：`{bd['sample_size']} / 25分`",
            f"  - 原始数据完整度：`{bd['raw_data_quality']} / 30分`",
            f"  - 临床表型丰度：`{bd['phenotype_richness']} / 20分`",
            f"  - 平台规范与成熟度：`{bd['platform_maturity']} / 15分`",
            f"  - 文献与设计严谨度：`{bd['publication_credibility']} / 10分`",
            f"- **质检核心亮点/缺陷**：{c['highlights']}",
            f"- **补充文件清单**：{', '.join(c.get('supplementary_files', [])) or '无'}",
            f""
        ])

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"[评估报告已落盘]")
    print(f"  ├── TSV 清单: {tsv_path}")
    print(f"  ├── JSON 数据: {json_path}")
    print(f"  └── Markdown 报告: {md_path}")


def apply_candidates_to_spec(job_spec_path: str, disease_zh: str, query_en: str, train_gse: str, val_gse: str):
    if not os.path.exists(job_spec_path):
        print(f"[Warning] 目标规格书文件不存在: {job_spec_path}")
        return

    with open(job_spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    spec.setdefault("base_request", {})
    spec["base_request"]["disease_zh"] = disease_zh
    spec["base_request"]["disease_en"] = query_en
    spec["base_request"]["specified_train_gse"] = train_gse
    spec["base_request"]["specified_val_gse"] = val_gse

    with open(job_spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    print(f"[已自动择优锁定] 已将得分最高的训练集: {train_gse} 与 独立验证集: {val_gse} 写入 {job_spec_path}！")


def main():
    parser = argparse.ArgumentParser(description="Standalone GEO Dataset Search & Quality Scoring Tool")
    parser.add_argument("--query", required=True, help="疾病/表型英文检索关键词 (例如: 'Diabetic Nephropathy')")
    parser.add_argument("--disease_zh", default="目标疾病", help="疾病中文名")
    parser.add_argument("--species", default="Homo sapiens", help="目标物种 (默认 'Homo sapiens')")
    parser.add_argument("--retmax", type=int, default=15, help="最大返回数量 (默认 15)")
    parser.add_argument("--min_samples", type=int, default=8, help="硬性最低样本数 (默认 8)")
    parser.add_argument("--config_dir", default=resolve_default_config_dir(), help="规则与黑名单配置文件目录")
    parser.add_argument("--job", default=None, help="要回填的任务规格书路径，使用 --apply 时必填")
    parser.add_argument("--apply", action="store_true", help="若指定，自动将得分排名前2的S/A级数据集填入规格书")
    parser.add_argument("--export_dir", default="eval_results", help="质量评估清单与报告导出目录 (默认 eval_results)")
    parser.add_argument("--no_export", action="store_true", help="不自动导出 TSV/JSON/Markdown 报告")

    args = parser.parse_args()
    check_and_print_ecosystem()
    results = search_and_score(
        query_en=args.query,
        species=args.species,
        disease_zh=args.disease_zh,
        retmax=args.retmax,
        config_dir=args.config_dir,
        min_samples=args.min_samples
    )

    if not args.no_export and len(results) > 0:
        export_evaluation_reports(
            candidates=results,
            query_en=args.query,
            disease_zh=args.disease_zh,
            species=args.species,
            export_dir=args.export_dir
        )

    qualified = [r for r in results if r["is_qualified"]]
    if args.apply and not args.job:
        print("[Notice] --apply 需要同时提供 --job <规格书路径>，本次未执行回填。")
    elif args.apply and len(qualified) >= 2:
        apply_candidates_to_spec(
            job_spec_path=args.job,
            disease_zh=args.disease_zh,
            query_en=args.query,
            train_gse=qualified[0]["accession"],
            val_gse=qualified[1]["accession"]
        )
    elif args.apply and len(qualified) < 2:
        print(f"[Notice] 合格数据集少于 2 个 (仅 {len(qualified)} 个)，未执行自动写入。")


if __name__ == "__main__":
    main()
