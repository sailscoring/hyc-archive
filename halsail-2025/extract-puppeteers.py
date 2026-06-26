#!/usr/bin/env python3
"""Extract the 2025 Puppeteer fleet from the published Sailwave HTML into
HalSail-import CSVs (classes/boats/races/finishes), for the #235 Phase-3
HalSail reproduction. Reads only real published data (hyc-archive rule:
never fabricate). See ./README.md for the build plan and caveats.

Source: ../sources/reshyc/results.hyc.ie/reshyc/2025/club/*.htm
Outputs: ./puppeteers/{boats,races}.csv and ./puppeteers/finishes/*.csv
"""
import re, os, csv, datetime

SRC = os.path.join(os.path.dirname(__file__),
                   "../sources/reshyc/results.hyc.ie/reshyc/2025/club")
OUT = os.path.join(os.path.dirname(__file__), "puppeteers")
YEAR = 2025
MONTHS = {m: i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}

# (file, day-label, block) — the published Puppeteer pages in scope
TUE = [("series1_tue_pup.htm","Tuesday","Series 1"),
       ("series2_tue_pup.htm","Tuesday","Series 2"),
       ("series3_tue_pup.htm","Tuesday","Series 3"),
       ("mini_tue_pup.htm","Tuesday","Mini")]
SAT = [("series1_satpups.htm","Saturday","Series 1"),
       ("series2_satpups.htm","Saturday","Series 2"),
       ("series3_satpups.htm","Saturday","Series 3")]

def cells(row):
    return [re.sub(r"<.*?>","",c).replace("&nbsp;"," ").strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]

def tables(html):
    out=[]
    for t in re.split(r"<table", html)[1:]:
        rows=[cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S)]
        rows=[r for r in rows if r]
        if rows: out.append(rows)
    return out

def parse_date(s):
    s=re.sub(r"^R\d+\s*", "", s.strip())  # drop "R1" race-number prefix
    m=re.match(r"([A-Za-z]{3})\w*\s+(\d+)", s)
    return datetime.date(YEAR, MONTHS[m.group(1)], int(m.group(2)))

def hms(s):
    # "21.01.36" -> timedelta/time; returns (h,m,s) ints or None
    m=re.match(r"^(\d{1,2})\.(\d{2})\.(\d{2})$", s.strip())
    return tuple(int(x) for x in m.groups()) if m else None

CODE_RE=re.compile(r"\b(DNC|DNF|DNS|RET|OCS|DSQ|DNE|TLE|RDG|UFD|BFD|ZFP|SCP)\b")

def parse_file(fn):
    html=open(os.path.join(SRC,fn),encoding="utf-8",errors="replace").read()
    ts=tables(html)
    summ=[t for t in ts if "Nett" in t[0]]
    det =[t for t in ts if "Finish" in t[0] and "Corrected" in t[0]]
    hdr=summ[0][0]
    i0=hdr.index("Rating")+1; i1=hdr.index("Total")
    dates=[parse_date(c) for c in hdr[i0:i1]]
    N=len(dates)
    # group detail tables into chunks of N; pick the HPH chunk (ratings vary)
    chunks=[det[i:i+N] for i in range(0,len(det),N)]
    def varies(chunk):
        rs=[r[4] for tb in chunk for r in tb[1:] if len(r)>4]
        return len(set(rs))>1
    hph=next((c for c in chunks if varies(c)), chunks[0])
    # per race: finishers (sail->(finish,elapsed,rating)) and start time
    races=[]
    for r,(d,tb) in enumerate(zip(dates,hph)):
        fin={}
        starts=[]
        for row in tb[1:]:
            if len(row)<8: continue
            sail,_,_,rating,finish,elapsed=row[1],row[2],row[3],row[4],row[5],row[6]
            fin[sail]={"finish":finish,"elapsed":elapsed,"rating":rating}
            f,e=hms(finish),hms(elapsed)
            if f and e:
                ft=datetime.timedelta(hours=f[0],minutes=f[1],seconds=f[2])
                et=datetime.timedelta(hours=e[0],minutes=e[1],seconds=e[2])
                starts.append(ft-et)
        start=min(starts) if starts else None
        races.append({"date":d,"start":start,"fin":fin})
    # codes per (sail, race) from summary (use first summary table)
    s0=summ[0]
    sh=s0[0]; ci0=sh.index("Rating")+1; ci1=sh.index("Total")
    codes={}
    boats={}
    for row in s0[1:]:
        if len(row)<ci1: continue
        sail,boat,ent=row[1],row[2],row[3]
        boats[sail]={"boat":boat,"entrant":ent}
        for r,cell in enumerate(row[ci0:ci1]):
            m=CODE_RE.search(cell)
            if m: codes.setdefault(r,{})[sail]=m.group(1)
    for r,race in enumerate(races):
        race["codes"]=codes.get(r,{})
    return races, boats

def collect(group):
    allraces=[]; boats={}
    for fn,day,block in group:
        races,bs=parse_file(fn)
        for sail,b in bs.items(): boats.setdefault(sail,b)
        for r in races:
            r["day"]=day; r["block"]=block; allraces.append(r)
    # dedupe races by date (Mini races are distinct dates; Series cover the rest)
    bydate={}
    for r in allraces:
        bydate.setdefault(r["date"], r)
    races=sorted(bydate.values(), key=lambda r:r["date"])
    return races, boats, allraces

tue_races, tue_boats, tue_all = collect(TUE)
sat_races, sat_boats, sat_all = collect(SAT)

# ---- merged boat list + per-day starting HPH rating ----
boats={}
for src in (tue_boats, sat_boats):
    for sail,b in src.items(): boats.setdefault(sail,dict(b))
def start_rating(races, sail):
    for r in races:  # earliest race the boat has a rating for
        if sail in r["fin"] and re.match(r"^\d\.\d+$", r["fin"][sail]["rating"]):
            return r["fin"][sail]["rating"]
    return None
for sail in boats:
    boats[sail]["tue_hph"]=start_rating(tue_races, sail)
    boats[sail]["sat_hph"]=start_rating(sat_races, sail)

os.makedirs(os.path.join(OUT,"finishes"), exist_ok=True)

# HalSail's CSV import splits on every comma (it does not honour quotes), so keep
# commas out of free-text fields. e.g. "Biggs, Sargent & Johnston" -> "Biggs /
# Sargent & Johnston". (Recorded as a delta in README.)
def nocomma(s): return s.replace(", "," / ").replace(","," / ")

# ---- boats.csv (one row per boat x class enrolment) ----
with open(os.path.join(OUT,"boats.csv"),"w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["Sail Number","Boat name","Owner","Helm","Class","Handicap"])
    for sail in sorted(boats, key=lambda s:(len(s),s)):
        b=boats[sail]; ent=nocomma(b["entrant"]); b["boat"]=nocomma(b["boat"])
        w.writerow([sail,b["boat"],ent,ent,"Puppeteer Master","1.000"])
        w.writerow([sail,b["boat"],ent,ent,"Puppeteer Scratch",""])
        if b["tue_hph"]:
            w.writerow([sail,b["boat"],ent,ent,"Puppeteer HPH (Tue)",b["tue_hph"]])
        if b["sat_hph"]:
            w.writerow([sail,b["boat"],ent,ent,"Puppeteer HPH (Sat)",b["sat_hph"]])

# ---- races.csv (into the hidden Puppeteer Master series) ----
def startdt(r):
    if r["start"] is None: return ""
    secs=int(r["start"].total_seconds()); h=secs//3600; m=(secs%3600)//60; s=secs%60
    return datetime.datetime(r["date"].year,r["date"].month,r["date"].day,h,m,s)
allmaster=sorted(tue_races+sat_races, key=lambda r:(r["date"], r["day"]))
with open(os.path.join(OUT,"races.csv"),"w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["Start","Class","Series","Sequence","Excludable","Notes"])
    for r in allmaster:
        dt=startdt(r)
        start=dt.strftime("%d/%m/%Y %H:%M:%S") if dt else r["date"].strftime("%d/%m/%Y")
        w.writerow([start,"Puppeteer Master","2025 Summer Series","5/4/1/go","TRUE",
                    f'{r["day"]} {r["block"]}'])

# ---- finishes/<day>-<date>.csv (per Master race) ----
def fmt_finish(s):
    return s.replace(".",":") if hms(s) else ""   # "21.01.36" -> "21:01:36"
for r in allmaster:
    key=f'{r["day"][:3].lower()}-{r["date"]:%m-%d}'
    with open(os.path.join(OUT,"finishes",key+".csv"),"w",newline="") as f:
        w=csv.writer(f); w.writerow(["Sail Number","Finish","Status"])
        # detail rows: a real time -> Finish; else a code (RET/DNF/... may sit in
        # the Finish or Elapsed cell, or only in the summary) -> Status
        for sail,d in r["fin"].items():
            fin=d["finish"]
            if hms(fin):
                w.writerow([sail, fin.replace(".",":"), ""])
            else:
                m=CODE_RE.search(f'{fin} {d["elapsed"]}')
                w.writerow([sail, "", m.group(1) if m else r["codes"].get(sail,"")])
        # boats coded only in the summary (not in detail); DNC is auto, so omit
        for sail,code in r["codes"].items():
            if sail not in r["fin"] and code!="DNC":
                w.writerow([sail,"",code])

# ---- classes.csv ----
with open(os.path.join(OUT,"classes.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(["Name","Handicap Type","Flag","Notes"])
    w.writerow(["Puppeteer Master","TCF","P","HIDDEN base: real races+finishes. Set series embargo to hidden-always."])
    w.writerow(["Puppeteer Scratch","Level","P","One-design scratch view (Tue+Sat)."])
    w.writerow(["Puppeteer HPH (Tue)","NHC","P","Tuesday HPH chain. After import set local handicap name to HPH."])
    w.writerow(["Puppeteer HPH (Sat)","NHC","P","Saturday HPH chain. After import set local handicap name to HPH."])

# ---- series-build-guide.md (the manual-entry artifact) ----
def dlist(races, block):
    ds=[r["date"] for r in races if r["block"]==block]
    return ", ".join(d.strftime("%a %-d %b") for d in sorted(set(ds)))
tue_all_dates=", ".join(d.strftime("%-d %b") for d in sorted({r["date"] for r in tue_races}))
with open(os.path.join(OUT,"series-build-guide.md"),"w") as f:
    f.write("# Puppeteer 2025 — series & tandem build guide\n\n")
    f.write("_Generated by `extract-puppeteers.py`. Manual HalSail steps after "
            "importing `classes.csv`, `boats.csv`, `races.csv`._\n\n")
    f.write("## Step 1 — Master series (hidden)\n\n"
            "Create series **`2025 Summer Series`** in class **`Puppeteer Master`**; "
            "set its embargo to **\"hidden, always embargoed\"**. Then import "
            "`races.csv` (27 races: 16 Tue + 11 Sat) into it.\n\n")
    f.write("## Step 2 — Tandem series (16)\n\n"
            "Each: **Schedule → New tandem series** → base class `Puppeteer Master`, "
            "base series `2025 Summer Series` → set **target class** + **name**, and "
            "include **only** the listed race dates.\n\n")
    def row(name, dates): f.write(f"| {name} | {dates} |\n")
    f.write("### → target class `Puppeteer Scratch`\n\n| Tandem series | Races to include |\n|---|---|\n")
    row("Tuesday Series 1", dlist(tue_all,"Series 1"))
    row("Tuesday Series 2", dlist(tue_all,"Series 2"))
    row("Tuesday Series 3", dlist(tue_all,"Series 3"))
    row("Tuesday Mini",     dlist(tue_all,"Mini"))
    row("Tuesday Overall",  "all 16 Tuesday races")
    row("Saturday Series 1",dlist(sat_all,"Series 1"))
    row("Saturday Series 2",dlist(sat_all,"Series 2"))
    row("Saturday Series 3",dlist(sat_all,"Series 3"))
    f.write("\n### → target class `Puppeteer HPH (Tue)`\n\n| Tandem series | Races to include |\n|---|---|\n")
    row("Tuesday Series 1", dlist(tue_all,"Series 1"))
    row("Tuesday Series 2", dlist(tue_all,"Series 2"))
    row("Tuesday Series 3", dlist(tue_all,"Series 3"))
    row("Tuesday Mini",     dlist(tue_all,"Mini"))
    row("Tuesday Overall",  "all 16 Tuesday races")
    f.write("\n### → target class `Puppeteer HPH (Sat)`\n\n| Tandem series | Races to include |\n|---|---|\n")
    row("Saturday Series 1",dlist(sat_all,"Series 1"))
    row("Saturday Series 2",dlist(sat_all,"Series 2"))
    row("Saturday Series 3",dlist(sat_all,"Series 3"))
    f.write("\n## Discards\n\n"
            "HYC 2025 used **1 discard per 4 races** (`floor(races/4)`), verified "
            "from the published Nett-vs-Total brackets (2-race Mini = 0, 4-race "
            "Series = 1, 16-race Overall = 4). Configure **one** discard profile and "
            "set it as the **club default** — keyed on the series' race count, it "
            "gives every tandem the right number automatically:\n\n"
            "| Races | Discards |\n|---|---|\n| 1-3 | 0 |\n| 4-7 | 1 |\n"
            "| 8-11 | 2 |\n| 12-15 | 3 |\n| 16-19 | 4 |\n\n"
            "Leave the hidden Master series unscored (no discards needed).\n")
    f.write("\n## Step 3 — Finishes\n\n"
            "Import each `finishes/<day>-<MM-DD>.csv` into its matching Master race "
            "(by date). Finishers carry clock finish times; RET/DNF/DNS/OCS/UFD are "
            "marked; DNC boats are omitted (HalSail auto-scores absentees as DNC).\n")

# ---- report ----
print(f"Tuesday races: {len(tue_races)}  Saturday races: {len(sat_races)}  total: {len(allmaster)}")
print(f"Boats: {len(boats)}")
print("\nTandem -> race dates:")
def blockdates(races, day, block):
    return [r["date"].strftime("%b %-d") for r in races if r["block"]==block]
for fn,day,block in TUE:
    ds=[r["date"].strftime("%b %-d") for r in tue_all if r["block"]==block]
    print(f"  {day} {block:8}: {ds}")
print(f"  Tuesday Overall : all {len(tue_races)} Tuesday races")
for fn,day,block in SAT:
    ds=[r["date"].strftime("%b %-d") for r in sat_all if r["block"]==block]
    print(f"  {day} {block:8}: {ds}")
print("\nSample boats:")
for sail in list(sorted(boats,key=lambda s:(len(s),s)))[:6]:
    print(" ",sail,boats[sail])
