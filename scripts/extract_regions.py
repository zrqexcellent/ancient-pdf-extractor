#!/usr/bin/env python3
"""
古籍研究著作PDF - 内容区域自动检测与裁剪脚本

从高分辨率渲染图中，通过像素级分析自动检测并裁剪内容区域。
专门处理"现代印刷排版 + 嵌入古代文书影印件"的混合版面。

依赖: pip install pypdfium2 Pillow numpy
"""

import numpy as np
from PIL import Image


def analyze_layout(img: Image.Image, gray_threshold: int = 180,
                   row_threshold: int = 50, col_threshold: int = 20) -> dict:
    """
    分析图片布局，检测所有文字区域。

    参数:
        img: PIL.Image 输入图片（建议灰度或RGB）
        gray_threshold: 灰度阈值，低于此值视为文字像素（0=全黑, 255=全白）
        row_threshold: 每行暗像素数超过此值则认为有文字
        col_threshold: 每列暗像素数超过此值则认为有文字

    返回:
        {
            "width": int, "height": int,
            "row_profile": list[int],
            "col_profile": list[int],
            "text_regions": [{"top", "bottom", "left", "right", "height", "width"}],
            "page_header": {"top", "bottom"} | None,
            "doc_images": [{"top", "bottom", "left", "right", "height", "width"}],
        }
    """
    arr = np.array(img.convert('L'))
    h, w = arr.shape
    text_mask = arr < gray_threshold
    row_counts = text_mask.sum(axis=1).tolist()
    col_counts = text_mask.sum(axis=0).tolist()

    in_text = False
    raw_regions = []
    for y, count in enumerate(row_counts):
        if count > row_threshold and not in_text:
            in_text = True
            region_start = y
        elif count <= row_threshold and in_text:
            in_text = False
            raw_regions.append((region_start, y))
    if in_text:
        raw_regions.append((region_start, h))

    merged = _merge_gaps(raw_regions, max_gap=30)

    text_regions = []
    for top, bottom in merged:
        if (bottom - top) < 30:
            continue
        region_mask = text_mask[top:bottom, :]
        col_counts_r = region_mask.sum(axis=0)

        in_col = False
        col_spans = []
        for x, cnt in enumerate(col_counts_r):
            if cnt > col_threshold and not in_col:
                in_col = True
                col_start = x
            elif cnt <= col_threshold and in_col:
                in_col = False
                col_spans.append((col_start, x))
        if in_col:
            col_spans.append((col_start, w))

        if col_spans:
            region_left = min(s for s, e in col_spans)
            region_right = max(e for s, e in col_spans)
        else:
            region_left, region_right = 0, w

        text_regions.append({
            "top": top, "bottom": bottom,
            "left": int(region_left), "right": int(region_right),
            "height": bottom - top, "width": region_right - region_left,
        })

    page_header = None
    doc_images = []
    normal_text = []

    for region in text_regions:
        if (region["width"] > w * 0.6 and
                region["height"] < h * 0.08 and
                region["top"] < h * 0.15 and
                (page_header is None or region["top"] < page_header["top"])):
            page_header = region
        elif region["height"] > h * 0.25:
            doc_images.append(region)
        else:
            normal_text.append(region)

    return {
        "width": w,
        "height": h,
        "row_profile": row_counts,
        "col_profile": col_counts,
        "text_regions": text_regions,
        "page_header": page_header,
        "doc_images": doc_images,
    }


def crop_with_buffer(img: Image.Image, region: dict, buffer: int = 30) -> Image.Image:
    """按区域裁剪图片，四周留buffer像素缓冲。"""
    left = max(0, region["left"] - buffer)
    top = max(0, region["top"] - buffer)
    right = min(img.width, region["right"] + buffer)
    bottom = min(img.height, region["bottom"] + buffer)
    return img.crop((left, top, right, bottom))


def find_gaps_between_regions(regions: list, min_gap: int = 50) -> list:
    """在连续区域之间找到显著间隙。返回 [(gap_y_start, gap_y_end, gap_size)]"""
    if len(regions) < 2:
        return []
    sorted_regions = sorted(regions, key=lambda r: r["top"])
    gaps = []
    for i in range(len(sorted_regions) - 1):
        gap_start = sorted_regions[i]["bottom"]
        gap_end = sorted_regions[i + 1]["top"]
        gap_size = gap_end - gap_start
        if gap_size >= min_gap:
            gaps.append((gap_start, gap_end, gap_size))
    return gaps


# ============================================================
# 分批渲染（解决大PDF内存问题）
# ============================================================

def render_page(pdf_path: str, page_idx: int, scale: float = 4.0) -> Image.Image:
    """
    渲染PDF的指定单页为PIL.Image。不保存文件，直接返回内存中的图片对象。

    适用于逐页处理场景：渲染一页 → 分析/裁剪 → 释放内存 → 处理下一页。
    """
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    bitmap = pdf[page_idx].render(scale=scale)
    return bitmap.to_pil()


def render_page_range(pdf_path: str, start: int, end: int,
                      scale: float = 4.0, output_dir: str = ".") -> list[str]:
    """
    渲染PDF的指定页范围 [start, end) 为PNG文件。

    参数:
        pdf_path: PDF文件路径
        start: 起始页索引（0-based）
        end: 结束页索引（不含），-1表示到最后一页
        scale: 渲染倍率
        output_dir: 输出目录

    返回:
        渲染后的图片路径列表
    """
    import pypdfium2 as pdfium
    import os

    os.makedirs(output_dir, exist_ok=True)
    pdf = pdfium.PdfDocument(pdf_path)
    total = len(pdf)
    if end < 0 or end > total:
        end = total

    paths = []
    for i in range(start, end):
        bitmap = pdf[i].render(scale=scale)
        img = bitmap.to_pil()
        path = os.path.join(output_dir, f"page_{i + 1:02d}.png")
        img.save(path)
        paths.append(path)

    return paths


def render_pdf_pages(pdf_path: str, scale: float = 4.0,
                     output_dir: str = ".") -> list[str]:
    """
    渲染全部页面（向后兼容）。小PDF可用，大PDF建议用 render_page_range 分批。
    """
    return render_page_range(pdf_path, 0, -1, scale, output_dir)


def get_page_count(pdf_path: str) -> int:
    """返回PDF总页数，无需加载全部页面。"""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    return len(pdf)


def get_batch_ranges(total_pages: int, batch_size: int = 10) -> list[tuple]:
    """
    将总页数分割为多个批次。每个批次不超过 batch_size 页。

    返回: [(start, end), ...]  其中 end 是不包含的上界
    示例: total=25, batch_size=10 → [(0,10), (10,20), (20,25)]
    """
    ranges = []
    for start in range(0, total_pages, batch_size):
        end = min(start + batch_size, total_pages)
        ranges.append((start, end))
    return ranges


# ============================================================
# 文字层诊断
# ============================================================

def detect_text_layer_quality(pdf_path: str, sample_pages: int = 2) -> dict:
    """
    快速检测PDF文字层的可靠性。

    返回:
        {"reliable": bool, "reason": str, "font_info": list[dict]}
    """
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    font_info = []

    for i in range(min(sample_pages, len(reader.pages))):
        page = reader.pages[i]
        resources = page.get("/Resources")
        if not resources:
            continue

        fonts = resources.get("/Font", {})
        for name, font_obj in fonts.items():
            info = {
                "page": i + 1,
                "name": name,
                "subtype": str(font_obj.get("/Subtype", "")),
                "base_font": str(font_obj.get("/BaseFont", "")),
                "encoding": str(font_obj.get("/Encoding", "")),
                "has_tounicode": "/ToUnicode" in font_obj,
            }
            font_info.append(info)

    has_tounicode = any(f["has_tounicode"] for f in font_info)
    all_no_tounicode = all(not f["has_tounicode"] for f in font_info) if font_info else True

    if all_no_tounicode and font_info:
        return {
            "reliable": False,
            "reason": "所有字体均无ToUnicode映射表，文字层与显示字形可能不对应",
            "font_info": font_info,
        }

    return {
        "reliable": has_tounicode,
        "reason": "文字层基本可用" if has_tounicode else "部分字体缺少ToUnicode映射",
        "font_info": font_info,
    }


def _merge_gaps(regions: list, max_gap: int = 30) -> list:
    if not regions:
        return []
    merged = [list(regions[0])]
    for start, end in regions[1:]:
        if start - merged[-1][1] <= max_gap:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]