from __future__ import annotations
import requests
from .config import SEC_USER_AGENT

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"

def latest_material_filing(ticker: str):
    if not SEC_USER_AGENT: return None
    h={"User-Agent":SEC_USER_AGENT,"Accept-Encoding":"gzip, deflate"}
    r=requests.get(TICKERS_URL,headers=h,timeout=12); r.raise_for_status()
    match=next((x for x in r.json().values() if str(x.get("ticker","")).upper()==ticker.upper()),None)
    if not match: return None
    cik=str(match["cik_str"]).zfill(10)
    r2=requests.get(SUBMISSIONS.format(cik=cik),headers=h,timeout=12); r2.raise_for_status()
    recent=((r2.json().get("filings") or {}).get("recent") or {})
    forms=recent.get("form") or []; acc=recent.get("accessionNumber") or []; dates=recent.get("filingDate") or []; docs=recent.get("primaryDocument") or []
    material={"8-K","6-K","10-Q","10-K","20-F","F-1","S-3","424B5"}
    for i,form in enumerate(forms):
        if form in material:
            a=acc[i] if i<len(acc) else None; d=docs[i] if i<len(docs) else None; dt=dates[i] if i<len(dates) else None
            url=None
            if a and d:
                url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a.replace('-','')}/{d}"
            return {"form":form,"date":dt,"url":url}
    return None
