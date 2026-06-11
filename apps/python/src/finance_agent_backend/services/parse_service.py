"""ParseService — 文件解析 + 银行检测的业务编排。"""
from __future__ import annotations

import os

from finance_agent_backend.account_registry import (
    AccountRegistry,
    get_account_entries,
)


class ParseService:
    """封装 parser_router + detect_banks，自 wire AccountRegistry。"""

    def __init__(self):
        self._account_registry = self._load_account_registry()

    @staticmethod
    def _load_account_registry() -> AccountRegistry:
        return AccountRegistry(get_account_entries())

    def parse(self, file_path: str, bank: str | None = None, doc_type: str | None = None) -> dict:
        """解析单个文件（PDF / CSV / Excel）。"""
        from finance_agent_backend import parser_router
        return parser_router.route(file_path, bank=bank, doc_type=doc_type)

    def detect_banks(self, file_paths: list[str]) -> list[dict]:
        """批量检测文件银行类型。"""
        from finance_agent_backend import parser_router

        results = []
        for fp in file_paths:
            if not os.path.exists(fp):
                results.append({
                    "filePath": fp, "bank": "未知银行",
                    "bankCode": "UNKNOWN", "docType": "unknown", "status": "failed",
                })
                continue

            ext = os.path.splitext(fp)[1].lower()
            try:
                if ext == '.csv':
                    results.append({
                        "filePath": fp, "bank": "工商银行", "bankCode": "ICBC",
                        "docType": "流水", "status": "ok",
                    })
                    continue
                if ext == '.xlsx':
                    results.append({
                        "filePath": fp, "bank": "招商银行", "bankCode": "CMB",
                        "docType": "流水", "status": "ok",
                    })
                    continue

                info = parser_router.detect_bank_from_pdf(fp)
                results.append({
                    "filePath": fp, "bank": info["bank"],
                    "bankCode": info["bankCode"], "docType": info["docType"],
                    "status": "ok",
                })
            except Exception:
                results.append({
                    "filePath": fp, "bank": "未知银行",
                    "bankCode": "UNKNOWN", "docType": "unknown", "status": "failed",
                })
        return results

    def detect_supported_banks(self) -> list[dict]:
        """返回当前支持的银行列表。"""
        from finance_agent_backend import parser_router
        return [
            {"code": code, "name": name}
            for code, name in parser_router.BANK_CODE_TO_NAME.items()
        ]

    def generate_excel(self, transactions: list[dict], output_path: str) -> str:
        """导出交易列表到 Excel。"""
        from finance_agent_backend.models import Transaction
        from finance_agent_backend.tools import excel_builder

        txn_objects = [Transaction.from_dict(t) for t in transactions]
        builder = excel_builder.ExcelBuilder()
        return builder.build(txn_objects, output_path)
