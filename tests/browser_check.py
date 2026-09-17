"""Run against a local or deployed site; requires pip install playwright."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

url=os.environ.get('TEST_URL','http://127.0.0.1:8765/')
with sync_playwright() as p:
    channel=os.environ.get('TEST_BROWSER','msedge' if os.name=='nt' else 'chromium')
    browser=p.chromium.launch(channel=None if channel=='chromium' else channel,headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url,wait_until='networkidle')
    page.wait_for_selector('.session')
    assert page.locator('.cinema-row').count()==8
    assert page.locator('.day-header').count()==7
    assert page.locator('#genre').is_visible()
    print('Initial:',page.locator('#count').inner_text())
    results=page.evaluate('''async () => {
      const {layoutSessions,monday,addDays,makeIcs,foldIcsLine}=await import('./calendar.js');
      const s=(id,start,duration)=>({id,title:id,start:'2026-09-16T'+start+':00+02:00',duration});
      const a=layoutSessions([s('a','10:00',120),s('b','10:30',60),s('c','11:30',30),s('d','12:00',60)]);
      const assert=(c,m)=>{if(!c)throw Error(m)};
      assert(a[0].lanes===2 && a[1].lane===1 && a[2].lane===1 && a[3].lanes===1,'overlap groups');
      assert(monday('2027-01-01')==='2026-12-28','year boundary');
      assert(addDays('2026-03-29',1)==='2026-03-30','DST civil date');
      const ics=makeIcs({...s('x','23:30',120),title:'Film, test; é',url:'https://example.org/'},{name:'Cinéma',address:'Lyon'});
      assert(ics.includes('DTSTART:20260916T213000Z') && ics.includes('DTEND:20260916T233000Z'),'UTC export');
      assert(foldIcsLine('é'.repeat(100)).split('\\r\\n').every(l=>new TextEncoder().encode(l).length<=75),'UTF8 fold');
      const buttons=[...document.querySelectorAll('.session')];
      assert(buttons.every(b=>b.getBoundingClientRect().width>20),'card widths');
      return 'Layout, DST, ICS and widths OK';
    }''')
    print(results)
    artifacts=Path('test-artifacts');artifacts.mkdir(exist_ok=True)
    page.screenshot(path=str(artifacts/'desktop.png'))
    page.locator('.session').first.click()
    assert page.locator('#details').is_visible()
    assert page.locator('#detail-title').inner_text()
    assert 'genre' in page.locator('.detail-meta').inner_text().lower()
    with page.expect_download() as download:
        page.locator('#export-ics').click()
    assert download.value.suggested_filename.endswith('.ics')
    page.keyboard.press('Escape')
    if page.locator('.overflow-button').count():
        page.locator('.overflow-button').first.click()
        assert page.locator('#details .list-session').count()>0
        page.locator('#details .list-session').first.click()
        assert page.locator('#export-ics').is_visible()
        page.keyboard.press('Escape')
    page.locator('#toggle-all').click()
    assert page.locator('#empty').is_visible()
    page.locator('#reset').click()
    page.locator('#search').fill('zzzzzz-no-film')
    page.wait_for_timeout(200)
    assert page.locator('#empty').is_visible()
    page.locator('#search').fill('')
    page.wait_for_timeout(200)
    page.locator('[data-view=list]').click()
    assert page.locator('.list-session').count()>0
    page.locator('[data-view=day]').click()
    assert page.locator('.day-header').count()==1
    page.locator('[data-view=week]').click()
    before=page.locator('#range').inner_text();page.locator('#next').click()
    assert before!=page.locator('#range').inner_text()
    page.locator('#today').click()
    page.locator('#version').select_option('VO')
    assert all(t.startswith('VO') for t in page.locator('.session-version').all_text_contents())
    page.locator('#version').select_option('')
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(artifacts/'mobile.png'))
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    page.locator('[data-view=list]').click()
    page.screenshot(path=str(artifacts/'mobile-list.png'))
    # A remote viewer must still see Lyon dates and times.
    foreign=browser.new_context(timezone_id='America/Los_Angeles')
    other=foreign.new_page();other.goto(url,wait_until='networkidle')
    assert other.locator('#date').input_value()==page.locator('#date').input_value()
    foreign.close()
    assert not errors,errors
    context.close()
    page=None
    browser.close()
    print('PASS: desktop, mobile, all filters, navigation, details, overflow, ICS, timezone; no JS errors')
