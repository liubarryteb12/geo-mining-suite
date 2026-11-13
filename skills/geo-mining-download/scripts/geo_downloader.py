#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo_downloader.py
-----------------
健壮流式下载引擎：
- 支持断点续传（HTTP Range Header）
- 支持分块流式落盘与实时进度打印
- 自动重试与指数退避（应对 NCBI 频控与网络抖动）
- 1GB 安全阈值强管控（>1GB 自动跳过并通知）
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

import time
import requests
from typing import Dict, Any, Optional, Callable

CHUNK_SIZE = 1024 * 512  # 512 KB
GB_THRESHOLD_BYTES = 1024 * 1024 * 1024  # 1.0 GB


def download_file(
    url: str,
    dest_path: str,
    is_raw_archive: bool = False,
    force_download_raw: bool = False,
    max_retries: int = 3,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    """
    下载单个远程文件，支持断点续传与大文件 1GB 拦截。
    返回 dict:
      {
        "status": "success" | "skipped_exceeds_1gb" | "skipped_exists" | "failed",
        "dest_path": str,
        "size_bytes": int,
        "size_mb": float,
        "size_gb": float,
        "message": str
      }
    """
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    filename = os.path.basename(dest_path)

    # 1. 先探查文件体积与可达性
    remote_size = None
    try:
        head_resp = requests.head(url, timeout=15, allow_redirects=True)
        if head_resp.status_code == 200:
            cl = head_resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                remote_size = int(cl)
    except Exception as e:
        pass

    size_mb = round(remote_size / (1024 * 1024), 2) if remote_size else 0
    size_gb = round(remote_size / (1024 * 1024 * 1024), 3) if remote_size else 0

    # 2. 检查 1GB 安全拦截规则
    if is_raw_archive and remote_size and remote_size >= GB_THRESHOLD_BYTES and not force_download_raw:
        reason_msg = (
            f"【安全拦截】文件 '{filename}' 体积为 {size_gb:.2f} GB ({size_mb} MB)，"
            f"已超出 1GB 默认下载阈值。为避免消耗过度流量与长时间阻塞，系统默认跳过此文件下载。\n"
            f"--> 若需强制拉取该原始大文件，请在命令中追加 --force-download-raw 参数。"
        )
        print(f"\n[WARN] {reason_msg}")
        return {
            "status": "skipped_exceeds_1gb",
            "dest_path": dest_path,
            "size_bytes": remote_size,
            "size_mb": size_mb,
            "size_gb": size_gb,
            "message": reason_msg
        }

    # 3. 检查本地是否已存在且完整
    if os.path.exists(dest_path) and remote_size:
        local_size = os.path.getsize(dest_path)
        if local_size == remote_size:
            print(f"[INFO] 本地已存在完整文件: {filename} ({size_mb} MB)，跳过重复下载。")
            return {
                "status": "skipped_exists",
                "dest_path": dest_path,
                "size_bytes": remote_size,
                "size_mb": size_mb,
                "size_gb": size_gb,
                "message": "文件已完整存在"
            }

    # 4. 执行多轮重试下载（支持 Range 断点续传）
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            downloaded = 0
            headers = {}
            mode = "wb"

            # 如果本地已有部分文件，尝试断点续传
            if os.path.exists(dest_path):
                existing_bytes = os.path.getsize(dest_path)
                if remote_size and existing_bytes < remote_size:
                    headers["Range"] = f"bytes={existing_bytes}-"
                    downloaded = existing_bytes
                    mode = "ab"

            print(f"[DOWNLOAD] 开始拉取: {filename} (尝试 {attempt}/{max_retries}, 大小: {size_mb} MB)...")

            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                if r.status_code not in [200, 206]:
                    raise RuntimeError(f"HTTP {r.status_code}: 无法获取文件 {url}")

                total_length = remote_size or int(r.headers.get("Content-Length", 0)) + downloaded
                last_print_time = time.time()

                with open(dest_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            # 每隔 1 秒或完成时刷新一次进度
                            now = time.time()
                            if now - last_print_time >= 1.0 or downloaded == total_length:
                                last_print_time = now
                                if total_length > 0:
                                    pct = (downloaded / total_length) * 100
                                    mb_done = downloaded / (1024 * 1024)
                                    mb_total = total_length / (1024 * 1024)
                                    sys.stdout.write(f"\r  --> [{filename}] 进度: {pct:.1f}% ({mb_done:.1f}/{mb_total:.1f} MB)")
                                    sys.stdout.flush()

            print(f"\n[SUCCESS] 下载完成: {filename} ({round(downloaded / (1024*1024), 2)} MB)")
            return {
                "status": "success",
                "dest_path": dest_path,
                "size_bytes": downloaded,
                "size_mb": round(downloaded / (1024 * 1024), 2),
                "size_gb": round(downloaded / (1024 * 1024 * 1024), 3),
                "message": "下载成功"
            }

        except Exception as e:
            print(f"\n[WARN] 下载异常 (尝试 {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(attempt * 2)
            else:
                return {
                    "status": "failed",
                    "dest_path": dest_path,
                    "size_bytes": 0,
                    "size_mb": 0,
                    "size_gb": 0,
                    "message": str(e)
                }

    return {
        "status": "failed",
        "dest_path": dest_path,
        "size_bytes": 0,
        "size_mb": 0,
        "size_gb": 0,
        "message": "超过最大重试次数"
    }
