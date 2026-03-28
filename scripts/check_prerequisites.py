"""Check that all prerequisites for MarketPulse AI are installed.

Run: python scripts/check_prerequisites.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Optional


def check(name, cmd, min_version=None):
    # type: (str, list, Optional[str]) -> bool
    path = shutil.which(cmd[0])
    if not path:
        print("  MISSING  {} — not found in PATH".format(name))
        return False

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        version = result.stdout.strip() or result.stderr.strip()
        print("  OK       {} — {}".format(name, version))
        return True
    except Exception as e:
        print("  ERROR    {} — {}".format(name, e))
        return False


def main():
    print("=== MarketPulse AI — Prerequisites Check ===\n")

    results = []

    # Python
    print("  INFO     Python interpreter: {}".format(sys.executable))
    print("  INFO     Python version: {}".format(sys.version))
    py_ok = sys.version_info >= (3, 12)
    if not py_ok:
        print("  WARNING  Python 3.12+ required, found {}.{}".format(
            sys.version_info.major, sys.version_info.minor))
        print("           Install from: https://www.python.org/downloads/")
    results.append(("Python 3.12+", py_ok))

    # PostgreSQL
    results.append(("PostgreSQL (psql)", check("PostgreSQL", ["psql", "--version"])))

    # uv
    results.append(("uv", check("uv", ["uv", "--version"])))

    # Node.js
    results.append(("Node.js", check("Node.js", ["node", "--version"])))

    # npm
    results.append(("npm", check("npm", ["npm", "--version"])))

    print("\n=== Summary ===\n")
    all_ok = True
    for name, ok in results:
        status = "OK" if ok else "NEEDS INSTALL"
        print("  {} {}: {}".format("[OK]" if ok else "[!!]", name, status))
        if not ok:
            all_ok = False

    if not all_ok:
        print("\n=== Installation Instructions ===\n")
        for name, ok in results:
            if ok:
                continue
            if name == "Python 3.12+":
                print("  {}: https://www.python.org/downloads/".format(name))
            elif name == "PostgreSQL (psql)":
                print("  {}: https://www.postgresql.org/download/windows/".format(name))
            elif name == "uv":
                print("  {}: pip install uv  OR  https://docs.astral.sh/uv/".format(name))
            elif name == "Node.js":
                print("  {}: https://nodejs.org/ (LTS recommended)".format(name))
            elif name == "npm":
                print("  {}: Comes with Node.js".format(name))
        print()

    if all_ok:
        print("\n  All prerequisites met! Ready to start development.\n")
    else:
        print("  Install missing prerequisites and run this script again.\n")


if __name__ == "__main__":
    main()
