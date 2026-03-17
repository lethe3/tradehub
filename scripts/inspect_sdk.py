#!/usr/bin/env python3
"""
用法：python scripts/inspect_sdk.py <模块路径>
例：  python scripts/inspect_sdk.py im.v1
     python scripts/inspect_sdk.py bitable.v1
"""
import sys
import inspect
import lark_oapi as lark


def inspect_module(path: str):
    parts = path.split(".")
    obj = lark
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            print(f"[ERROR] lark_oapi.{path} 不存在")
            return

    print(f"=== lark_oapi.{path} ===")
    if inspect.isclass(obj) or inspect.ismodule(obj):
        for name, member in inspect.getmembers(obj):
            if name.startswith("_"):
                continue
            if inspect.isfunction(member) or inspect.ismethod(member):
                try:
                    sig = inspect.signature(member)
                    print(f"  {name}{sig}")
                except (ValueError, TypeError):
                    print(f"  {name}(...)")
            elif inspect.isclass(member):
                print(f"  [class] {name}")
    else:
        print(f"  {repr(obj)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    inspect_module(sys.argv[1])
