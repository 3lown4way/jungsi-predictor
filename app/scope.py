"""입시 예측 프로젝트의 제한된 연구 범위.

'주요 20개'는 공인된 순위가 아니며 사용자와 조정할 수 있는 작업용 명단이다.
의·치·한·약·수는 학교에 관계없이 **면허 직결 모집단위**만 대상으로 한다.
간호학, 의공학, 약과학, 바이오의학 등 이름이 비슷한 비면허 학과는 제외한다.
"""
from __future__ import annotations
import re

TOP_20 = (
    '서울대학교', '연세대학교', '고려대학교', '서강대학교', '성균관대학교',
    '한양대학교', '중앙대학교', '경희대학교', '한국외국어대학교', '서울시립대학교',
    '이화여자대학교', '건국대학교', '동국대학교', '홍익대학교', '숙명여자대학교',
    '국민대학교', '숭실대학교', '세종대학교', '아주대학교', '인하대학교',
)
MEDICAL_FIELDS = {
    'medicine': '의예·의학',
    'dentistry': '치의예·치의학',
    'oriental_medicine': '한의예·한의학',
    'pharmacy': '약학',
    'veterinary': '수의예·수의학',
}
# 별도의 목록 없이 자동 감지할 수 있는 대표적인 정시 모집단위 표기.
# 실제 학과별 원문 검증 및 수동 분류가 우선한다.
MEDICAL_PREFIXES = (
    ('medicine', ('의예', '의학')),
    ('dentistry', ('치의예', '치의학')),
    ('oriental_medicine', ('한의예', '한의학')),
    ('pharmacy', ('약학', '제약학')),
    ('veterinary', ('수의예', '수의학')),
)
_SUFFIX = r'(?:과|부|학부|전공|계열)?(?:\s*\(|$)'


def infer_medical_field(department: str) -> str | None:
    name = re.sub(r'\s+', '', department or '')
    for field, prefixes in MEDICAL_PREFIXES:
        for prefix in prefixes:
            if re.match(r'^' + re.escape(prefix) + _SUFFIX, name):
                return field
    return None


def medical_field(program: dict) -> str | None:
    declared = program.get('medical_field')
    if declared in MEDICAL_FIELDS:
        return declared
    # 분류 값이 없는 이전 DB 레코드만 안전한 모집단위명으로 추론
    return infer_medical_field(program.get('department', ''))


def in_scope(program: dict) -> bool:
    # 정시 일반전형이 아닌 지역인재·기회균형 등을 혼동하여 학습하지 않는다.
    if program.get('selection_type', '일반') not in ('일반', None, ''):
        return False
    return program.get('university') in TOP_20 or medical_field(program) is not None


def scope_payload() -> dict:
    return {
        'start_year': 2022, 'latest_year': 2027,
        'admission_type': '정시 일반전형',
        'university_group': '주요 일반대학 20곳 (조정 가능한 연구용 목록, 순위가 아님)',
        'universities': list(TOP_20),
        'medical_categories': MEDICAL_FIELDS,
        'medical_coverage': '전국 대학의 의치한약수 면허 직결 모집단위 (대학 수 제한 없음)',
        'exclusions': '간호학과, 바이오의학, 의공학, 약과학 등 비면허 모집단위는 일반대학 20곳에 속하지 않는 한 제외',
        'warning': '명단에 포함됐다는 사실은 해당 연도 모집요강이나 입결 데이터가 수집됐다는 뜻이 아닙니다.'
    }
