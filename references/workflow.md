# 古籍研究著作PDF — 工作流详解

本文档是 `ancient-pdf-extractor` 技能的详细工作流参考。
当 SKILL.md 中的简要流程不足以覆盖复杂情况时，agent 应读取本文档。

## 目录

1. [完整工作流](#1-完整工作流)
2. [阶段一：PDF预检与文字层诊断](#2-阶段一pdf预检与文字层诊断)
3. [阶段二：结构分析](#3-阶段二结构分析)
4. [阶段三：OCR识别](#4-阶段三ocr识别)
5. [阶段四：文书图片提取](#5-阶段四文书图片提取)
6. [阶段五：质量校验](#6-阶段五质量校验)
7. [阶段六：交付物输出](#7-阶段六交付物输出)
8. [附录A：大PDF分批处理指南](#8-附录a大pdf分批处理指南)
9. [常见陷阱](#9-常见陷阱)
10. [经验教训](#10-经验教训)


## 1. 完整工作流

```
PDF输入 → 预检(文字层诊断+页数) → 结构分析(布局/页码/篇章)
  → OCR识别(方案选择) → 文书图片提取(像素级裁剪)
  → 质量校验(生僻字/形近字) → 交付物输出(Excel+图片)
```

每阶段的输出是下一阶段的输入。不要跳过预检阶段——文字层诊断结果直接决定OCR方案选择。


## 2. 阶段一：PDF预检与文字层诊断

### 2.1 快速信息提取

```python
from pypdf import PdfReader
from extract_regions import get_page_count, detect_text_layer_quality

# 获取总页数（无需加载全部页面）
total = get_page_count("input.pdf")
print(f"总页数: {total}")

# 快速文字量评估
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    text = page.extract_text()
    print(f"第{i+1}页文字长度: {len(text) if text else 0}")
```

### 2.2 文字层可靠性检测

**关键步骤，不可跳过。** 使用 `scripts/extract_regions.py` 中的 `detect_text_layer_quality()`:

```python
result = detect_text_layer_quality("input.pdf", sample_pages=2)
print(f"文字层可靠: {result['reliable']}")
print(f"原因: {result['reason']}")
for f in result['font_info']:
    print(f"  字体: {f['base_font']}, ToUnicode: {f['has_tounicode']}")
```

**判断规则：**

| 指标 | 判定 | OCR方案 |
|------|------|--------|
| 有ToUnicode + 文字正常 | 文字层可用 | 方案A: pypdf/pdfplumber直接提取 |
| 无ToUnicode映射表 | 文字层不可信 | 方案B: 视觉模型OCR（必须） |
| 有ToUnicode但大量乱码 | 编码损坏 | 方案B: 视觉模型OCR |

**经验：** 古籍扫描PDF、影印版PDF、OCR层PDF几乎都缺少ToUnicode映射表，
此时pypdf提取的文字层完全不可信（形近字错误率40-60%），必须使用视觉模型方案。

### 2.3 已知问题：PDF文字层的形近字灾难

当PDF缺少ToUnicode映射表时，pypdf/pdfplumber提取的文字会出现系统性形近字错误：

```
正确: 敦煌碑铭赞辑释    错误: 效理避铝赞辑释
正确: 游自勇            错误: 哥目男
正确: 右武卫大将军      错误: 石武卫大将车
正确: 莫高窟佛龛碑      错误: 莫高鼠佛第碑
正确: 法身常住          错误: 法身常住（少数正确的）
```

这些错误**不是随机噪声**，而是字形映射系统性的偏移，看起来像"另一个文本"。


## 3. 阶段二：结构分析

### 3.1 渲染预览

**小PDF（≤50页）：**

```python
from extract_regions import render_pdf_pages
pages = render_pdf_pages("input.pdf", scale=3.0, output_dir="./preview")
```

**大PDF（>50页）：** 仅预览前几页即可，不需要全部渲染。

```python
from extract_regions import render_page_range
pages = render_page_range("input.pdf", 0, 5, scale=3.0, output_dir="./preview")
```

### 3.2 逐页视觉分析

对**每一页**调用 `view_image`，明确记录：

- [ ] 左上角页码（原书页码）
- [ ] 页眉/书名（如有）
- [ ] 正文区域（标题、编号、正文内容）的位置和范围
- [ ] 文书图片数量（0/1/2张）和位置（上方/下方/全页）
- [ ] 校释内容（有/无）
- [ ] 页面类型：纯文字 / 文字+图片 / 纯图片 / 校释

**输出格式**（每页一条记录）：

```
第N页: 原书页码XX | 类型:正文+图片 | 标题:XXX | 编号:S.XXXX |
       图片:1张(下方) | 校释:无
```

### 3.3 篇章识别

根据标题和编号变化，划分PDF中的独立篇章：

```
篇1: 标题, 编号, 起止页码, 内容类型(正文+图片+校释)
篇2: ...
```

### 3.4 自动布局检测（辅助）

对纯文字页面，可用 `analyze_layout()` 快速定位文字区域：

```python
from extract_regions import analyze_layout
from PIL import Image
layout = analyze_layout(Image.open("preview_1.png"))
for r in layout["text_regions"]:
    print(f"区域: y={r['top']}~{r['bottom']} x={r['left']}~{r['right']}")


## 4. 阶段三：OCR识别

### 4.1 方案A：文字层直接提取（仅当文字层可靠时）

```python
import pdfplumber
with pdfplumber.open("input.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
```

**适用条件：** `detect_text_layer_quality()` 返回 `reliable=True`

### 4.2 方案B：视觉模型OCR（推荐，古籍PDF必选）

#### 步骤

1. **高分辨率渲染**（scale=4，约288DPI）：

**小PDF（≤10页）：**
```python
from extract_regions import render_pdf_pages
pages = render_pdf_pages("input.pdf", scale=4.0, output_dir="./hd_pages")
```

**大PDF（>10页）：** 使用分批渲染（详见[附录A](#8-附录a大pdf分批处理指南)）。

2. **逐页视觉识别**，prompt模板：

```
请完整、逐字逐句准确地抄录这页上的所有文字内容。
这是一页古籍校录PDF。请按原文格式转录，精确保留：
- 所有上标数字[1][2]等
- 所有括号如（前缺）(昭)等
- 所有方框□缺字符号
- 所有标点符号
一字不漏地完整转录全部文字。
```

3. **分段识别优化**（针对生僻字）：

如果识别结果中存在可疑的低频字，裁剪该字所在的行/段落，单独重新识别：

```python
from PIL import Image
# 裁剪半行（包含可疑字的上下文）
crop = img.crop((x1, y1, x2, y2))  # 精确到该字所在行
```

单字/半行识别→正确；整页识别→可能替换为近义词。**分段识别是关键优化。**

### 4.3 生僻字专项校验

识别完成后，对以下类型的字做专项复核：

- **人名/地名/官职名**中的低频字
- **竹字头、走之底、言字旁**等偏旁的生僻字
- **上下文语义不通顺**的字

方法：裁剪该字±20像素区域，单独送视觉模型确认。

**已知案例：**
- "簉"(zào, 侍从)被整页识别为"筵"(yán, 筵席)
- "窅"(yǎo, 深远)被识别为"冒"(mào)
- "仞"(rèn)被标注为"屻"


## 5. 阶段四：文书图片提取

### 5.1 问题背景

古籍研究著作PDF通常在正文中嵌入古代文书影印件（手写/拓片）。
任务是将每张文书图片单独提取出来，每页仅展示一张。

### 5.2 裁剪方法对比

| 方法 | 精度 | 可靠性 | 适用场景 |
|------|------|--------|---------|
| 视觉模型返回百分比坐标 | 低(误差20-50px) | 不可靠 | 不推荐 |
| pdfplumber图片碎片拼接 | 中 | 不稳定(碎片边界不准) | 仅作辅助参考 |
| **像素级自动检测(推荐)** | **高(±2px)** | **可靠** | **标准方法** |

### 5.3 像素级自动检测流程（标准方法）

**步骤1: 高分辨率渲染**

```python
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument("input.pdf")
# 对含文书图片的页面，使用更高分辨率
bitmap = pdf[page_idx].render(scale=6.0)  # 约432DPI
img = bitmap.to_pil()
```

或使用内置函数（内存更友好）：
```python
from extract_regions import render_page
img = render_page("input.pdf", page_idx=0, scale=6.0)
```

**步骤2: 灰度+阈值生成文字蒙版**

```python
import numpy as np
from PIL import Image
arr = np.array(img.convert('L'))  # 转灰度
text_mask = arr < 180              # 文字为深色(低灰度值)
```

**步骤3: 行列统计检测边界**

```python
row_counts = text_mask.sum(axis=1)  # 每行暗像素数
col_counts = text_mask.sum(axis=0)  # 每列暗像素数
```

**步骤4: 区域分割**

- 按行统计找连续文字区域
- 合并小间隙(≤30px)
- 在大间隙(>50px)处分割上下两张文书
- 排除页眉/标题区域

**步骤5: 加缓冲裁剪**

```python
from extract_regions import analyze_layout, crop_with_buffer
layout = analyze_layout(img)
for i, doc_img in enumerate(layout["doc_images"]):
    cropped = crop_with_buffer(img, doc_img, buffer=30)
    cropped.save(f"output/doc_{page}_{i+1}.png")
```

### 5.4 大PDF中的文书提取策略

对于大PDF（>50页），不是所有页面都含文书图片。建议：

1. 先用 `render_page` 逐页低分辨率(scale=2)渲染预览
2. 用 `view_image` 批量判断哪些页面含文书图片
3. 仅对含文书的页面用高分辨率(scale=6)渲染和裁剪
4. 避免对全部页面做高分辨率渲染

```python
from extract_regions import render_page, get_page_count

total = get_page_count("input.pdf")
doc_pages = []  # 记录含文书的页面索引

for i in range(total):
    img = render_page("input.pdf", i, scale=2.0)  # 低分辨率预览
    layout = analyze_layout(img)
    if layout["doc_images"]:
        doc_pages.append(i)
    del img  # 释放内存

# 仅对含文书的页面做高分辨率处理
for i in doc_pages:
    img = render_page("input.pdf", i, scale=6.0)
    layout = analyze_layout(img)
    for j, doc_region in enumerate(layout["doc_images"]):
        cropped = crop_with_buffer(img, doc_region, buffer=30)
        cropped.save(f"文书图片/{碑铭名称}_{原书页码}.png")
    del img
```

### 5.5 裁剪后验证

对每张裁剪结果，调用 `view_image` 检查四边：

```
请检查这张文书图片四个边缘的完整性：
上/下/左/右边缘是否有文字笔画被截断？
严重程度：无截断/轻微/明显/严重？
```

**左右边缘个别列被截断的判断：**
- 用 `view_image` 对比原始PDF页面
- 如果原始页面中该列文字本身就紧贴文书纸张边缘 → 是原文排版特征，非裁剪问题
- 如果原始页面中有完整文字但裁剪后缺失 → 需要调整坐标

### 5.6 命名规范

```
{碑铭名称}_{原书页码}.png          # 单张
{碑铭名称}_{原书页码}_上.png        # 上下两张时
{碑铭名称}_{原书页码}_下.png
```

示例：
```
唐右翊卫将军康国公史大奈碑_16页.png
唐右翊卫将军康国公史大奈碑_17页_上.png
唐右翊卫将军康国公史大奈碑_17页_下.png
```


## 6. 阶段五：质量校验

### 6.1 OCR文字校验

- [ ] 标题识别完整（无遗漏字）
- [ ] 文书编号正确（如S.2078V、P.2551V）
- [ ] 上标数字[1][2]...保留完整
- [ ] 括号标注（前缺）(昭)等保留完整
- [ ] 方框□缺字符号保留完整
- [ ] 标点符号（中文逗号/句号/分号）保留完整
- [ ] 生僻字已通过分段识别校验
- [ ] 校释内容中的书名号《》、引号""等保留完整

### 6.2 文书图片校验

- [ ] 每张图片仅含一张文书（无混入）
- [ ] 四边无多余元素（页眉、标题、分割线）
- [ ] 上/下边缘文字笔画完整
- [ ] 左/右边缘截断已与原始PDF对比确认
- [ ] 命名规范正确（碑铭名称+页码）

### 6.3 页码校验

- [ ] 所有内容标注了PDF页码（第N页，从1开始）
- [ ] 所有内容标注了原书页码（从PDF左上角/页眉提取）
- [ ] 页码映射关系正确（PDF页码→原书页码可能不连续）


## 7. 阶段六：交付物输出

### 7.1 Excel结构

| Sheet | 内容 | 说明 |
|-------|------|------|
| 篇目总览 | 序号、标题、编号、PDF页码、原书页码、摘要 | 全局导航 |
| 完整OCR文字 | 分行按PDF页码记录全部识别文字 | 核心内容 |
| 文书图片 | 文件名、原书页码、嵌入图片、说明 | 图片展示 |
| 方案对比 | 各方案准确率对比（如有） | 方法论说明 |
| 教训与优化 | 问题排查记录、优化策略、经验沉淀 | 质量保障 |

### 7.2 文件命名

```
output/
├── {书名}OCR结果.xlsx
└── 文书图片/
    ├── {碑铭名称}_{页码}.png
    └── ...
```


## 8. 附录A：大PDF分批处理指南

### 8.1 为什么需要分批

`pypdfium2` 渲染时，每页scale=4的PNG约5-15MB，scale=6约10-30MB。
一次性渲染全部页面会导致：
- **内存溢出**（OOM）：100页 × 20MB = 2GB纯图片内存
- **处理缓慢**：GC压力增大，整体耗时倍增

### 8.2 分批策略

| PDF页数 | 推荐方式 | 说明 |
|---------|---------|------|
| ≤10页 | `render_pdf_pages()` 一次性渲染 | 简单直接 |
| 11-50页 | `render_page_range()` 分批渲染 | 每批10页 |
| >50页 | `render_page()` 逐页渲染 | 最省内存 |

### 8.3 内置分批函数

**`get_page_count(pdf_path)`** — 获取总页数，不加载页面内容：

```python
from extract_regions import get_page_count
total = get_page_count("input.pdf")  # 如 256
```

**`get_batch_ranges(total_pages, batch_size=10)`** — 计算分批范围：

```python
from extract_regions import get_batch_ranges
batches = get_batch_ranges(256, batch_size=10)
# [(0,10), (10,20), (20,30), ..., (250,256)]
```

**`render_page_range(pdf_path, start, end, scale, output_dir)`** — 渲染指定页范围 [start, end) 为PNG文件。返回渲染后的图片路径列表。

```python
from extract_regions import render_page_range
paths = render_page_range("input.pdf", 0, 10, scale=4.0, output_dir="./batch_1")
# 返回 ['batch_1/page_01.png', 'batch_1/page_02.png', ...]
```

**`render_page(pdf_path, page_idx, scale)`** — 渲染PDF的指定单页为PIL.Image。不保存文件，直接返回内存中的图片对象。

```python
from extract_regions import render_page
img = render_page("input.pdf", 15, scale=6.0)
# 返回 PIL.Image，适合直接分析/裁剪
```

### 8.4 推荐处理模式

**模式一：批量OCR（关注文字提取）**

```python
from extract_regions import get_batch_ranges, render_page_range

batches = get_batch_ranges(total, batch_size=10)
for batch_idx, (start, end) in enumerate(batches):
    paths = render_page_range("input.pdf", start, end, scale=4.0, output_dir=f"./batch_{batch_idx}")
    for path in paths:
        # 对每张图片调用 view_image OCR
        ...
    # 处理完一批后，可以删除该批次的临时图片释放磁盘空间
```

**模式二：选择性高分辨率处理（关注文书图片提取）**

```python
from extract_regions import get_page_count, render_page, analyze_layout, crop_with_buffer

total = get_page_count("input.pdf")
for i in range(total):
    # 低分辨率预览判断是否含文书
    preview = render_page("input.pdf", i, scale=2.0)
    layout = analyze_layout(preview)
    del preview

    if layout["doc_images"]:
        # 仅对含文书的页面做高分辨率渲染
        hd_img = render_page("input.pdf", i, scale=6.0)
        hd_layout = analyze_layout(hd_img)
        for j, region in enumerate(hd_layout["doc_images"]):
            cropped = crop_with_buffer(hd_img, region, buffer=30)
            cropped.save(f"文书图片/doc_{i+1}_{j+1}.png")
        del hd_img
```

### 8.5 内存管理要点

1. **显式释放**：处理完一页后 `del img`，处理完一批后清理临时文件
2. **避免累积**：不要把所有渲染结果保存在列表中，处理完即释放
3. **按需渲染**：OCR用scale=4，裁剪用scale=6，预览用scale=2-3
4. **进度追踪**：大PDF处理时间较长，应打印进度信息


## 9. 常见陷阱

### 9.1 pdfplumber图片碎片不可靠

同一张文书图片在pdfplumber中可能被拆成多个碎片，碎片边界与视觉边界不一致。
**不要依赖pdfplumber的图片坐标来裁剪。**

### 9.2 整页OCR的生僻字问题

视觉模型处理整页大图(~500万像素)时，低频生僻字容易被高频近义词替换。
**解决：分段识别+专项校验。**

### 9.3 页码不连续

PDF页码(PDF文件的页面序号)和原书页码(书本身的印刷页码)可能不对应。
例如PDF第1页可能是原书第15页。**始终同时记录两种页码。**

### 9.4 文书图片的左右边缘

古籍文书影印件中，边缘竖列文字可能本身就紧贴纸张边界。
这不是裁剪问题，而是原文排版特征。**需要与原始PDF对比确认。**

### 9.5 一页含多张文书

有些页面上下各有一张文书图片，需要：
1. 先用像素检测找到最大间隙位置
2. 在间隙处分割
3. 分别裁剪为独立图片
4. 用"_上"/"_下"后缀区分

### 9.6 大PDF内存溢出

一次性渲染全部高分辨率页面会导致OOM。
**使用 `render_page()` 或 `render_page_range()` 分批处理。**


## 10. 经验教训

### 10.1 PDF预检是必选项

永远先检查文字层可靠性。缺少ToUnicode映射表 → 文字层不可信 → 必须用视觉模型。
**跳过这步会导致40-60%的形近字错误且不自知。**

### 10.2 视觉模型的上下文长度陷阱

单字识别正确 ≠ 整页识别正确。低频生僻字在长上下文中会被语义替换。
**分段识别是准确率的保障。**

### 10.3 裁剪精度决定质量

视觉模型返回的百分比坐标误差可达20-50像素。
**像素级自动检测(灰度阈值+行列统计)是可靠的方法。**

### 10.4 始终保留双页码

PDF页码用于定位文件，原书页码用于学术引用。
**两种页码的映射关系是交付物的基本要求。**

### 10.5 交叉验证

当对某个字的识别有疑问时，用多种方式验证：
1. 裁剪局部重新识别
2. 查阅原文扫描件
3. 结合上下文语义判断
4. 参考已有学术文献中的引用

### 10.6 大PDF必须分批

内存是有限资源。100页scale=6的渲染图约需2-3GB纯图片内存。
**分批渲染+显式释放是处理大PDF的唯一可靠方式。**