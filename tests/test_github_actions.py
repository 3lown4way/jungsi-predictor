"""배포할 스냅샷의 경로와 개인정보 보호 불변조건 테스트."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_static_export_no_raw_personal_outcomes(tmp_path):
    site=tmp_path/'site'
    env={**os.environ, 'ADMISSION_DB':str(tmp_path/'sensitive-local-db.sqlite3')}
    result=subprocess.run([sys.executable,'-m','scripts.build_pages','--output',str(site)],
                          cwd=ROOT,env=env,capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    html=(site/'index.html').read_text(encoding='utf-8')
    assert 'href="./static/styles.css"' in html
    assert 'src="./static/config.js"' in html
    assert 'src="./static/app.js"' in html
    assert 'href="/static/' not in html
    assert (site/'static'/'config.js').exists()
    meta=json.loads((site/'data'/'meta.json').read_text())
    assert meta['application_outcomes']==0
    for entry in (site/'data').glob('programs-*.json'):
        assert isinstance(json.loads(entry.read_text()),list)
    assert not list(site.rglob('*.sqlite3'))
    assert not list(site.rglob('actual_applications.csv'))


def test_public_csv_directory_starts_empty():
    # 초기에 공식 검증 없이 실측 합격확률을 임의 구성하지 않음
    # 공개 데이터는 언제든 검수된 CSV를 추가할 수 있으며 이 테스트는 그것을 막지 않음
    assert (ROOT/'data'/'public'/'programs').is_dir()


def test_workflow_configuration_exists():
    for name in ('ci.yml','pages.yml','data-audit.yml'):
        assert (ROOT/'.github'/'workflows'/name).is_file()
