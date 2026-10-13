"""공개 정적 스냅샷 빌드. 사용: python -m scripts.build_pages --output site

GitHub Pages는 FastAPI를 실행하지 않는다. 공식 공개 모집단위 스냅샷만 배포하며
실측 지원자 자료와 모델 파일은 애초에 읽지 않는다.
"""
import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(output: Path, api_base_url: str = ''):
    if api_base_url and not re.fullmatch(r'https://[^/\s]+(?:/[^\s]*)?', api_base_url):
        raise ValueError('PUBLIC_API_BASE_URL은 공개 HTTPS URL이어야 합니다.')
    # 외부 환경변수/로컬 DB를 강제로 무시하여 고객 개인 DB 게시 위험 차단.
    with tempfile.TemporaryDirectory(prefix='admission-pages-') as working:
        os.environ['ADMISSION_DB'] = str(Path(working) / 'public.sqlite3')
        from app import database
        database.DB = Path(os.environ['ADMISSION_DB'])
        from scripts.public_data import load
        from fastapi.testclient import TestClient
        from app.main import app
        imported = load()
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / 'app' / 'static', output / 'static', dirs_exist_ok=True)
        page = (ROOT / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')
        page = page.replace('/static/', './static/')
        page = page.replace('RESEARCH BUILD · v0.2', 'GITHUB ACTIONS · v0.3')
        page = page.replace('href="./static/outcomes_template.csv"', 'href="./static/outcomes_template.csv"')
        (output / 'index.html').write_text(page, encoding='utf-8')
        (output / '.nojekyll').write_text('', encoding='utf-8')
        config = {'staticMode': True, 'apiBaseUrl': api_base_url.rstrip('/')}
        (output / 'static' / 'config.js').write_text('window.ADMISSION_SITE_CONFIG = '+json.dumps(config, ensure_ascii=False)+';\n', encoding='utf-8')
        data_dir = output / 'data'; data_dir.mkdir(exist_ok=True)
        with TestClient(app) as client:
            endpoints = {'meta': '/api/meta', 'scope': '/api/scope', 'backtest': '/api/backtest'}
            for name, path in endpoints.items():
                response = client.get(path); response.raise_for_status()
                result = response.json()
                if name == 'backtest':
                    # 정적 GitHub Pages 공개 화면에는 개인정보 기반 모형 결과 미출력.
                    assert result['count'] == 0
                write_json(data_dir / f'{name}.json', result)
            for year in range(2022, 2028):
                response=client.get('/api/programs', params={'year': year})
                response.raise_for_status()
                write_json(data_dir / f'programs-{year}.json', response.json())
        write_json(data_dir / 'build-info.json', {
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'imported_public_csv_count': len(imported),
            'note': '자동 모니터링이 공식 입시 자료의 갱신이나 실측 합불 학습을 의미하지 않습니다.',
            'live_api_configured': bool(api_base_url)
        })
    return output


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='site')
    parser.add_argument('--api-base-url',default=os.environ.get('PUBLIC_API_BASE_URL',''))
    args=parser.parse_args()
    print('정적 사이트 생성:',run(Path(args.output), args.api_base_url))
