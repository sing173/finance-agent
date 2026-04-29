#!/usr/bin/env python3
"""
finance-agent Python Bridge
JSON-RPC 2.0 服务器，通过 stdio 与 Electron 通信
同步版本 — 简单、可靠、兼容所有 Python 3.11+
"""

import json
import sys

# 方法注册表
METHODS = {}


def register_method(name: str):
    """装饰器：注册 RPC 方法"""
    def decorator(func):
        METHODS[name] = func
        return func
    return decorator


@register_method("health")
def handle_health(params: dict) -> dict:
    import sys
    return {
        "status": "ok",
        "version": "0.1.0",
        "python_version": sys.version,
    }


def handle_request(request: dict) -> dict:
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")

    if method in METHODS:
        try:
            result = METHODS[method](params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }


def main():
    """主循环：逐行读取 stdin，解析 JSON-RPC，写入 stdout"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
        else:
            response = handle_request(request)

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
