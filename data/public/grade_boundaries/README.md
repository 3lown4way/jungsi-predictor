# 확정 등급 경계점수 입력 디렉터리

연도별 **확정** 평가원 채점자료만 CSV로 검수하여 이 폴더에 넣습니다. 원본 문제지 자체에는 등급컷이 없습니다.

필수 열:
`year,exam_type,bundle_id,area,subject,grade,std_score_floor,percentile_floor,kind,math_track,source_url`

- `exam_type`: `june`, `september`, `csat`
- `area`: `korean`, `math`, `inquiry1`, `inquiry2`. 동일 `bundle_id`는 실제 과목 조합 하나를 지정합니다.
- `grade`: 1~9 등급. `std_score_floor`는 경계 표준점수, `percentile_floor`는 **공식 확인된 경계 백분위**만 기입합니다. 일괄 등급/백분위 표(1등급 96 등)를 임의로 대입하지 않습니다.
- 국어/수학 선택과목, 두 탐구의 실제 과목별 등급컷에 출처를 붙이세요. `kind`는 탐구에서 `social` / `science`, 수학의 `math_track`은 `calculus` / `probability` / `geometry`입니다.
- 한 번에 가상의 `bundle_id`로 여러 과목을 결합해선 안 됩니다. 실제 구성된 과목 조합이라고 명시한 연구 시나리오임을 별도 검증합니다.
- 대학별 산식이 백분위를 요구하는 경우 **공식 `percentile_floor`가 누락되면 계산하지 않습니다.** 표준점수를 요구하는 산식 플러그인은 추후 별도 구현해야 합니다.

이 폴더에 CSV가 없다면 계산 결과는 0건입니다. 이는 무단 추정치 생성보다 바람직한 상태입니다.
