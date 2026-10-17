"""Check that an excerpt appears in a saved source's text.

Usage: backend/.venv/bin/python scripts/check_excerpt.py SOURCE_ID "exact excerpt"
Exit 0 if found (after whitespace/case normalisation), 1 if not. Also reports word count (max 25).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import norm

ROOT = Path(__file__).resolve().parent.parent
idx = {r["id"]: r for r in json.loads((ROOT / "data/sources/index.json").read_text())}
sid, excerpt = sys.argv[1], sys.argv[2]
if sid not in idx:
    print(f"NO_SUCH_SOURCE {sid}")
    sys.exit(2)
text = norm((ROOT / "data/sources" / idx[sid]["text_file"]).read_text())
words = len(excerpt.split())
ok = norm(excerpt) in text
print(f"{'FOUND' if ok else 'NOT_FOUND'} words={words}{' TOO_LONG' if words > 25 else ''}")
sys.exit(0 if ok and words <= 25 else 1)
