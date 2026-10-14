"""Historical 2025 Soongsil CSAT component calculator.

Official 2025 category weights: 2025 Adiga school profile.
2025 CSAT score maxima and final normal social/science inquiry conversion table:
2026 Adiga profile, explicitly labelled *2025* appendix.
The 2026 worked examples for the natural group demonstrate the same component
weights and bonus pattern, allowing arithmetic verification.

This is a **2025 CSAT scoring** plugin, not a 2025 September predictor.
A September exam score requires a separately verified score-scale adjustment.
It must not be used to label application/admission outcomes.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_DOWN
from app.scoring import ScoreResult
from app.weighted_rules import public_percentile_conversion_tables

SOURCE_WEIGHTS="https://www.adiga.kr/ucp/uvt/uni/univDetailSelection.do?menuId=PCUVTINF2000&searchSyr=2025&unvCd=0000143"
SOURCE_2025_FINAL_INQUIRY_TABLE="https://www.adiga.kr/ucp/uvt/uni/univDetailSelection.do?menuId=PCUVTINF2000&searchSyr=2026&unvCd=0000143"
KOREAN_MAX=139
MATH_MAX=140
INQUIRY_MAX=70
WEIGHTS={
    "humanities":(.35,.25,.20,.20),
    "business":(.25,.35,.20,.20),
    "free_humanities":(.30,.25,.20,.25),
    "natural1":(.20,.35,.20,.25),
    "natural2":(.20,.35,.20,.25),
    "free_natural":(.20,.35,.20,.25),
}
ENGLISH={i:v for i,v in enumerate((200,194,186,173,144,116,87,44,0),1)}
HISTORY={i:Decimal("4")-Decimal(i-1)*Decimal(".5") for i in range(1,10)}
TABLE_ID="soongsil_2025_social_science"


def _d(v):
    if type(v) not in (int,float,Decimal) or isinstance(v,bool):
        raise ValueError("invalid numeric score")
    return Decimal(str(v))


def _trunc3(v):
    return v.quantize(Decimal(".001"),rounding=ROUND_DOWN)


def compute_soongsil_2025_csat(student,program, *, table=None):
    """Returns None if non-CSAT exam, incomplete inputs or unsupported track.
    Breakdowns are official *score components*, not chance of acceptance."""
    if (program.get("year")!=2025 or program.get("university")!="숭실대학교"
        or program.get("formula_id")!="soongsil_2025_csat_v1"
        or program.get("formula_source_url")!=SOURCE_WEIGHTS
        or student.get("exam_type")!="csat"):
        return None
    track=program.get("track")
    if track not in WEIGHTS:
        return None
    inquiries=student.get("inquiries")
    if not isinstance(inquiries,list) or len(inquiries)!=2 or any(
        i.get("kind") not in ("social","science") for i in inquiries):
        return None
    if student.get("english_grade") not in ENGLISH or student.get("history_grade") not in HISTORY:
        return None
    if (track in ("natural1","natural2","free_natural") and
       student.get("math_track") not in ("probability","calculus","geometry")):
        return None
    if student.get("math_track") not in ("probability","calculus","geometry"):
        return None
    table=public_percentile_conversion_tables() if table is None else table
    try:
        korean=_d(student["korean_std"])
        math=_d(student["math_std"])
        if not(0<=korean<=KOREAN_MAX and 0<=math<=MATH_MAX):
            return None
        pk=[_d(s["pct"]) for s in inquiries]
        if any(p!=p.to_integral_value() or not 0<=p<=100 for p in pk):
            return None
        converted=[]
        for inquiry,p in zip(inquiries,pk):
            val=table.get((2025,"숭실대학교",TABLE_ID,"*",int(p)))
            if val is None:return None
            converted.append(_d(val))
    except (KeyError,ValueError,TypeError):
        return None
    k_w,m_w,e_w,t_w=(Decimal(str(x)) for x in WEIGHTS[track])
    # The published rule explicitly truncates each region's score to 3 digits.
    breakdown={
        "국어":_trunc3(korean*(k_w*1000)/KOREAN_MAX),
        "수학":_trunc3(math*(m_w*1000)/MATH_MAX),
        "영어":_d(ENGLISH[student["english_grade"]]),
        "탐구 1":_trunc3(converted[0]*(t_w*500)/INQUIRY_MAX),
        "탐구 2":_trunc3(converted[1]*(t_w*500)/INQUIRY_MAX),
        "한국사":HISTORY[student["history_grade"]],
    }
    is_natural=track in ("natural1","natural2","free_natural")
    if is_natural and student["math_track"] in ("calculus","geometry"):
        rate=Decimal(".07") if track=="natural1" else Decimal(".05")
        breakdown["수학 가산점"]=_trunc3(math*rate)
    inquiry_bonus_kind=(
        "social" if track=="free_humanities" else
        "science" if is_natural else None
    )
    for i,(inq,p) in enumerate(zip(inquiries,pk),1):
        if inq["kind"]==inquiry_bonus_kind:
            breakdown[f"탐구 {i} 가산점"]=_trunc3(p*Decimal(".025"))
    total=sum(breakdown.values())
    return ScoreResult(total=float(_trunc3(total)),
                       breakdown={k:float(v) for k,v in breakdown.items()},
                       score_scale=1000.0)
