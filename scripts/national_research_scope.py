"""Complete research queue, distinct from verified historical weighted admission scores."""
import json
from pathlib import Path
from app.scope import TOP_20

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'data/public/historical_admissions/top20_research_2022_2026.json'
FIELDS=ROOT/'data/public/historical_admissions/national_medical_research.json'
STATUSES={
'year_specific_official_document_not_yet_located',
'year_selectable_official_archive',
'year_listed_in_official_guide_archive',
'year_listed_in_official_admissions_notices',
'official_2026_full_guide_pdf','official_2025_full_guide_pdf',
'official_2024_full_guide_pdf',
'official_2026_guide_notice_with_attachment',
'official_year_guide_from_prior_research',
'official_archive_listing_from_prior_research',
'year_selectable_adiga_university_profile'
}

def read_research():
    rows=json.loads(REGISTRY.read_text(encoding='utf-8'))
    keys={(r['year'],r['university']) for r in rows}
    wanted={(year,uni) for year in range(2022,2027) for uni in TOP_20}
    if len(rows)!=100 or keys!=wanted:
        raise ValueError('20 university × 5 academic years must be complete and unique')
    for r in rows:
        if r['guide_status'] not in STATUSES:
            raise ValueError('unknown provenance status')
        known=r['guide_status']!='year_specific_official_document_not_yet_located'
        if known and not (r['official_guide_url'] or '').startswith('https://'):
            raise ValueError('official source missing')
        if not known and r['official_guide_url'] is not None:
            raise ValueError('unverified URLs may not be fabricated')
        if r['complete_formula_approved'] or r['public_admissions_prediction_ready']:
            raise ValueError('source URL is not a complete weighted conversion formula')
    return rows

def read_medical_candidates():
    data=json.loads(FIELDS.read_text(encoding='utf-8'))
    medicine=data['faculty_candidates']['medicine']
    veterinary=data['faculty_candidates']['veterinary']
    if len(medicine)!=40 or len(veterinary)!=10:
        raise ValueError('medical and veterinary research roster count mismatch')
    for category,entries in (('medicine',medicine),('veterinary',veterinary)):
        if len({x['university'] for x in entries})!=len(entries):
            raise ValueError('duplicate faculty institution in '+category)
        for row in entries:
            if row['medical_field']!=category or not row['list_source_url'].startswith('https://'):
                raise ValueError('invalid national medical research metadata')
            if row['verified_2027_regular_admission'] is not False or row['year_specific_2022_2026_guides_loaded'] is not False:
                raise ValueError('candidate institutions are not verified admission programmes')
    if set(data['incomplete_rosters'])!={'dentistry','oriental_medicine','pharmacy'}:
        raise ValueError('partial medical scope falsely claimed complete')
    return data

def summary():
    rows=read_research()
    med=read_medical_candidates()
    return {'reviewed_universities':len({r['university'] for r in rows}),
            'target_university_year_pairs':len(rows),
            'historical_year_links_found':sum(r['official_guide_url'] is not None for r in rows),
            'historical_year_links_missing':sum(r['official_guide_url'] is None for r in rows),
            'complete_historical_formulas_from_inventory':0,
            'national_medical_faculty_research_candidates':len(med['faculty_candidates']['medicine']),
            'national_veterinary_faculty_research_candidates':len(med['faculty_candidates']['veterinary']),
            'remaining_unverified_medical_rosters':list(med['incomplete_rosters']),
            'note':'대학별 학년도별 원문 링크 수집률; 모집단위·환산식·입결 학습 완료율 아님.'}
