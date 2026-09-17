"""Collect public screening schedules. No credentials or browser required."""
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import tz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'site' / 'data' / 'schedule.json'
PARIS = tz.gettz('Europe/Paris')
TODAY = datetime.now(PARIS).date()
NOW = datetime.now(PARIS).isoformat(timespec='seconds')
MONTHS = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
CINEMAS = [
    dict(id='pathe-bellecour',name='Pathé Bellecour',short='P. Bellecour',group='Pathé',color='#cb9b31',pale='#faf0d4',ink='#785717',url='https://www.pathe.fr/cinemas/cinema-pathe-bellecour',address='79 rue de la République, Lyon 2e'),
    dict(id='pathe-vaise',name='Pathé Vaise',short='P. Vaise',group='Pathé',color='#d78348',pale='#fae8d9',ink='#844a23',url='https://www.pathe.fr/cinemas/cinema-pathe-vaise',address='43 rue des Docks, Lyon 9e'),
    dict(id='pathe-soie',name='Pathé Carré de Soie',short='P. Carré de Soie',group='Pathé',color='#bcac42',pale='#f3f0d7',ink='#696020',url='https://www.pathe.fr/cinemas/cinema-pathe-carre-de-soie',address='Pôle de loisirs Carré de Soie, Vaulx-en-Velin'),
    dict(id='lumiere-bellecour',name='Lumière Bellecour',short='L. Bellecour',group='Cinémas Lumière',color='#c66b7b',pale='#f8e5e9',ink='#853a4b',url='https://www.cinemas-lumiere.com/programmation/lumiere-bellecour.html',address='12 rue de la Barre, Lyon 2e'),
    dict(id='lumiere-fourmi',name='Lumière Fourmi',short='L. Fourmi',group='Cinémas Lumière',color='#6b91bc',pale='#e6edf8',ink='#365a87',url='https://www.cinemas-lumiere.com/programmation/lumiere-fourmi.html',address='68 rue Pierre Corneille, Lyon 3e'),
    dict(id='lumiere-terreaux',name='Lumière Terreaux',short='L. Terreaux',group='Cinémas Lumière',color='#977bb2',pale='#efe8f6',ink='#65477e',url='https://www.cinemas-lumiere.com/programmation/lumiere-terreaux.html',address='40 rue du Président Édouard Herriot, Lyon 1er'),
    dict(id='institut',name='Institut Lumière',short='Institut Lumière',group='Indépendants',color='#729a8b',pale='#e4efe9',ink='#3e6e5b',url='https://www.institut-lumiere.org/calendrier',address='25 rue du Premier-Film, Lyon 8e'),
    dict(id='comoedia',name='Comœdia',short='Comœdia',group='Indépendants',color='#cf7862',pale='#f8e6df',ink='#944d38',url='https://www.cinema-comoedia.com/films/',address='13 avenue Berthelot, Lyon 7e'),
]
HTTP = requests.Session()
HTTP.headers.update({'User-Agent':'Travelling-Lyon/1.0 (public cinema calendar)', 'Accept-Language':'fr-FR,fr;q=0.9'})
HTTP.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1, status_forcelist=[429,500,502,503,504])))

def get(url, **kwargs):
    response = HTTP.get(url, timeout=40, **kwargs)
    response.raise_for_status()
    return response

def soup(url):
    return BeautifulSoup(get(url).content, 'html.parser')

def duration(text):
    m = re.search(r'(?<!\d)(\d{1,2})\s*h\s*(\d{1,2})?', str(text), re.I)
    if m:
        value = int(m[1])*60 + int(m[2] or 0)
        return value if 0 < value < 900 else None
    m = re.search(r'(\d+)\s*(?:min|mn)', str(text), re.I)
    return int(m[1]) if m else None

def genres(value):
    if not value:
        return []
    if isinstance(value, str):
        raw = re.split(r'[,/|]', value)
    else:
        raw = []
        for item in value:
            if isinstance(item, dict):
                raw.append(item.get('name') or item.get('label') or item.get('title') or '')
            else:
                raw.append(str(item))
    result = []
    for item in raw:
        name = re.sub(r'\s+', ' ', str(item)).strip(' .;-')
        if name and name.lower() not in {g.lower() for g in result}:
            result.append(name)
    return result

def screening(cinema, title, start, minutes, url, version='', extra='', identity='', movie_genres=None):
    date = datetime.fromisoformat(start.replace('Z','+00:00'))
    date = date.replace(tzinfo=PARIS) if date.tzinfo is None else date.astimezone(PARIS)
    stable = '|'.join([cinema,title,date.isoformat(),version,identity])
    return dict(id=hashlib.sha256(stable.encode()).hexdigest()[:18],cinema=cinema,title=title.strip(),start=date.isoformat(timespec='seconds'),duration=minutes,url=url,version=version,extra=extra,genres=genres(movie_genres))

def extract_genres_from_text(text):
    patterns = [
        r'Genres?\s*:\s*([^|•\n\r]+)',
        r'Genre\s*:\s*([^|•\n\r]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            chunk = re.split(r'\s{2,}|Durée|Année|Nationalité|De\s+', match[1], maxsplit=1)[0]
            return genres(chunk)
    return []

def ticket(item, fallback):
    entries = (item.get('data') or {}).get('ticketing') or []
    entries = sorted(entries, key=lambda x: x.get('provider') != 'default')
    return next((u for entry in entries for u in entry.get('urls',[]) if u.startswith('https://')), fallback)

def language(tags):
    if 'Localization.Version.Original' in tags:
        return 'VOST' if 'Showtime.Accessibility.Subtitled' in tags else 'VO'
    return 'VF' if 'Localization.Language.French' in tags else ''

def collect_lumiere():
    base='https://www.cinemas-lumiere.com/calendrier-general.html'
    first=soup(base)
    pages=[(base, first)]
    # Include the preceding cinema week to fill Monday and Tuesday where published.
    wednesday=TODAY-timedelta(days=(TODAY.weekday()-2)%7)
    for offset in (-7,7,14,21):
        url=base+'?week='+str(wednesday+timedelta(days=offset))
        pages.append((url,soup(url)))
    events=[]; days=set(); durations={}
    for page_url, page in pages:
        table=page.select_one('table.schedule')
        if not table:
            raise ValueError('Calendrier Lumière introuvable')
        days.update(t['datetime'][:10] for t in table.select('tr.days time[datetime]'))
        cinema=None
        for row in table.select('tr'):
            if 'cinema' in row.get('class',[]):
                use=row.find('use')
                logo=str(use)
                cinema=next(('lumiere-'+n for n in ['terreaux','bellecour','fourmi'] if 'logo-'+n in logo),None)
            if 'movie' not in row.get('class',[]) or not cinema:
                continue
            anchor=row.select_one('.movie-title a')
            title=anchor.get_text(' ',strip=True); film_url=anchor['href']
            if film_url not in durations:
                try:
                    text=soup(film_url).get_text(' ',strip=True)
                    match=re.search(r'Durée\s*:\s*(\d+h\d+)',text)
                    durations[film_url]=(duration(match[1]) if match else None, extract_genres_from_text(text))
                except requests.RequestException:
                    durations[film_url]=(None, [])
                time.sleep(.08)
            for slot in row.select('time.session[datetime]'):
                a=slot.find('a'); v=slot.select_one('.version')
                film_duration, film_genres = durations[film_url]
                events.append(screening(cinema,title,slot['datetime'],film_duration,a['href'] if a else film_url,v.get_text(strip=True) if v else '',movie_genres=film_genres))
    return events, sorted(days), 'Cinémas Lumière', base

def parse_institut(page, url):
    title=page.find('h1').get_text(' ',strip=True)
    year=int(re.search(r'20\d{2}',title)[0])
    result=[]; days=set()
    for heading in page.select('h2'):
        text=heading.get_text(' ',strip=True).lower()
        match=re.search(r'(\d{1,2})(?:er)?\s+('+'|'.join(MONTHS)+')',text)
        if not match:
            continue
        day=datetime(year,MONTHS.index(match[2])+1,int(match[1])).date().isoformat()
        days.add(day)
        for article in heading.parent.select('article'):
            copy=BeautifulSoup(str(article),'html.parser')
            for strong in copy.select('strong'):
                clock=re.fullmatch(r'(\d{1,2})h(\d{2})?',strong.get_text(strip=True))
                if clock:
                    strong.replace_with('|||'+clock[1].zfill(2)+':'+(clock[2] or '00')+'|||')
            parts=re.split(r'\|\|\|(\d{2}:\d{2})\|\|\|',str(copy))
            for i in range(1,len(parts),2):
                fragment=BeautifulSoup(parts[i+1],'html.parser')
                anchors=fragment.select('a')
                anchor=next((a for a in anchors if a.find('i')),anchors[0] if anchors else None)
                if anchor is None:
                    continue
                name=anchor.get_text(' ',strip=True)
                following=str(fragment).split(str(anchor),1)[-1]
                remaining=BeautifulSoup(following,'html.parser').get_text(' ',strip=True)
                film_duration=duration(remaining)
                context=fragment.get_text(' ',strip=True)
                version='VF' if 'SÉANCE ENFANTS' in context or 'TOUT-PETITS' in context else ''
                result.append(screening('institut',name,day+'T'+parts[i]+':00',film_duration,urljoin(url,anchor['href']),version,context,movie_genres=extract_genres_from_text(context)))
    if not days:
        raise ValueError('Aucune date trouvée dans le calendrier Institut Lumière')
    return result,days

def collect_institut():
    url='https://www.institut-lumiere.org/calendrier'
    page=soup(url)
    events,days=parse_institut(page,url)
    links={urljoin(url,a['href']) for a in page.select('a[href]') if 'Voir les séances du mois' in a.get_text()}
    for link in sorted(links):
        try:
            extra,extra_days=parse_institut(soup(link),link)
            events.extend(extra); days.update(extra_days)
        except (requests.RequestException,ValueError,AttributeError,TypeError):
            pass
    return events,sorted(days),'Institut Lumière',url

def collect_comoedia():
    base='https://www.cinema-comoedia.com/api/gatsby-source-boxofficeapi/'
    start=TODAY-timedelta(days=TODAY.weekday())
    end=start+timedelta(days=35)
    params={'from':str(start)+'T00:00:00','includeAllMovies':'true','theaters':json.dumps({'id':'P3757','timeZone':'Europe/Paris'},separators=(',',':')),'to':str(end)+'T00:00:00'}
    data=get(base+'schedule',params=params).json()['P3757']['schedule']
    ids=list(data); movies={}
    for i in range(0,len(ids),40):
        batch=get(base+'movies',params={'basic':'false','castingLimit':0,'ids':ids[i:i+40]}).json()
        movies.update({m['id']:m for m in batch})
    events=[]
    for movie_id,schedule in data.items():
        movie=movies.get(movie_id)
        if not movie:
            raise ValueError('Métadonnées Comœdia manquantes pour '+movie_id)
        for day,slots in schedule.items():
            for item in slots:
                tags=item.get('tags',[])
                events.append(screening('comoedia',movie['title'],item['startsAt'],round(movie['runtime']/60) if movie.get('runtime') else None,ticket(item,'https://www.cinema-comoedia.com/films/'),language(tags),(item.get('screen') or {}).get('name',''),item['id'],movie.get('genres') or movie.get('genre')))
    return events,[(start+timedelta(days=d)).isoformat() for d in range(35)],'Comœdia','https://www.cinema-comoedia.com/films/'

def repair_allocine_movies(data, cache):
    for row in data.get('results') or []:
        if row.get('movie'):
            continue
        match=re.search(r'gid_entity=movie\.movie\._\.(\d+)',json.dumps(row))
        if not match:
            raise ValueError('Séance sans titre ni identifiant film')
        movie_id=match[1]
        if movie_id not in cache:
            try:
                page=soup('https://www.allocine.fr/film/fichefilm_gen_cfilm='+movie_id+'.html')
                title=page.select_one('.titlebar-title')
                info=page.select_one('.meta-body-info')
                cache[movie_id]={'title':title.get_text(' ',strip=True) if title else 'Séance · titre non communiqué','runtime':info.get_text(' ',strip=True) if info else '','genres':extract_genres_from_text(page.get_text(' ',strip=True))}
            except requests.RequestException:
                # A removed movie record must not hide the rest of a cinema's week.
                cache[movie_id]={'title':'Séance · titre non communiqué','runtime':'','genres':[]}
        row['movie']=cache[movie_id]

def parse_allocine(data, cinema, source_url):
    events=[]
    if data.get('error'):
        raise ValueError('Erreur de programme AlloCiné')
    for result in data.get('results') or []:
        movie=result['movie']
        for group,slots in result['showtimes'].items():
            for item in slots:
                tags=item.get('tags',[])
                extra=' · '.join((item.get('experience') or [])+(item.get('projection') or []))
                events.append(screening(cinema,movie['title'],item['startsAt'],duration(movie.get('runtime','')),ticket(item,source_url),language(tags),extra,str(item['internalId']),movie.get('genres') or movie.get('genre')))
    return events

def collect_pathe(cinema, theater):
    source='https://www.allocine.fr/seance/salle_gen_csalle='+theater+'.html'
    page=soup(source)
    block=page.select_one('#theaterpage-showtimes-index-ui')
    if block is None:
        raise ValueError('Calendrier Pathé indisponible sur AlloCiné')
    dates=json.loads(block['data-showtimes-dates'])
    end=TODAY+timedelta(days=28)
    dates=[d for d in dates if str(TODAY)<=d<str(end)]
    events=[]; movie_cache={}
    for day in dates:
        endpoint='https://www.allocine.fr/_/showtimes/theater-'+theater+'/d-'+day+'/'
        data=get(endpoint).json()
        repair_allocine_movies(data,movie_cache)
        events.extend(parse_allocine(data,cinema,source))
        for number in range(2,(data.get('pagination') or {}).get('totalPages',1)+1):
            more=get(endpoint+'p-'+str(number)+'/').json()
            if int(more['pagination']['page'])!=number:
                raise ValueError('Pagination des séances non respectée')
            repair_allocine_movies(more,movie_cache)
            events.extend(parse_allocine(more,cinema,source))
        time.sleep(.15)
    return events,dates,'AlloCiné · programme Pathé',source

def main():
    previous=json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else {'sessions':[],'sources':{}}
    sessions=previous['sessions']; statuses=previous.get('sources',{})
    jobs=[(['lumiere-bellecour','lumiere-fourmi','lumiere-terreaux'],collect_lumiere),(['institut'],collect_institut),(['comoedia'],collect_comoedia)]
    for cinema,theater in [('pathe-bellecour','P0012'),('pathe-vaise','P6909'),('pathe-soie','P8507')]:
        jobs.append(([cinema],lambda c=cinema,t=theater:collect_pathe(c,t)))
    successes=0
    for cinema_ids,collector in jobs:
        try:
            incoming,days,label,url=collector()
            if not incoming:
                raise ValueError('Source sans séance : ancienne collecte conservée')
            # Replace fetched dates atomically; keep past days not exposed by the source.
            day_set=set(days)
            sessions=[s for s in sessions if s['cinema'] not in cinema_ids or s['start'][:10] not in day_set]
            sessions.extend(incoming)
            for cinema in cinema_ids:
                statuses[cinema]=dict(status='ok',updatedAt=NOW,checkedAt=NOW,label=label,url=url,days=days,count=sum(s['cinema']==cinema for s in incoming))
            print('OK',','.join(cinema_ids),len(incoming),'séances',flush=True)
            successes+=1
        except Exception as error:
            for cinema in cinema_ids:
                statuses[cinema]={**statuses.get(cinema,{}),'status':'error','checkedAt':NOW,'message':'Actualisation indisponible ; dernier programme conservé.'}
            print('ERROR',','.join(cinema_ids),str(error)[:300],file=sys.stderr,flush=True)
    cutoff=str(TODAY-timedelta(days=35))
    sessions=list({s['id']:s for s in sessions if s['start'][:10]>=cutoff}.values())
    sessions.sort(key=lambda s:(s['start'],s['cinema'],s['title']))
    payload=dict(generatedAt=NOW,timezone='Europe/Paris',cinemas=CINEMAS,sources=statuses,sessions=sessions)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUTPUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temp.replace(OUTPUT)
    print('TOTAL',len(sessions),'séances ;',successes,'collecteurs disponibles',flush=True)
    if not sessions:
        raise SystemExit('Aucune donnée publiable')

if __name__=='__main__':
    main()
