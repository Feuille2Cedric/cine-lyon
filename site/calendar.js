export function addDays(iso,n){const d=new Date(iso+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);}
export function monday(iso){return addDays(iso,-((new Date(iso+'T12:00:00Z').getUTCDay()+6)%7));}
export function civilMinutes(start){return Number(start.slice(11,13))*60+Number(start.slice(14,16));}
export function layoutSessions(sessions){
  const sorted=sessions.map(s=>({...s,minute:civilMinutes(s.start),length:s.duration||90})).sort((a,b)=>a.minute-b.minute||b.length-a.length||a.title.localeCompare(b.title));
  let group=[],end=-1;const output=[];
  function flush(){const ends=[];for(const e of group){let lane=ends.findIndex(t=>t<=e.minute);if(lane===-1)lane=ends.length;ends[lane]=e.minute+e.length;e.lane=lane;}for(const e of group)output.push({...e,lanes:ends.length});group=[];}
  for(const e of sorted){if(group.length&&e.minute>=end){flush();end=-1;}group.push(e);end=Math.max(end,e.minute+e.length);}flush();return output;
}
export function foldIcsLine(line){const encoder=new TextEncoder();let result='',current='',size=0;for(const c of line){const bytes=encoder.encode(c).length;if(size+bytes>75){result+=current+'\r\n';current=' ';size=1;}current+=c;size+=bytes;}return result+current;}
export function makeIcs(s,c){
  const escape=text=>String(text||'').replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
  const stamp=value=>new Date(value).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z');
  return ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Travelling//Lyon//FR','CALSCALE:GREGORIAN','BEGIN:VEVENT','UID:'+s.id+'@travelling-lyon','DTSTAMP:'+stamp(Date.now()),'DTSTART:'+stamp(s.start),'DTEND:'+stamp(new Date(s.start).getTime()+(s.duration||90)*60000),'SUMMARY:'+escape(s.title),'LOCATION:'+escape(c.name+' — '+c.address),'DESCRIPTION:'+escape((s.duration?'Fin estimée, hors publicités et échanges.':'Durée inconnue : créneau indicatif de 90 minutes.')+'\n'+s.url),'URL:'+s.url,'END:VEVENT','END:VCALENDAR'].map(foldIcsLine).join('\r\n')+'\r\n';
}
