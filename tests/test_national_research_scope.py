from scripts.national_research_scope import read_research,read_medical_candidates,summary


def test_top20_all_2022_to_2026_slots_without_fabricated_urls():
    rows=read_research()
    assert len(rows)==100
    assert {(r['university'],r['year']) for r in rows}=={
      (r['university'],year) for year in range(2022,2027) for r in rows if r['year']==2026}
    assert sum(r['official_guide_url'] is None for r in rows)==8
    assert sum(r['guide_status']=='official_adiga_year_profile_selector_not_downloaded_pdf' for r in rows)>=30
    assert all(r['complete_formula_approved'] is False for r in rows)
    assert len([r for r in rows if r['university']=='서울대학교' and r['official_guide_url']])==5
    assert sum(r['guide_status']=='year_selectable_adiga_university_profile' for r in rows)==6
    assert all(not r['weights_verified'] and not r['complete_formula_approved'] for r in rows)
    assert sum(r['official_guide_url'] is not None for r in rows)==summary()['historical_year_links_found']


def test_hanyang_historical_2022_2026_selector_is_year_specific():
    rows=read_research()
    a=[r for r in rows if r['university']=='한양대학교']
    assert len(a)==5
    assert all(f"m_year={r['year']}" in r['official_guide_url'] for r in a)
    assert all(r['guide_status']=='year_selectable_official_archive' for r in a)


def test_national_medical_is_research_scope_not_false_2027_enrolment_claim():
    data=read_medical_candidates()
    assert len(data['faculty_candidates']['medicine'])==40
    assert len(data['faculty_candidates']['veterinary'])==10
    assert {'medicine','veterinary'}==set(data['faculty_candidates'])
    assert {'dentistry','oriental_medicine','pharmacy'}==set(data['incomplete_rosters'])
    assert all(not r['verified_2027_regular_admission'] for group in data['faculty_candidates'].values() for r in group)
