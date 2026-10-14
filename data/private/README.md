# 비공개 과거 9평 성적→대학별 실제 지원·합격 데이터

Supabase 비공개 테이블 \`public.historical_mock_outcomes\`으로 관리합니다.
대학별 공식 반영비는 이 테이블에 저장하지 않고 **해당 학년도의 공식 대학 모집단위 자료**
\`data/public/programs/*.csv\`에 검수·등록합니다.

1. 본 SQL을 Supabase SQL Editor에 실행하고 비공개 테이블을 생성합니다.
2. 개인 동의와 실제 지원·합격 증빙을 확인한 2022~2026학년도 9평 성적 기록만 적재합니다.
3. 저장소 Actions Secrets에서 \`SUPABASE_URL\`, \`SUPABASE_SERVICE_ROLE_KEY\` 설정.
4. Actions의 \`Train 2027 admission model from verified historical university weights\` 수동 실행.
5. 2025·2026 홀드아웃 기준을 통과한 모집단위만 \`data/public/models/historical-2027.json\`으로 공개 커밋됩니다.

원본 파일은 GitHub Actions 러너 임시 폴더에서만 사용되며 종료 전 삭제됩니다.
개인 성적·해시·입학 결과 원자료를 공개 GitHub, Pages, 로그, 아티팩트에 게시하지 않습니다.

\`service_role\` 키는 **절대 사이트 JS·공개 저장소·사용자 브라우저에 넣으면 안 됩니다**.
