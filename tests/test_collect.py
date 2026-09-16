import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect import duration,screening,parse_institut,parse_allocine

class CollectorTests(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(duration('1h 47min'),107)
        self.assertEqual(duration('77mn'),77)
        self.assertIsNone(duration('non communiquée'))

    def test_paris_timezone(self):
        summer=screening('c','Film','2026-07-01T21:00:00',90,'https://example.org')
        winter=screening('c','Film','2026-12-01T21:00:00',90,'https://example.org')
        self.assertTrue(summer['start'].endswith('+02:00'))
        self.assertTrue(winter['start'].endswith('+01:00'))

    def test_institut_multiple_screenings_and_not_film_duration_as_start(self):
        html='''<h1>Calendrier septembre 2026</h1><div><h2>Mercredi 16 septembre</h2><article><p><strong>14h30</strong> ENFANTS <a href="/film"><i>Film A</i></a> (77mn)<br><strong>16h</strong> CINÉ-CLUB <a href="/film2"><i>Film B</i></a> (Réalisateur, 1h45)</p></article></div>'''
        events,days=parse_institut(BeautifulSoup(html,'html.parser'),'https://www.institut-lumiere.org/calendrier')
        self.assertEqual(len(events),2)
        self.assertEqual([e['duration'] for e in events],[77,105])
        self.assertEqual(events[1]['start'],'2026-09-16T16:00:00+02:00')
        self.assertEqual(days,{'2026-09-16'})

    def test_pathe_versions_and_booking(self):
        event={'internalId':1,'startsAt':'2026-09-20T10:40:00','tags':['Localization.Version.Original','Showtime.Accessibility.Subtitled'],'data':{'ticketing':[{'provider':'default','urls':['https://s.pathe.fr/fr/booking']}]}}
        payload={'results':[{'movie':{'title':'Film','runtime':'1h 47min'},'showtimes':{'original_st':[event]}}]}
        result=parse_allocine(payload,'pathe-bellecour','https://www.allocine.fr')
        self.assertEqual(result[0]['version'],'VOST')
        self.assertEqual(result[0]['duration'],107)
        self.assertEqual(result[0]['url'],'https://s.pathe.fr/fr/booking')
        self.assertEqual(parse_allocine({'results':None},'c','https://example.org'),[])

if __name__=='__main__':unittest.main()
