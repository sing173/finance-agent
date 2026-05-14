"""科目加载器 — 从标准科目 xlsx 文件加载会计科目并构建层级名称"""
import openpyxl
from typing import Dict, Optional

from ..models import Subject


class SubjectLoader:
    """从金蝶精斗云导出的科目 xlsx 加载科目字典

    科目 xlsx 格式（列顺序固定）：
        A: 编码  B: 名称  C: 类别  D: 余额方向
        E: 辅助核算类别  F: 是否现金科目  G: 状态  H: 是否平行科目
    """

    def load(self, xlsx_path: str) -> Dict[str, Subject]:
        """加载科目文件，返回以科目编码为 key 的字典，并自动填充 full_name。

        Args:
            xlsx_path: 科目 xlsx 文件路径

        Returns:
            Dict[str, Subject]，key 为科目编码字符串
        """
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        ws = wb.active

        subjects: Dict[str, Subject] = {}

        for row in ws.iter_rows(min_row=2, values_only=True):
            code = row[0]
            if not code:
                continue
            code = str(code).strip()
            name = str(row[1]).strip() if row[1] else ''
            category = str(row[2]).strip() if row[2] else ''
            direction = str(row[3]).strip() if row[3] else '借'
            aux_category = str(row[4]).strip() if row[4] else ''
            is_cash = str(row[5]).strip() == '是' if row[5] else False
            enabled = str(row[6]).strip() != '停用' if row[6] else True

            subjects[code] = Subject(
                code=code,
                name=name,
                category=category,
                direction=direction,
                aux_category=aux_category,
                is_cash=is_cash,
                enabled=enabled,
                full_name='',  # 后面统一填充
            )

        wb.close()

        # 填充 full_name（父_子 层级拼接）
        for code, subject in subjects.items():
            subject.full_name = self._build_full_name(code, subjects)

        return subjects

    def _build_full_name(self, code: str, subjects: Dict[str, Subject]) -> str:
        """递归向上拼接完整科目层级名称。

        金蝶科目编码规则：父编码是子编码的前缀。
        例如：10002 是 1000201 的父科目。
        完整名称：银行存款_工商银行（4363）

        Args:
            code: 当前科目编码
            subjects: 全量科目字典

        Returns:
            完整层级名称，如 '银行存款_工商银行（4363）'
        """
        parts = self._get_ancestor_chain(code, subjects)
        # 只取最顶层父科目和当前科目（跳过中间层，与金蝶实际显示一致）
        if len(parts) == 1:
            return parts[0]
        # 将祖先链（从根到叶）用 _ 连接
        return '_'.join(parts)

    def _get_ancestor_chain(self, code: str, subjects: Dict[str, Subject]) -> list:
        """返回从根科目到当前科目的名称链（包含自身）。"""
        chain = []
        current_code = code
        visited = set()

        while current_code and current_code not in visited:
            visited.add(current_code)
            if current_code in subjects:
                chain.append(subjects[current_code].name)
            # 找父编码：在现有编码中找最长的能作为当前编码前缀的编码
            parent_code = self._find_parent_code(current_code, subjects)
            current_code = parent_code

        chain.reverse()  # 从根到叶
        return chain

    def _find_parent_code(self, code: str, subjects: Dict[str, Subject]) -> Optional[str]:
        """在科目字典中找当前编码的直接父编码（最长匹配前缀）。"""
        best_parent = None
        best_len = 0
        for candidate in subjects:
            if (
                len(candidate) < len(code)
                and code.startswith(candidate)
                and len(candidate) > best_len
            ):
                best_parent = candidate
                best_len = len(candidate)
        return best_parent

    def get_full_name(self, code: str, subjects: Dict[str, Subject]) -> str:
        """获取指定科目的完整层级名称（full_name 字段已预填充时直接返回）。"""
        subject = subjects.get(code)
        if not subject:
            return code
        if subject.full_name:
            return subject.full_name
        return self._build_full_name(code, subjects)
