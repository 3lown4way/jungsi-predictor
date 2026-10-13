from app.scope import TOP_20, MEDICAL_FIELDS, in_scope, infer_medical_field
from app.scoring import compute



def record(university, department, selection_type='일반'):
    return {'university':university,'department':department,'selection_type':selection_type}


def test_target_universities_are_20_unique():
    assert len(TOP_20)==20
    assert len(set(TOP_20))==20
    assert all(in_scope(record(s,'일반 경영학과')) for s in TOP_20)
    assert not in_scope(record('상명대학교','컴퓨터과학전공'))


def test_medical_every_university_and_no_medical_near_names():
    positives=['의예과','치의예과','한의예과','약학과','수의예과',
               '의학부','치의학과','한의학과','제약학과','수의학과']
    assert all(in_scope(record('시험대학교',dep)) for dep in positives)
    negatives=['간호학과','의공학과','바이오의학과','약과학과', '약품생명공학과','의류학과']
    assert all(not in_scope(record('시험대학교',dep)) for dep in negatives)
    assert len(MEDICAL_FIELDS)==5
    assert infer_medical_field('의예과(일반)')=='medicine'


def test_non_general_admissions_excluded():
    assert not in_scope(record('서울대학교','의예과','지역인재'))
    assert not in_scope(record('서울대학교','경영학과','기회균형'))
