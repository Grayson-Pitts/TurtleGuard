"""Import recognizable Mote weekly summary tables from PDFs into existing weekly CSV.
Uses PyMuPDF (pymupdf). Duplicate reports are safe to re-import.
Unexpected layouts/conflicting values are skipped and reported, never overwritten.
"""
import argparse, csv, re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import fitz

COLS=['location','year','period_start','period_end','frequency','species','nests','false_crawls','source_file','status']
LOCATIONS={'Longboat Key Manatee':'Longboat Key (Manatee)','Longboat Key Sarasota':'Longboat Key (Sarasota)', 'Lido Beach':'Lido Key','Siesta Key':'Siesta Key','Casey Key':'Casey Key','Venice':'Venice'}
WEEK_HEADING=re.compile(r'^\s*Weekly Summary\s*-\s*(20\d\d)\s*$', re.I|re.M)
PERIOD=re.compile(r'For the week of\s*(\d{1,2}-[A-Za-z]{3})\s+thru\s+(\d{1,2}-[A-Za-z]{3})',re.I)
ITEM=re.compile(r'^\s*(Longboat Key Manatee|Longboat Key Sarasota|Lido Beach|Siesta Key|Casey Key|Venice)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',re.I|re.M)

def key(row):return (row['location'],row['year'],row['period_start'],row['period_end'],row['species'])
def records(pdf):
    with fitz.open(pdf) as doc: content='\n'.join(page.get_text(sort=True) for page in doc)
    headings=list(WEEK_HEADING.finditer(content))
    if not headings: raise ValueError('No recognizable Weekly Summary section; PDF may be scanned or different format')
    outputs=[]
    for i, h in enumerate(headings):
        block=content[h.end():headings[i+1].start() if i+1<len(headings) else len(content)]
        # stop before cumulative so we're importing weekly increments only
        block=re.split(r'Cumulative\s+(?:Totals|Summary)',block,maxsplit=1,flags=re.I)[0]
        period=PERIOD.search(block)
        if not period:raise ValueError(f'Missing weekly dates for {h.group(1)}')
        year=int(h.group(1))
        start=datetime.strptime(f'{period.group(1)}-{year}', '%d-%b-%Y').date()
        end=datetime.strptime(f'{period.group(2)}-{year}', '%d-%b-%Y').date()
        if end<start:end=datetime.strptime(f'{period.group(2)}-{year+1}', '%d-%b-%Y').date()
        if (end-start).days!=6:raise ValueError(f'Invalid weekly range {start} to {end}')
        matches=ITEM.findall(block)
        if len(matches)!=6:raise ValueError(f'Expected 6 monitored locations for {year} {start}, found {len(matches)}')
        for loc,ln,lf,gn,gf in matches:
            for species,n,fc in [('loggerhead',ln,lf),('green',gn,gf)]:
                outputs.append(dict(location=LOCATIONS[loc],year=str(year),period_start=str(start),period_end=str(end),frequency='weekly',species=species,nests=str(int(n)),false_crawls=str(int(fc)),source_file=pdf.name,status='observed_weekly'))
    return outputs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--incoming',default='data/incoming_reports');ap.add_argument('--output',default='data/mote_weekly_2007_2008.csv');a=ap.parse_args()
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);incoming=Path(a.incoming);incoming.mkdir(parents=True,exist_ok=True)
    existing={}
    if out.exists():
        with out.open(newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):existing[key(r)]=r
    added=0; issues=[]
    files=sorted(incoming.rglob('*.pdf'))
    for pdf in files:
        try:
            new=records(pdf)
            conflicts=[]
            for r in new:
                old=existing.get(key(r))
                if old and (int(float(old['nests']))!=int(r['nests']) or int(float(old.get('false_crawls') or 0))!=int(r['false_crawls'])):
                    conflicts.append(f"{r['location']} {r['period_end']} {r['species']}: existing={old['nests']}, new={r['nests']}")
            if conflicts:raise ValueError('Conflicting records; no rows imported from report: '+'; '.join(conflicts[:4]))
            for r in new:
                if key(r) not in existing:existing[key(r)]=r;added+=1
            print(f'OK   {pdf.name}: {len(new)} records examined')
        except Exception as e:issues.append(f'{pdf.name}: {e}');print(f'SKIP {pdf.name}: {e}')
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(sorted(existing.values(),key=lambda r:(r['year'],r['period_end'],r['location'],r['species'])))
    print(f'Saved {out}: {len(existing)} total records, {added} newly added, {len(issues)} reports needing review.')
    if issues:
        Path('import_review.txt').write_text('\n'.join(issues)+'\n',encoding='utf-8')
        print('Review import_review.txt. Existing data is preserved.')

if __name__=='__main__':main()
