#!/usr/bin/env python3
"""Falha se houver 0 ou mais de um head no grafo Alembic (branches divergentes)."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def main() -> int:
    backend = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        print(
            f"ERRO: esperado exatamente 1 revision head no Alembic, obtido {len(heads)}: {heads}",
            file=sys.stderr,
        )
        return 1
    print(f"OK: Alembic head único — {heads[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
