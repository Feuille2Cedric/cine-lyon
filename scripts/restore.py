"""Keep past showtimes from the previous public deployment, if available."""
import json
import os
from pathlib import Path
import requests
path=Path(__file__).resolve().parents[1]/'site/data/schedule.json'
try:
    response=requests.get(os.environ['PREVIOUS_DATA_URL'],timeout=20)
    response.raise_for_status()
    previous=response.json()
    current=json.loads(path.read_text(encoding='utf-8'))
    assert isinstance(previous['sessions'],list) and isinstance(previous['sources'],dict)
    if previous['generatedAt']>current['generatedAt']:
        path.write_text(json.dumps(previous,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        print('Programme publié restauré pour conserver les séances passées.')
except (requests.RequestException,ValueError,KeyError,AssertionError) as error:
    print('Utilisation du programme inclus dans le dépôt :',type(error).__name__)
