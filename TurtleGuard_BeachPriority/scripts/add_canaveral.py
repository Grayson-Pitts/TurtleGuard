import csv
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'data'/'nesting_counts.csv'
# Annual species counts transcribed from NPS Sea Turtle Monitoring table (1985-2024), checked against source.
rows='''2024 5571 1801
2023 5677 11106
2022 6188 6331
2021 3708 4303
2020 4187 367
2019 5646 7629
2018 4223 301
2017 4556 7736
2016 5057 381
2015 3905 3571
2014 3322 420
2013 3758 4152
2012 5154 816
2011 3742 1374
2010 4250 1343
2009 2729 301
2008 3637 899
2007 2356 1249
2006 2470 396
2005 2547 1040
2004 2281 255
2003 3229 74
2002 3161 856
2001 3257 7
2000 3892 662
1999 4501 5
1998 3976 427
1997 2702 21
1996 3260 222
1995 4121 47
1994 3886 364
1993 3140 28
1992 3279 298
1991 4074 25
1990 3922 185
1989 3091 41
1988 2203 43
1987 1670 90
1986 3349 22
1985 2389 94'''
with p.open(newline='',encoding='utf-8-sig') as f: data=list(csv.DictReader(f))
data=[r for r in data if r['location']!='Canaveral National Seashore']
for row in rows.splitlines():
 year,logger,green=row.split()
 for species,nests in [('loggerhead',logger),('green',green)]: data.append(dict(location='Canaveral National Seashore',year=year,species=species,nests=nests))
data.sort(key=lambda r:(r['location'],r['species'],int(r['year'])))
with p.open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=['location','year','species','nests']);w.writeheader();w.writerows(data)
print(f'Wrote {len(data)} rows to {p}')
