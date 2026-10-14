"""Pull consented, verified historical September-to-admission rows from private Supabase.
No direct API endpoint in the public browser. Nothing printed except aggregate count.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

BATCH=500
COLUMNS=("year","exam_type","program_key","applicant_hash","applied","verified",
         "consented","admitted","student")


def collect(url,key,*, opener=urlopen):
    if not url.startswith("https://") or not urlparse(url).netloc or not key:
        raise ValueError("Secure Supabase URL and service-role key required")
    base=url.rstrip("/")
    output=[]
    offset=0
    while True:
        query=urlencode({
            "select":",".join(COLUMNS),"year":"gte.2022","exam_type":"eq.september",
            "verified":"eq.true","consented":"eq.true","applied":"eq.true",
            "order":"year.asc,id.asc","limit":str(BATCH),"offset":str(offset)
        })
        endpoint=base+"/rest/v1/historical_mock_outcomes?"+query
        request=Request(endpoint,headers={
            "apikey":key,"Authorization":"Bearer "+key,"Accept":"application/json"
        })
        with opener(request,timeout=30) as response:
            records=json.loads(response.read().decode("utf-8"))
        if not isinstance(records,list):
            raise ValueError("Supabase returned invalid records format")
        for row in records:
            if set(row)!=set(COLUMNS):
                raise ValueError("Private historical record schema mismatch")
            if row.get("year") not in range(2022,2027):
                raise ValueError("Future-year historical response rejected")
            output.append(row)
        if len(records)<BATCH:break
        offset+=BATCH
        if offset>200000:
            raise ValueError("Excessive private historical record count")
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    rows=collect(os.environ.get("SUPABASE_URL",""),
                 os.environ.get("SUPABASE_SERVICE_ROLE_KEY",""))
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in rows),encoding="utf-8")
    path.chmod(0o600)
    # Never print individual scores, subjects, identifiers, hashes or tokens.
    print("Fetched verified historical observations:",len(rows))


if __name__=="__main__":
    main()
