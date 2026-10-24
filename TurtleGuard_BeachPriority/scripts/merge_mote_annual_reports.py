"""Reproducible Mote annual CSV extraction from the supplied report PDF styles.

Usage:
  python scripts/merge_mote_annual_reports.py --reports data/mote_annual_reports

Parses historical comparisons inside PDFs, records every candidate with provenance,
then selects the largest annual nest count for matching year and beach. Never
adds false crawls. Does NOT assume report-year 2026 is a completed season.

This parser intentionally supports only the supplied Mote report layouts and
raises an error for unexpected text shapes instead of silently guessing.
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREAS = ('Longboat Key','Lido Key','Siesta Key','Casey Key','Venice')
LONGBOAT_MANATEE = re.compile(r'^Longboat(?:\s+Key)?\s*(?:[-–‐]\s*)?Manatee(?:\s+County)?$', re.I)
LONGBOAT_SARASOTA = re.compile(r'^Longboat(?:\s+Key)?\s*(?:[-–‐]\s*)?Sarasota(?:\s+County)?$', re.I)

def normalized(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0',' ').replace('‐','-').replace('–','-')).strip()

def where(s):
    t=normalized(s)
    if LONGBOAT_MANATEE.fullmatch(t):return ('Longboat Key','manatee')
    if LONGBOAT_SARASOTA.fullmatch(t):return ('Longboat Key','sarasota')
    if t.lower() in ('longboat key',):return ('Longboat Key','whole')
    if t.lower() in ('lido key','lido beach'):return ('Lido Key','whole')
    if t.lower() == 'siesta key':return ('Siesta Key','whole')
    if t.lower() == 'casey key':return ('Casey Key','whole')
    if t.lower() == 'venice':return ('Venice','whole')
    return None

def number(t):
    text=normalized(t).replace(',','').removesuffix('*')
    if re.fullmatch(r'\d+',text):return int(text)
    return None

def get_rows(lines, width, *, maxrow=1000):
    rows=[]
    for i,t in enumerate(lines):
        area=where(t)
        if not area:continue
        vals=[]
        for q in lines[i+1:i+1+maxrow]:
            if where(q) or q.lower().startswith(('total','yearly:', 'grand total')):
                break
            n=number(q)
            if n is None: break
            vals.append(n)
        if len(vals) == width:rows.append((i,area,vals))
    return rows

def get_candidates(p):
    import pymupdf
    lines=[normalized(s) for s in pymupdf.open(p)[0].get_text().splitlines()]
    title=' '.join(lines[:20]).lower()
    extracted=[]
    # New table layout: year begins a block of five named beaches with trailing
    # Yearly Nests, Yearly FCs, Yearly All. Avoid the weekly zero columns.
    if 'key name' in title and 'yearly nests' in title:
        idx=next(i for i,s in enumerate(lines) if s.lower()=='yearly nests')
        i=idx+3 if lines[idx+1:idx+3]==['Yearly FCs','Yearly All'] else idx+1
        year=None; allrows=defaultdict(dict)
        while i<len(lines):
            t=lines[i]
            if re.fullmatch(r'20\d\d',t):year=int(t);i+=1;continue
            area=where(t)
            if area and year is not None:
                nums=[number(x) for x in lines[i+1:i+13]]
                if any(v is None for v in nums) or len(nums)!=12:
                    raise ValueError(f'{p.name}: unexpected year table columns for {year} {t}')
                count=nums[-3]; allrows[year][area[0]]=count
                i+=13;continue
            i+=1
        if not allrows or any(set(row)!=set(AREAS) for row in allrows.values()):
            raise ValueError(f'{p.name}: missing annual table rows')
        for yr,places in allrows.items():
            for area,val in places.items():
                extracted.append((yr,area,val,'annual_table'))
        return extracted

    # Final-year species table, six rows incl. two Longboat county pieces.
    if 'final' in p.name.lower():
        m=re.search(r'20\d\d', p.name)
        if not m:raise ValueError('Missing year from final report filename: '+p.name)
        year=int(m.group())
        rows=[]
        for i,line in enumerate(lines):
            area=where(line)
            if area:
                vals=[]
                for tok in lines[i+1:]:
                    n=number(tok)
                    if n is None:break
                    vals.append(n)
                if year==2015:
                    if len(vals) not in (5,7):raise ValueError(f'{p.name}: unsupported 2015 row: {line} {vals}')
                    nests=vals[-3]
                elif year==2019:
                    if len(vals)!=6:raise ValueError(f'{p.name}: unsupported 2019 row {line} {vals}')
                    nests=vals[0]+vals[2]+vals[4]
                else:
                    if len(vals)!=4:raise ValueError(f'{p.name}: unsupported final row {line} {vals}')
                    nests=vals[0]+vals[2]
                rows.append((area,nests))
        if len(rows)!=6:raise ValueError(f'{p.name}: expected 6 beach/county rows, got {len(rows)}')
        totals=defaultdict(lambda:defaultdict(int))
        for (area,part),v in rows:totals[area][part]+=v
        if len(totals)!=5 or set(totals['Longboat Key'])!={'manatee','sarasota'}:
            raise ValueError(f'{p.name}: unexpected beach set or Longboat split')
        return [(year,area,sum(parts.values()),'final_table') for area,parts in totals.items()]

    # Older weekly report: 4 blocks (current weekly, current cumulative,
    # previous weekly, previous cumulative), each six rows with four columns:
    # loggerhead nests, false crawls, green nests, false crawls.
    reportyear = 2009 if p.name.startswith('Nesting_Update_') else int(re.search(r'20\d\d',p.name).group())
    rows=get_rows(lines,4)
    if len(rows)!=24:raise ValueError(f'{p.name}: expected 24 rows of old weekly layout, got {len(rows)}')
    for group_index,year in [(1,reportyear),(3,reportyear-1)]:
        rowsgroup=rows[group_index*6:(group_index+1)*6]
        per=defaultdict(dict)
        for _,(area,part),v in rowsgroup:per[area][part]=v[0]+v[2]
        if set(per)!=set(AREAS) or set(per['Longboat Key']) != {'manatee','sarasota'}:
            raise ValueError(f'{p.name}: missing cumulative beach rows for {year}')
        for area,parts in per.items():
            if year>=2009: extracted.append((year,area,sum(parts.values()),'partial_season_cumulative'))
    return extracted

def save_csv(filename, rows, fields):
    filename.parent.mkdir(parents=True,exist_ok=True)
    with filename.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def merge_reports(report_dir, existing, output):
    sources=[]
    for p in sorted(report_dir.glob('*.pdf')):
        entries=get_candidates(p)
        if not entries:raise ValueError('No recognized nesting entries in '+p.name)
        for year,area,count,kind in entries:
            sources.append(dict(location=area,year=year,nests=count,source=p.name,source_type=kind,
                                status='provisional' if year==2026 else ('final_report' if kind=='final_table' else 'cumulative_report')))
    # Existing input is a fallback only; current named source reports take priority
    # when choosing equivalent counts, but max count is user-specified criterion.
    with existing.open('r',encoding='utf-8-sig',newline='') as f:
        historic=list(csv.DictReader(f))
    if not historic:raise ValueError('Existing historical CSV empty')
    preserved=[r for r in historic if r['location'] not in AREAS]
    for r in historic:
        if r['location'] in AREAS:
            sources.append(dict(location=r['location'],year=int(r['year']),nests=int(float(r['nests'])),
                                source='preexisting_nesting_counts.csv',source_type='previous_import',status='previously_imported'))
    grouped=defaultdict(list)
    for record in sources:
        if record['location'] in AREAS and 2009 <= int(record['year']) <= 2026:
            grouped[(record['location'],int(record['year']))].append(record)
    selected=[]; conflicts=[]
    for (area,yr), candidates in sorted(grouped.items()):
        chosen=max(candidates,key=lambda r:(r['nests'],r['source_type']!='previous_import'))
        selected.append(dict(location=area,year=yr,species='all',nests=chosen['nests']))
        diff=sorted(set(x['nests'] for x in candidates))
        if len(diff)>1:
            conflicts.append(dict(location=area,year=yr,selected_nests=chosen['nests'],
                                  alternatives=';'.join(map(str,diff)),source=chosen['source']))
    for area in AREAS:
        years={r['year'] for r in selected if r['location']==area}
        if years!=set(range(2009,2027)):
            raise ValueError(f'{area}: years absent from source documents: {sorted(set(range(2009,2027))-years)}')
    # No fake zero years; other areas are unchanged.
    combined=[dict(location=r['location'],year=int(r['year']),species=r['species'],nests=int(float(r['nests']))) for r in preserved]+selected
    combined.sort(key=lambda r:(r['location'],r['species'],r['year']))
    keys=[(r['location'],r['species'],r['year']) for r in combined]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate output location/species/year')
    save_csv(output,combined,['location','year','species','nests'])
    root=output.parent
    save_csv(root/'mote_candidates_audit.csv',sources,['location','year','nests','source','source_type','status'])
    save_csv(root/'mote_conflicts_review.csv',conflicts,['location','year','selected_nests','alternatives','source'])
    save_csv(root/'mote_annual_selected_sources.csv',[
        dict(location=a,year=y,nests=max(g,key=lambda r:r['nests'])['nests'],
             selected_source=max(g,key=lambda r:r['nests'])['source'],
             data_status='PROVISIONAL_INCOMPLETE_2026' if y==2026 else 'historical_report')
        for (a,y),g in sorted(grouped.items())],
        ['location','year','nests','selected_source','data_status'])
    print(f'Merged {len(selected)} Mote annual observations (2009-2026) into {output}; {len(conflicts)} conflicting area/years flagged. 2026 provisional.')
    return combined,conflicts

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--reports',default='data/mote_annual_reports')
    ap.add_argument('--existing',default='data/nesting_counts.csv')
    ap.add_argument('--output',default='data/nesting_counts.csv')
    args=ap.parse_args()
    report_dir=Path(args.reports);report_dir=report_dir if report_dir.is_absolute() else ROOT/report_dir
    existing=Path(args.existing);existing=existing if existing.is_absolute() else ROOT/existing
    output=Path(args.output);output=output if output.is_absolute() else ROOT/output
    if not report_dir.exists():raise ValueError('No report directory: '+str(report_dir))
    merge_reports(report_dir,existing,output)
if __name__=='__main__':main()
