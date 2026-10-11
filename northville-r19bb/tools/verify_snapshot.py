"""Validate the Northville snapshot and (after deployment) its served bytes."""
import hashlib,json,re,sys,urllib.request,time
from pathlib import Path
from datetime import datetime
from itertools import groupby
from zoneinfo import ZoneInfo
from pypdf import PdfReader
root=Path(sys.argv[1]);base=sys.argv[2] if len(sys.argv)>2 else None
d=json.loads((root/'data/r19bb-archive.json').read_text());v=json.loads((root/'data/r19bb-verification.json').read_text());m=json.loads((root/'data/report-manifest.json').read_text());page=(root/'index.html').read_text()
assert d['station']==m['station']==v['station']=='AM.R19BB.00'
assert len(v['five_checks'])==5 and all(c['result']=='passed' for c in v['five_checks'])
assert hashlib.sha256((root/'data/r19bb-archive.json').read_bytes()).hexdigest()==v['archive_sha256']
assert set(d['channels'])=={'HDF','EHZ'}
for c in d['channels'].values():
 a=c['minutes'];assert len(a)==c['complete_minutes'] and len(a)==len({t for t,b in a})
 assert all(t%60==0 for t,b in a) and c['conflicting_samples']==0
h=d['channels']['HDF'];selected=[t for t,b in h['minutes'] if b=='4-8'];lengths=[len(list(g)) for _,g in groupby(enumerate(selected),key=lambda z:z[1]-z[0]*60)]
assert len(selected)==h['dominant_4_8_minutes']==352 and len(h['minutes'])==7371
assert max(lengths)==h['longest']['minutes']==7
assert {str(n):sum(l>=n for l in lengths) for n in [10,30,60]}==h['counts']
for report in m['reports'].values():
 p=root/'downloads'/report['filename'];assert p.read_bytes().startswith(b'%PDF-') and hashlib.sha256(p.read_bytes()).hexdigest()==report['sha256']
 assert report['filename']+'?v='+report['sha256'][:16] in page
 start=datetime.fromisoformat(report['start_utc']).timestamp();end=datetime.fromisoformat(report['end_exclusive_utc']).timestamp()
 a=[(t,b) for t,b in h['minutes'] if start<=t<end]
 assert len(a)==report['hdf']['complete_minutes'] and sum(b=='4-8' for t,b in a)==report['hdf']['dominant_4_8_minutes']
 txt=' '.join(p.extract_text() for p in PdfReader(p).pages);assert 'R19BB' in txt and 'ARCHIVED RECORDINGS' in txt
 assert not re.search('R6E8A|2709|2510170221',txt)
for p in root.rglob('*'):
 if p.suffix in ['.html','.json']:assert not re.search('R6E8A|Unit 2709|2510170221',p.read_text())
assert '7,371' in page and '352 complete minutes' in page and 'current reporting status unverified' in page
receipt={'station':d['station'],'checked_at_eastern':datetime.now(ZoneInfo('America/Detroit')).isoformat(),'snapshot_checks':'passed','served_files':[]}
if base:
 for p in sorted(root.rglob('*')):
  if not p.is_file():continue
  path=p.relative_to(root).as_posix();expected=p.read_bytes();ok=False
  for attempt in range(6):
   try:
    req=urllib.request.Request(base.rstrip('/')+'/'+path+'?verify='+str(time.time_ns()),headers={'Cache-Control':'no-cache','User-Agent':'Northville-R19BB-verification/1.0'})
    with urllib.request.urlopen(req,timeout=20) as resp:actual=resp.read();status=resp.status
    ok=actual==expected
    if ok:break
   except Exception as exc:err=str(exc)
   if attempt<5:time.sleep(10)
  receipt['served_files'].append({'path':path,'pass':ok,'expected_sha256':hashlib.sha256(expected).hexdigest(),'served_sha256':hashlib.sha256(actual).hexdigest() if 'actual' in locals() else None})
  assert ok,'Public file mismatch: '+path
 receipt['public_url']=base;receipt['all_served_files_match']=True
Path('r19bb-delivery-verification.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
