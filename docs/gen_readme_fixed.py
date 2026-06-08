#!/usr/bin/env python3
"""Regenerate README.md from PRD.html and architecture.html.

Simple approach:
  1. Pre-extract tables, flows, SVGs → placeholders
  2. Apply ordered regex substitutions to strip/convert HTML
  3. Post-process whitespace
"""
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

PRD_PATH = Path("docs/PRD.html")
ARCH_PATH = Path("docs/architecture.html")
README_PATH = Path("README.md")


def extract_tables(html):
    tables = []
    for tm in re.finditer(r'<table>(.*?)</table>', html, re.DOTALL):
        rows = []
        for rm in re.finditer(r'<tr>(.*?)</tr>', tm.group(1), re.DOTALL):
            cells = re.findall(r'<t[hd]>(.*?)</t[hd]>', rm.group(1), re.DOTALL)
            cell_texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if cell_texts:
                rows.append(cell_texts)
        if rows:
            tables.append(rows)
    return tables


def md_table(rows):
    if not rows:
        return ''
    cols = max(len(r) for r in rows)
    lines = []
    header = rows[0] + [''] * (cols - len(rows[0]))
    lines.append('| ' + ' | '.join(str(c) for c in header) + ' |')
    lines.append('| ' + ' | '.join(['---'] * cols) + ' |')
    for row in rows[1:]:
        cells = [str(c) for c in row] + [''] * (cols - len(row))
        lines.append('| ' + ' | '.join(cells[:cols]) + ' |')
    return '\n'.join(lines)


def convert_flow(inner):
    """Extract flow-step blocks from .flow inner HTML using div-depth counting."""
    steps = []
    for m in re.finditer(r'<div class="flow-step">', inner):
        start = m.end()
        depth = 1
        pos = start
        while pos < len(inner) and depth > 0:
            next_open = inner.find('<div', pos)
            next_close = inner.find('</div>', pos)
            if next_close < 0:
                break
            if 0 <= next_open < next_close:
                depth += 1
                pos = next_open + 4
            else:
                depth -= 1
                pos = next_close + 6
        if depth == 0:
            step_html = inner[start:pos - 6]  # exclude the closing </div>
            # Extract num, label, desc
            num_m = re.search(r'<div class="num">(.*?)</div>', step_html, re.DOTALL)
            label_m = re.search(r'<div class="label">(.*?)</div>', step_html, re.DOTALL)
            desc_m = re.search(r'<div class="desc">(.*?)</div>', step_html, re.DOTALL)

            num = re.sub(r'<[^>]+>', '', num_m.group(1)).strip() if num_m else ''
            label = re.sub(r'<[^>]+>', '', label_m.group(1)).strip() if label_m else ''
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''

            parts = [p for p in [num, label, desc] if p]
            steps.append(' '.join(parts))

    if not steps:
        return ''
    lines = []
    for i, text in enumerate(steps):
        sep = '  →  ' if i < len(steps) - 1 else ''
        lines.append(f'- {text}{sep}')
    return '\n'.join(lines)


def convert_flow_from_html(html):
    """Find <div class="flow"> in html, extract inner content, convert to list."""
    flow_start = html.find('<div class="flow">')
    if flow_start < 0:
        return ''
    # Start AFTER the opening <div ...> tag (at '>')
    pos = html.find('>', flow_start) + 1

    # Find matching </div> for .flow
    # depth starts at 0; each nested <div> adds 1, each </div> subtracts 1
    # The </div> that makes depth -1 is the outer .flow's closing tag
    depth = 0
    while pos < len(html) and depth >= 0:
        next_open = html.find('<div', pos)
        next_close = html.find('</div>', pos)
        if next_close < 0:
            break
        if 0 <= next_open < next_close:
            depth += 1
            pos = next_open + 4  # skip '<div'
        else:
            depth -= 1
            pos = next_close + 6  # skip '</div>'
    if depth != -1:
        return ''
    # Inner content: from after '<div class="flow">' to before closing </div>
    inner_start = flow_start + len('<div class="flow">')
    flow_inner = html[inner_start:pos - 6]
    return _convert_flow_steps(flow_inner)


def _convert_flow_steps(inner):
    """Convert flow-step divs within flow inner HTML to Markdown list."""
    steps = []
    for m in re.finditer(r'<div class="flow-step">', inner):
        start = m.end()
        # Find matching </div> for this flow-step
        depth = 0
        pos = start
        while pos < len(inner) and depth >= 0:
            no = inner.find('<div', pos)
            nc = inner.find('</div>', pos)
            if nc < 0:
                break
            if 0 <= no < nc:
                depth += 1
                pos = no + 4
            else:
                depth -= 1
                pos = nc + 6
        if depth == -1:
            step_html = inner[start:pos - 6]
            num_m = re.search(r'<div class="num">(.*?)</div>', step_html, re.DOTALL)
            label_m = re.search(r'<div class="label">(.*?)</div>', step_html, re.DOTALL)
            desc_m = re.search(r'<div class="desc">(.*?)</div>', step_html, re.DOTALL)

            num = re.sub(r'<[^>]+>', '', num_m.group(1)).strip() if num_m else ''
            label = re.sub(r'<[^>]+>', '', label_m.group(1)).strip() if label_m else ''
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ''

            parts = [p for p in [num, label, desc] if p]
            steps.append(' '.join(parts))

    if not steps:
        return ''
    lines = []
    for i, text in enumerate(steps):
        sep = '  →  ' if i < len(steps) - 1 else ''
        lines.append(f'- {text}{sep}')
    return '\n'.join(lines)


def strip_html(html):
    """Convert HTML to Markdown using sequential regex replacements.

    Order matters: more specific patterns first.
    """
    s = html

    # Unescape HTML entities
    s = s.replace('&middot;', '·')
    s = s.replace('&#10230;', '→')
    s = s.replace('&lt;', '<')
    s = s.replace('&gt;', '>')
    s = s.replace('&amp;', '&')
    s = s.replace('&nbsp;', ' ')

    # Remove HTML comments
    s = re.sub(r'<!--.*?-->', '', s, flags=re.DOTALL)

    # Handle heading tags: <h2>Title</h2> → \n## Title\n
    for tag, prefix in [('h1', '#'), ('h2', '##'), ('h3', '###'),
                         ('h4', '####'), ('h5', '#####'), ('h6', '######')]:
        s = re.sub(
            rf'<{tag}[^>]*>(.*?)</{tag}>',
            lambda m, p=prefix: f'\n{p} {m.group(1).strip()}\n',
            s, flags=re.DOTALL
        )

    # Handle block tags: <p>content</p> → \ncontent\n
    for tag in ['p', 'tr']:
        s = re.sub(
            rf'<{tag}[^>]*>(.*?)</{tag}>',
            lambda m: f'\n{m.group(1).strip()}\n',
            s, flags=re.DOTALL
        )

    # Handle inline formatting
    for tag, md in [('strong', '**'), ('b', '**'), ('em', '*'), ('i', '*'), ('code', '`')]:
        s = re.sub(
            rf'<{tag}[^>]*>(.*?)</{tag}>',
            lambda m, c=md: f'{c}{m.group(1).strip()}{c}',
            s, flags=re.DOTALL
        )

    # Handle links: <a href="url">text</a> → text(url)
    s = re.sub(
        r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>',
        lambda m: f'{m.group(2).strip()}({m.group(1)})',
        s, flags=re.DOTALL
    )

    # Handle <li> → list item
    s = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', s, flags=re.DOTALL)

    # Remove all remaining HTML tags (div, span, section, td, th, etc.)
    s = re.sub(r'<[^>]+>', '', s)

    # Convert <br> and <br/> to newlines
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.IGNORECASE)

    # Clean whitespace: collapse spaces but keep intentional newlines
    lines = s.split('\n')
    cleaned = []
    for line in lines:
        stripped = ' '.join(line.split())
        cleaned.append(stripped)
    s = '\n'.join(cleaned)

    # Collapse multiple blank lines
    s = re.sub(r'\n{3,}', '\n\n', s)

    return s.strip()


# ── Section handling ──────────────────────────────────────────────────

def extract_main(html):
    m = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    return m.group(1) if m else html


def clean_content(content):
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    # Remove decorative sections (non-content)
    content = re.sub(r'<section\b[^>]*class="cover"[^>]*>.*?</section>', '', content, flags=re.DOTALL)
    content = re.sub(r'<section\b[^>]*class="toc"[^>]*>.*?</section>', '', content, flags=re.DOTALL)
    content = re.sub(r'<section\b[^>]*class="stat-row"[^>]*>.*?</section>', '', content, flags=re.DOTALL)
    content = re.sub(r'<section\b[^>]*class="section-icon"[^>]*>.*?</section>', '', content, flags=re.DOTALL)
    # Remove footer, aside, script
    content = re.sub(r'<footer.*?</footer>', '', content, flags=re.DOTALL)
    content = re.sub(r'<aside.*?</aside>', '', content, flags=re.DOTALL)
    content = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
    # Don't remove layout divs - let them be stripped later by strip_html
    return content


def extract_sections(content):
    parts = re.split(r'(<h2\b[^>]*>.*?</h2>)', content, flags=re.DOTALL)
    sections = []
    i = 0
    while i < len(parts):
        part = parts[i]
        if part.startswith('<h2'):
            title_m = re.search(r'<h2\b[^>]*>(.*?)</h2>', part, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
            body = parts[i + 1] if i + 1 < len(parts) else ''
            sections.append((title, body))
            i += 2
        else:
            if part.strip():
                sections.append(('', part))
            i += 1
    return sections


def render_section(title, body_html):
    out = []
    if title:
        out.append(f'## {title}')
        out.append('')

    if not body_html.strip():
        return '\n'.join(out)

    # 1. Tables → placeholders
    tables = extract_tables(body_html)
    ph_map = {}
    for idx, rows in enumerate(tables):
        ph = f'\x00T{idx}\x00'
        ph_map[ph] = '\n' + md_table(rows) + '\n'

    body = body_html
    t_idx = 0
    def put_ph(m):
        nonlocal t_idx
        ph = f'\x00T{t_idx}\x00'
        t_idx += 1
        return ph
    body = re.sub(r'<table>.*?</table>', put_ph, body, flags=re.DOTALL)

    # 2. Flow diagrams — replace entire .flow block with converted list
    body = _replace_flow_block(body)

    # 3. SVG → placeholder (preserve raw SVG, restore after strip_html)
    svg_map = {}
    svg_idx = 0
    def svg_ph(m):
        nonlocal svg_idx
        ph = f'\x00S{svg_idx}\x00'
        svg_idx += 1
        svg_map[ph] = f'\n```svg\n{m.group(0).strip()}\n```\n'
        return ph
    body = re.sub(r'<svg.*?</svg>', svg_ph, body, flags=re.DOTALL)

    # 4. Strip+convert HTML → MD
    body_md = strip_html(body)

    # 5. Restore tables
    for ph, md_text in ph_map.items():
        body_md = body_md.replace(ph, md_text)

    # 5b. Restore SVGs
    for ph, svg_block in svg_map.items():
        body_md = body_md.replace(ph, svg_block)

    # 6. Final whitespace cleanup
    body_md = re.sub(r'\n{3,}', '\n\n', body_md)

    out.append(body_md.strip())
    return '\n'.join(out)


def _replace_flow_block(html):
    """Find ALL <div class="flow">...</div> blocks and replace with Markdown lists."""
    result = html
    while True:
        flow_open = '<div class="flow">'
        start = result.find(flow_open)
        if start < 0:
            break

        # Start scanning AFTER the opening <div class="flow"> tag
        pos = result.find('>', start) + 1

        # Find matching </div> using depth counting
        # The </div> that brings depth to 0 is the .flow's closing tag
        depth = 1
        while pos < len(result) and depth > 0:
            no = result.find('<div', pos)
            nc = result.find('</div>', pos)
            if nc < 0:
                break
            if 0 <= no < nc:
                depth += 1
                pos = no + 4
            else:
                depth -= 1
                pos = nc + 6
        if depth != 0:
            break  # unbalanced

        # Inner content
        inner_start = start + len(flow_open)
        inner = result[inner_start:pos - 6]
        md_list = _convert_flow_steps(inner)

        # Reconstruct
        prefix = result[:start]
        suffix = result[pos:]
        result = prefix + '\n' + md_list + '\n' + suffix

    return result


# ══════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════

def main():
    print("Reading source files...")
    prd_html = PRD_PATH.read_text(encoding='utf-8')
    arch_html = ARCH_PATH.read_text(encoding='utf-8')

    md = []

    # Header (product overview, written manually for quality)
    md.extend([
        '# FinanceAssistant',
        '',
        '---',
        '',
        '## 产品概述',
        '',
        'FinanceAssistant 是一款面向中小企业财务人员的桌面应用程序，旨在解决银行流水文件（PDF / CSV / Excel 等）到金蝶精斗云会计凭证的全链路自动化转换问题。（后续会扩展对接更多平台或自定义凭证模板）',
        '',
        '传统工作流中，财务人员需要手动打开银行对账单 PDF，逐条录入摘要、金额、对方户名，再对照科目表手工匹配借贷方科目——一条交易约需 1–2 分钟，一个月 200 条交易意味着 3–6 小时的低价值重复劳动。FinanceAssistant 将这一流程压缩至分钟级：拖入文件 → 自动识别银行与格式 → 解析交易 → 三层智能匹配科目 → 预览确认 → 一键导出金蝶凭证 Excel。',
        '',
    ])

    # PRD sections
    prd_content = clean_content(extract_main(prd_html))
    prd_sections = extract_sections(prd_content)
    for title, body in prd_sections:
        rendered = render_section(title, body)
        if rendered.strip():
            md.append(rendered)
            md.append('')

    # Document links
    md.extend([
        '---',
        '',
        '## 📖 完整文档',
        '',
        '- **[产品需求文档 (PRD)](docs/PRD.html)** — 产品经理视角，涵盖产品概述、目标用户、核心价值、功能概览、用户旅程',
        '- **[技术架构文档](docs/architecture.html)** — 涵盖进程架构、银行与格式支持、科目匹配系统、凭证系统、导出能力、技术栈、路线图、产品指标',
        '',
    ])

    # Architecture
    md.append('---')
    md.append('')
    md.append('## 🏗️ 技术架构')
    md.append('')

    arch_content = clean_content(extract_main(arch_html))
    arch_sections = extract_sections(arch_content)
    for title, body in arch_sections:
        if not title or title.startswith('<') or len(title) > 120:
            continue
        rendered = render_section(title, body)
        if rendered.strip():
            md.append(rendered)
            md.append('')

    # Write
    final = '\n'.join(md)
    final = re.sub(r'\n{3,}', '\n\n', final)
    final = final.rstrip() + '\n'

    README_PATH.write_text(final, encoding='utf-8')
    print(f"Done! README.md: {len(final)} bytes, {final.count(chr(10))} lines")


if __name__ == '__main__':
    main()
