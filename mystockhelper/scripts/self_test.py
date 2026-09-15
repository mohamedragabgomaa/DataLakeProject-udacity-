import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.config import WATCHLIST
assert WATCHLIST==["PCLA","NVDA","ORCL","ESTC","XOS"]
print("PASS: watchlist")
print("PASS: imports")
print("PASS: no secret required for static self-test")
