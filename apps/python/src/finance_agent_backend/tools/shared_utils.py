"""Shared utility functions for bank statement parsers.

Consolidates duplicated code found across 13 parser/builder files:
- PDF reading (9 identical copies → 1 function)
- Date parsing (6 implementations → 5 canonical functions)
- Amount parsing (7 implementations → 3 canonical functions)
- Span extraction/clustering/partitioning (3 copies → 1 set)
- Table helpers: nearby-number, balance extraction, key normalization
- Unified bank name constants
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import fitz


# ═══════════════════════════════════════════════════════════════════
# Bank name constants (unified — ICBC uses full name everywhere now)
# ═══════════════════════════════════════════════════════════════════

BANK_ICBC = "中国工商银行"
BANK_CMB = "招商银行"
BANK_GFB = "广发银行"
BANK_BOC = "中国银行"
BANK_CCB = "建设银行"


# ═══════════════════════════════════════════════════════════════════
# PDF file I/O
# ═══════════════════════════════════════════════════════════════════

def read_pdf_bytes(file_path: str) -> bytes:
    """Read PDF as bytes — bypasses Windows Unicode path issues in mupdf."""
    with open(file_path, 'rb') as f:
        return f.read()


def open_pdf(file_path: str) -> fitz.Document:
    """Open PDF from file path (handles Unicode Windows paths)."""
    return fitz.open('pdf', read_pdf_bytes(file_path))


# ═══════════════════════════════════════════════════════════════════
# Date parsing
# ═══════════════════════════════════════════════════════════════════

def parse_date_yyyymmdd(text: str) -> Optional[date]:
    """Parse YYYYMMDD or YYYY-MM-DD format."""
    text = text.strip()
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_date_chinese(text: str) -> Optional[date]:
    """Parse Chinese date: YYYY年M月D日, YYYY-M-D, YYYY-MM-DD."""
    if not text:
        return None
    m = re.search(r'(\d{4})[年-](\d{1,2})[月-](\d{1,2})', text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def parse_date_iso(text: str) -> Optional[date]:
    """Parse YYYY-MM-DD only (strict)."""
    text = text.strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_date_flexible(text: str) -> Optional[date]:
    """Parse YYYY-MM-DD, YYYYMMDD, or YYYY年MM月DD日."""
    text = text.strip()
    for fmt in ('%Y-%m-%d', '%Y%m%d'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_timestamp_date(ts: str) -> Optional[date]:
    """Extract date from timestamp like 2026-03-26-19.33.30.354123."""
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', ts)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════
# Amount parsing
# ═══════════════════════════════════════════════════════════════════

def parse_amount(text: str) -> Optional[Decimal]:
    """Parse amount to Decimal, stripping commas/spaces/plus-sign. Returns None on failure."""
    text = text.strip().replace(',', '').replace(' ', '')
    text = re.sub(r'^\+', '', text)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_amount_lenient(text: str) -> Decimal:
    """Parse amount with ￥/元 stripping. Returns Decimal('0') on empty/failure."""
    if not text:
        return Decimal('0')
    text = text.replace('￥', '').replace('元', '').strip()
    text = text.replace(',', '').replace('，', '').replace(' ', '')
    m = re.search(r'[\d,]+\.?\d*', text)
    if m:
        return Decimal(m.group().replace(',', ''))
    return Decimal('0')


def parse_amount_clean(text: str) -> Optional[Decimal]:
    """Parse amount with ￥/CNY stripping. Returns None on empty/failure."""
    text = text.strip().replace(',', '').replace(' ', '').replace('￥', '')
    text = text.replace('CNY', '').replace('cny', '')
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, Exception):
        return None


# ═══════════════════════════════════════════════════════════════════
# PDF span extraction & layout analysis
# ═══════════════════════════════════════════════════════════════════

def extract_all_spans(page: fitz.Page) -> List[dict]:
    """Extract all text spans from a PDF page with positions.

    Each span dict: {x0, y0, x1, y1, text, size}.
    """
    td = page.get_text('dict')
    spans = []
    for block in td.get('blocks', []):
        if 'lines' not in block:
            continue
        for line in block['lines']:
            for span in line['spans']:
                text = span['text'].strip()
                if not text:
                    continue
                spans.append({
                    'x0': span['bbox'][0], 'y0': span['bbox'][1],
                    'x1': span['bbox'][2], 'y1': span['bbox'][3],
                    'text': text, 'size': span.get('size', 0),
                })
    return spans


def cluster_by_y(spans: list, gap: float = 2.0) -> List[list]:
    """Cluster spans into rows by y-coordinate proximity.

    Adjacent spans with y0 difference <= gap are grouped into the same row.
    """
    if not spans:
        return []
    sorted_spans = sorted(spans, key=lambda s: s['y0'])
    clusters, current, current_y = [], [sorted_spans[0]], sorted_spans[0]['y0']
    for s in sorted_spans[1:]:
        if s['y0'] - current_y > gap:
            clusters.append(current)
            current, current_y = [s], s['y0']
        else:
            current.append(s)
            current_y = max(current_y, s['y0'])
    clusters.append(current)
    return clusters


# ═══════════════════════════════════════════════════════════════════
# Table region detection & partitioning
# ═══════════════════════════════════════════════════════════════════

def find_table_region(spans: list, col_titles: List[str],
                      fallback: Tuple[float, float] = (105.0, 165.0),
                      require_all: bool = False) -> Tuple[float, float]:
    """Find table y-range by locating column title spans.

    Args:
        require_all: If True, all col_titles must appear in a span to match.
            If False, any col_title match suffices.
    """
    if require_all:
        y_list = [s['y0'] for s in spans
                  if all(k in s['text'] for k in col_titles)]
    else:
        y_list = [s['y0'] for s in spans
                  if any(k in s['text'] for k in col_titles)]
    if not y_list:
        return fallback
    return min(y_list) - 5, max(s['y1'] for s in spans)


def partition_spans(spans: list, col_titles: List[str],
                    require_all: bool = False) -> Tuple[list, list, list]:
    """Partition spans into (header, table, footer) by y position."""
    table_start, table_end = find_table_region(spans, col_titles, require_all=require_all)
    header = [s for s in spans if s['y0'] < table_start - 5]
    table = [s for s in spans if table_start - 5 <= s['y0'] <= table_end + 5]
    footer = [s for s in spans if s['y0'] > table_end + 5]
    return header, table, footer


# ═══════════════════════════════════════════════════════════════════
# Nearby value / balance extraction
# ═══════════════════════════════════════════════════════════════════

def find_nearby_number(spans: list, ref_index: int,
                       max_distance: int = 5) -> Optional[Decimal]:
    """Find monetary value near a reference span (same-row priority)."""
    ref_y = spans[ref_index]['y0']
    candidates = []
    for offset in range(1, max_distance + 1):
        for idx in (ref_index + offset, ref_index - offset):
            if 0 <= idx < len(spans):
                s = spans[idx]
                if abs(s['y0'] - ref_y) < 3:
                    text = s['text'].strip()
                    if re.match(r'^-?\d[\d,]*\.\d{2}$', text):
                        candidates.append((abs(idx - ref_index), parse_amount(text)))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


def find_nearby_value(spans: list, ref_index: int,
                      max_distance: int = 5) -> Optional[str]:
    """Find numeric value string near a reference span (returns raw string)."""
    ref_y = spans[ref_index]['y0']
    for offset in range(1, max_distance + 1):
        for idx in (ref_index + offset, ref_index - offset):
            if 0 <= idx < len(spans):
                s = spans[idx]
                if abs(s['y0'] - ref_y) < 3:
                    text = s['text'].strip()
                    if re.match(r'^-?\d[\d,]*\.\d{2}$', text):
                        return text
    return None


def find_balance_in_spans(spans: list, keyword: str) -> Optional[str]:
    """Search spans for a keyword and extract associated balance value."""
    sorted_spans = sorted(spans, key=lambda s: (s['y0'], s['x0']))
    for i, s in enumerate(sorted_spans):
        if keyword in s['text']:
            m = re.search(r'(\d[\d,]*\.\d{2})', s['text'])
            if m:
                return m.group(1)
            return find_nearby_value(sorted_spans, i)
    return None


def extract_balance_from_footer(footer_spans: list, keyword: str) -> Optional[Decimal]:
    """Extract closing/ending balance from footer spans by keyword."""
    sorted_spans = sorted(footer_spans, key=lambda s: (s['y0'], s['x0']))
    for i, s in enumerate(sorted_spans):
        if keyword in s['text']:
            m = re.search(r'(\d[\d,]*\.\d{2})', s['text'])
            if m:
                return parse_amount(m.group(1))
            return find_nearby_number(sorted_spans, i)
    return None


# ═══════════════════════════════════════════════════════════════════
# Header metadata key normalization
# ═══════════════════════════════════════════════════════════════════

def normalize_key(key: str) -> str:
    """Normalize header key: remove NBSP, fullwidth/halfwidth colons, merge spaces."""
    key = key.replace('\xa0', ' ').replace(' ', '')
    key = key.replace('：', '').replace(':', '')
    return key


def lookup_header_key(header_keys: Dict[str, str], raw_key: str) -> Optional[str]:
    """Look up raw key in a HEADER_KEYS map (handles NBSP variants)."""
    norm = normalize_key(raw_key)
    for k, v in header_keys.items():
        if normalize_key(k) == norm:
            return v
    return None
