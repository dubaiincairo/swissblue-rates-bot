"""Build the rates site from raw/<Hotel>.json files (one per hotel, from collect.cjs).
Usage: python3 build.py raw_dir prev_dir site_dir
prev_dir holds the last published data/<hotel>.json; a source that failed this run keeps its last good table."""
import json, os, re, sys, math, html, datetime, statistics as st, base64
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Riyadh')
HERE = os.path.dirname(os.path.abspath(__file__))
H = json.load(open(os.path.join(HERE, 'hotels.json')))
VAT = 1.17875
OWN = re.compile(r'swiss ?blue|vinas|tulip|سويس ?بلو', re.I)
BIG = re.compile(r'Two-Bedroom|Three-Bedroom|Four-Bedroom|Chalet|Villa|Dormitory|Bed in|\b[2-9] ?BR\b|\b[2-9] ?Bedroom|غرفتين|[٢-٩2-9] غرف', re.I)
AGODA_SKIP = re.compile(r'Villa|Entire House|Chalet|Hostel|Resort', re.I)
E = html.escape
FIVE = ['Booking.com', 'Agoda', 'Expedia.com', 'Hotels.com', 'Trip.com']

def nxt(d): return (datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat()
def hav(a, b, c, d):
    p = math.radians; h = math.sin(p(c - a) / 2) ** 2 + math.cos(p(a)) * math.cos(p(c)) * math.sin(p(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))
UNIT = {'km': 1, 'm': 0.001, 'mi': 1.609344, 'mile': 1.609344, 'miles': 1.609344, 'ft': 0.0003048, 'feet': 0.0003048}
def km(s):
    m = re.search(r'([\d.,]+)\s*(km|miles|mile|mi|feet|ft|m)\b', s or '')
    return None if not m else float(m.group(1).replace(',', '')) * UNIT[m.group(2)]
def num(s):
    m = re.search(r'([\d,]+)', s or ''); return int(m.group(1).replace(',', '')) if m else None
def score(s):
    m = re.search(r'Scored ([\d.]+)', s or ''); return float(m.group(1)) if m else None
def clean_room(r):
    return re.split(r' (?:Free cancellation|No prepayment|We have \d+ left|Only \d+ left|Breakfast included|Entire |Private )', r or '')[0].strip()[:70]

def _v(n):
    o = []
    while n > 127: o.append((n & 127) | 128); n >>= 7
    return o + [n]
def _f(n, t, p): return _v(n << 3) + _v(p) if t == 0 else _v(n << 3 | 2) + _v(len(p)) + list(p)
def gts(ci, co):
    dt = lambda d: (lambda y, m, dd: _f(1, 0, y) + _f(2, 0, m) + _f(3, 0, dd))(*map(int, d.split('-')))
    a = _f(1, 0, 3); f2 = _f(1, 2, a) + _f(1, 2, a) + _f(2, 0, 0)
    ds = _f(1, 2, dt(ci)) + _f(2, 2, dt(co)) + _f(3, 0, 1)
    f3 = _f(1, 2, _f(3, 2, [])) + _f(2, 2, _f(2, 2, ds) + _f(6, 2, _f(2, 0, 0)))
    f5 = _f(1, 2, _f(7, 2, list(b'SAR'))) + _f(3, 2, [])
    return base64.urlsafe_b64encode(bytes(_f(1, 0, 1) + _f(2, 2, f2) + _f(3, 2, f3) + _f(5, 2, f5))).decode().rstrip('=')
def gurl(eid, d): return f'https://www.google.com/travel/hotels/entity/{eid}/prices?hl=en&gl=sa&curr=SAR&ts={gts(d, nxt(d))}'
def burl(u, d): return f'{u}?checkin={d}&checkout={nxt(d)}&group_adults=2&no_rooms=1&group_children=0&selected_currency=SAR' if u else None
def aurl(path, d): return f'https://www.agoda.com{path}?checkIn={d}&los=1&adults=2&rooms=1&children=0&currencyCode=SAR' if path else None

# ---------- turn raw results into tables: {own:{d:{v,u,t}}, rows:[{name,km,score,kind,u:{d:url},p:{d:v},t:{d:tip}}]}
def t_booking(k, raw):
    h = H[k]; own, rows = {}, {}
    for r in raw.get('booking') or []:
        d = r.get('date')
        for c in r.get('cards') or []:
            n, p, room = (c.get('name') or '').strip(), num(c.get('price')), c.get('room') or ''
            if not n or p is None: continue
            if OWN.search(n):
                own.setdefault(d, {'v': p, 'u': burl(c.get('url'), d), 't': clean_room(room)}); continue
            dist = km(c.get('dist'))
            if dist is None or dist > h['radius'] or p > 1500 or BIG.search(room) or BIG.search(n) or score(c.get('score')) is None: continue
            e = rows.setdefault(n, {'name': n, 'km': dist, 'score': score(c.get('score')), 'p': {}, 'u': {}, 't': {}})
            e['p'][d] = p; e['u'][d] = burl(c.get('url'), d); e['t'][d] = clean_room(room)
    ok = sum(1 for r in raw.get('booking') or [] if r.get('cards'))
    return {'own': own, 'rows': sorted(rows.values(), key=lambda e: e['km']), 'ok': ok}

def t_agoda(k, raw):
    h = H[k]; own, rows = {}, {}; rad = h['radius']
    for r in raw.get('agoda') or []:
        d = r.get('date')
        for c in r.get('cards') or []:
            if not c.get('available') or not c.get('net') or not c.get('name'): continue
            v = round(c['net'])
            if c.get('id') == h['agoda_own']:
                own[d] = {'v': v, 'u': aurl(c.get('link'), d), 't': c['name']}; continue
            if OWN.search(c['name']) or c.get('lat') is None: continue
            dist = hav(h['lat'], h['lon'], c['lat'], c['lon'])
            if dist > rad or v > 1500 or AGODA_SKIP.search(c.get('type') or '') or BIG.search(c['name']) or not c.get('score'): continue
            e = rows.setdefault(c['id'], {'name': c['name'], 'km': dist, 'score': c['score'], 'p': {}, 'u': {}, 't': {}})
            e['p'][d] = v; e['u'][d] = aurl(c.get('link'), d); e['t'][d] = c.get('type') or ''
    ok = sum(1 for r in raw.get('agoda') or [] if r.get('cards'))
    return {'own': own, 'rows': sorted(rows.values(), key=lambda e: e['km']), 'ok': ok}

def google_offers(raw):
    G = {}
    for r in raw.get('google') or []:
        if not r.get('offers'): continue
        div = VAT if r.get('mode') == 'total' else 1
        G.setdefault(r['key'], {})[r['date']] = {o['p']: round(o['v'] / div) for o in r['offers']}
    return G

def t_google(k, raw, pick):
    """pick(offers_dict) -> (value, tip) or None. Rows = hand-picked competitors (Google Hotels)."""
    h = H[k]; G = google_offers(raw); own, rows = {}, []
    for c in h['google']:
        e = {'name': c['name'], 'km': c.get('km'), 'seg': c['seg'], 'p': {}, 'u': {}, 't': {}}
        for d, offers in (G.get(c['key']) or {}).items():
            got = pick(offers)
            if not got: continue
            if c['seg'] == 'own': own[d] = {'v': got[0], 'u': gurl(c['id'], d), 't': got[1]}
            else: e['p'][d] = got[0]; e['u'][d] = gurl(c['id'], d); e['t'][d] = got[1]
        e['link'] = gurl(c['id'], raw['dates'][0]) if raw.get('dates') else None
        if c['seg'] != 'own': rows.append(e)
    ok = len({d for v in G.values() for d in v})
    return {'own': own, 'rows': rows, 'ok': ok}

def pick_expedia(o):
    if 'Expedia.com' in o: return o['Expedia.com'], 'Expedia.com'
    if 'Hotels.com' in o: return o['Hotels.com'], 'Hotels.com (Expedia Group)'
def pick_avg(o):
    v = [(p, o[p]) for p in FIVE if p in o]
    if not v: return None
    return round(sum(x for _, x in v) / len(v)), ', '.join(f'{p} {x}' for p, x in v)

def middles(tab, dates):
    m = {}
    for d in dates:
        v = [e['p'][d] for e in tab['rows'] if d in e['p']]
        if v: m[d] = (int(st.median(v)), len(v))
    return m

# ---------- HTML
def dhead(dates):
    months, cur = [], None
    for d in dates:
        x = datetime.date.fromisoformat(d); lab = x.strftime('%B %Y')
        if months and months[-1][0] == lab: months[-1][1] += 1
        else: months.append([lab, 1])
    r1 = ''.join(f'<th scope="colgroup" colspan="{n}" class="mon">{E(l)}</th>' for l, n in months)
    r2 = ''
    for d in dates:
        x = datetime.date.fromisoformat(d); we = ' we' if x.weekday() in (3, 4) else ''
        r2 += f'<th scope="col" class="day{we}"><span>{x.strftime("%a")}</span>{x.day}</th>'
    return r1, r2

EXT = '<svg class="ext" viewBox="0 0 16 16" aria-hidden="true"><path d="M9 2h5v5M14 2 7 9M12 9v4a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
def a(u, txt, title=''):
    if not u: return txt
    t = f' title="{E(title)}"' if title else ''
    return f'<a href="{E(u)}" target="_blank" rel="noopener noreferrer"{t}>{txt}</a>'

def table(tab, dates, label, src_name, rowlink):
    r1, r2 = dhead(dates); mid = middles(tab, dates)
    def cells(row, own=False):
        out = ''
        for d in dates:
            x = date_cls = ''
            dd = datetime.date.fromisoformat(d)
            we = ' we' if dd.weekday() in (3, 4) else ''
            if own:
                o = tab['own'].get(d)
                out += (f'<td class="n{we}">{a(o["u"], str(o["v"]), o["t"])}</td>' if o else f'<td class="n na{we}">–</td>')
            else:
                v = row['p'].get(d)
                if v is None: out += f'<td class="n na{we}">–</td>'; continue
                ours = tab['own'].get(d, {}).get('v')
                lo = ' lo' if ours and v < ours else ''
                out += f'<td class="n{lo}{we}">{a(row["u"].get(d), str(v), row["t"].get(d, ""))}</td>'
        return out
    us = f'<tr class="usr"><th scope="row" class="nm"><span>Us: {E(label)}</span></th>{cells(None, True)}</tr>'
    mr = ''.join((f'<td class="n{" we" if datetime.date.fromisoformat(d).weekday() in (3, 4) else ""}">{mid[d][0]}<small>{mid[d][1]}</small></td>' if d in mid else '<td class="n na">–</td>') for d in dates)
    midrow = f'<tr class="mid"><th scope="row" class="nm"><span>Competitors’ middle price <small>(how many places)</small></span></th>{mr}</tr>'
    rows = ''
    for e in tab['rows']:
        if not e['p']: continue
        first = next((e['u'][d] for d in dates if e['u'].get(d)), None) or e.get('link')
        meta = []
        if e.get('km') is not None: meta.append(f'{int(e["km"] * 1000)} m' if e['km'] < 1 else f'{e["km"]:.1f} km')
        if e.get('score'): meta.append(f'★ {e["score"]:.1f}')
        if e.get('seg'): meta.append('direct' if e['seg'].startswith('direct') else 'indirect')
        nm = a(first, E(e['name']) + EXT, f'Open on {src_name}')
        rows += f'<tr><th scope="row" class="nm"><span>{nm}</span><small>{" · ".join(meta)}</small></th>{cells(e)}</tr>'
    if not rows: rows = f'<tr><td class="none" colspan="{len(dates) + 1}">No prices this time.</td></tr>'
    return (f'<div class="tw" tabindex="0" role="region" aria-label="{E(src_name)} prices, next {len(dates)} nights"><table class="cal">'
            f'<thead><tr><th scope="col" rowspan="2" class="nm corner">Place</th>{r1}</tr><tr>{r2}</tr></thead>'
            f'<tbody class="top">{us}{midrow}</tbody><tbody>{rows}</tbody></table></div>')

def info(items):
    return '<dl class="info">' + ''.join(f'<div><dt>{E(k)}</dt><dd>{v}</dd></div>' for k, v in items) + '</dl>'

def fmt_t(iso):
    return datetime.datetime.fromisoformat(iso).astimezone(TZ).strftime('%-d %b %Y, %H:%M')

def hotel_page(k, D, nav):
    h = H[k]; dates = D['dates']
    secs = []
    spec = [
        ('booking', 'All nearby places on Booking.com', 'Booking.com', [
            ('Who is compared', f'Every place on Booking.com within {h["radius"]:g} km of {E(h["label"])} that has guest reviews. Rooms, studios and one-bedroom units only; 2+ bedroom units, chalets and hostel beds are left out.'),
            ('Price shown', "Booking.com's cheapest room for that night, 2 adults, <strong>without</strong> VAT and fees."),
            ('Colours', '<span class="sw lo"></span> Red = cheaper than us that night. <span class="sw we"></span> Shaded columns = Thursday and Friday.'),
            ('Links', 'Click a name or a price to open that place on Booking.com for that night.')]),
        ('agoda', 'All nearby places on Agoda', 'Agoda', [
            ('Who is compared', f'Every place on Agoda within {h["radius"]:g} km of {E(h["label"])} that has guest reviews. Villas, whole houses, chalets, hostels and 2+ bedroom units are left out.'),
            ('Price shown', "Agoda's cheapest room for that night, 2 adults, <strong>without</strong> VAT and fees (Agoda's own \"price before taxes\")."),
            ('Colours', '<span class="sw lo"></span> Red = cheaper than us that night. <span class="sw we"></span> Shaded columns = Thursday and Friday.'),
            ('Links', 'Click a name or a price to open that place on Agoda for that night.')]),
        ('expedia', 'Hand-picked competitors on Expedia', 'Google Hotels', [
            ('Who is compared', 'Hand-picked direct and indirect competitors (pricing doc, section 9).'),
            ('Price shown', "Expedia's cheapest room for that night, <strong>without</strong> VAT and fees. If Expedia has no price that night we show Hotels.com: it belongs to Expedia and sells the same rooms."),
            ('Where it comes from', "Expedia blocks robots on its own website, so we read Expedia's price from Google Hotels. Google shows prices <strong>with</strong> 15% VAT and 2.5% municipality fee, so we remove them (Google price ÷ 1.17875) to compare the same way as the other tables."),
            ('Colours', '<span class="sw lo"></span> Red = cheaper than us on Expedia that night.'),
            ('Links', 'Click a name or a price to open Google Hotels for that night: it lists every platform with a "Visit site" button.')]),
        ('avg', 'Average of 5 platforms', 'Google Hotels', [
            ('Who is compared', 'Hand-picked direct and indirect competitors (pricing doc, section 9).'),
            ('Price shown', 'For each place: the average of its cheapest room on <strong>Booking.com, Agoda, Expedia, Hotels.com and Trip.com</strong> (only the platforms that have a price that night), <strong>without</strong> VAT and fees. Hover a price to see each platform.'),
            ('Where it comes from', 'Google Hotels, which lists every platform for each place. Google shows prices <strong>with</strong> 15% VAT and 2.5% municipality fee, so we remove them (Google price ÷ 1.17875).'),
            ('Colours', '<span class="sw lo"></span> Red = cheaper than our own 5-platform average that night.'),
            ('Links', 'Click a name or a price to open Google Hotels for that night: it lists every platform with a "Visit site" button.')]),
    ]
    jump = ''.join(f'<a href="#{sid}">{E(title.replace("All nearby places on ", "").replace("Hand-picked competitors on ", ""))}</a>' for sid, title, _, _ in spec)
    for sid, title, src, items in spec:
        tab = D['tables'].get(sid)
        upd = D['updated_by'].get(sid)
        items = items + [('Updated', (fmt_t(upd) + ' Riyadh time' if upd else 'not yet') + ('. <span class="old">Kept from the last good run: this run could not read the site.</span>' if D['kept'].get(sid) else ''))]
        body = table(tab, dates, h['label'], src, None) if tab else '<p class="none">No data yet.</p>'
        secs.append(f'<section id="{sid}" class="block"><h2>{E(title)}</h2>{info(items)}{body}</section>')
    d0 = dates[0]
    def kv(sid):
        tab = D['tables'].get(sid) or {'own': {}, 'rows': []}
        o = tab['own'].get(d0, {}).get('v'); m = middles(tab, [d0]).get(d0)
        return o, m
    tiles = ''
    for sid, nm in (('booking', 'Booking.com'), ('agoda', 'Agoda'), ('avg', '5-platform average')):
        o, m = kv(sid)
        tiles += (f'<div class="kpi"><span class="kl">{nm}, tonight</span><span class="kv">{o if o else "–"} <small>our price</small></span>'
                  '<span class="ks">' + ("Competitors’ middle price: <strong>" + str(m[0]) + "</strong> (" + str(m[1]) + " places)" if m else "No competitor prices tonight") + '</span></div>')
    return page(f'{h["label"]} competitor prices', nav, k, f'''
<header class="hhead"><p class="crumb"><a href="../">All hotels</a> <span aria-hidden="true">›</span> {E(h["label"])}</p>
<h1>{E(h["label"])} <span class="city">{E(h["city"])} · {E(h["kind"])}</span></h1>
<p class="intro">Our prices against nearby competitors on Booking.com, Agoda, Expedia and 5 platforms together, for every night from today to 30 days ahead. SAR per night, 2 adults, <strong>without</strong> VAT and fees.</p>
<div class="kpis">{tiles}</div>
<nav class="jump" aria-label="Tables on this page">{jump}</nav></header>
{"".join(secs)}''', D['updated'])

SYNC = '''<div class="sync" id="sync"><div class="synct"><span class="live" aria-hidden="true"></span><span class="lbl">Live · last synced</span> <time id="synced" datetime="{iso}">{txt} Riyadh time</time> <span id="ago" class="ago"></span></div>
<button type="button" id="syncbtn" class="btn">Sync now</button><p id="syncmsg" class="syncmsg" role="status" aria-live="polite"></p></div>'''

def page(title, nav, active, body, updated, root=False):
    pre = '' if root else '../'
    tabs = ''.join(f'<a href="{pre}{kk.lower()}/" {"aria-current=page" if kk == active else ""}>{E(H[kk]["label"])}</a>' for kk in H)
    sync = SYNC.format(iso=updated, txt=fmt_t(updated))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow, noarchive"><title>{E(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Sans+Arabic:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{pre}assets/site.css"></head><body>
<div class="bar"><div class="barin"><a class="brand" href="{pre}">Swiss Blue <span>rates</span></a><nav class="htabs" aria-label="Hotels">{tabs}</nav></div></div>
<main>{sync}{body}</main>
<footer><p>Data: Booking.com and Agoda searches, and Google Hotels for Expedia, Hotels.com and Trip.com. Updated every 8 hours by a robot (and whenever someone presses Sync now); prices can change at any time. Not indexed by search engines.</p></footer>
<script src="{pre}assets/site.js" defer></script></body></html>'''

def home(all_D):
    upd = max(D['updated'] for D in all_D.values())
    cards = ''
    for k, D in all_D.items():
        h = H[k]; d0 = D['dates'][0]; lines = ''
        for sid, nm in (('booking', 'Booking.com'), ('agoda', 'Agoda'), ('avg', '5 platforms')):
            tab = D['tables'].get(sid) or {'own': {}, 'rows': []}
            o = tab['own'].get(d0, {}).get('v'); m = middles(tab, [d0]).get(d0)
            ch = sum(1 for e in tab['rows'] if d0 in e['p'] and o and e['p'][d0] < o)
            n = sum(1 for e in tab['rows'] if d0 in e['p'])
            lines += f'<tr><th scope="row">{nm}</th><td>{o or "–"}</td><td>{m[0] if m else "–"}</td><td>{f"{ch} of {n}" if o and n else "–"}</td></tr>'
        cards += f'''<a class="hcard" href="{k.lower()}/"><h2>{E(h["label"])} <span class="city">{E(h["city"])}</span></h2><p class="kind">{E(h["kind"])}</p>
<table class="mini"><thead><tr><th scope="col">Tonight</th><th scope="col">Us</th><th scope="col">Competitors\u2019 middle</th><th scope="col">Cheaper than us</th></tr></thead><tbody>{lines}</tbody></table>
<span class="go">Open {E(h["label"])} calendar →</span></a>'''
    body = f'''<header class="hhead"><p class="eyebrow">Swiss Blue · competitor prices</p><h1>Choose a hotel</h1>
<p class="intro">Each hotel has its own page with 30-night price calendars on Booking.com, Agoda, Expedia and the average of 5 platforms. SAR per night, 2 adults, without VAT and fees.</p></header>
<div class="hgrid">{cards}</div>'''
    return page('Competitor prices', None, None, body, upd, root=True)

def main():
    raw_dir, prev_dir, site = sys.argv[1:4]
    all_D = {}
    for k in H:
        try: raw = json.load(open(os.path.join(raw_dir, f'{k}.json')))
        except Exception: raw = {}
        try: prev = json.load(open(os.path.join(prev_dir, f'{k.lower()}.json')))
        except Exception: prev = {}
        dates = raw.get('dates') or prev.get('dates')
        if not dates: continue
        fin = raw.get('finished') or datetime.datetime.now(TZ).isoformat()
        tabs = {'booking': t_booking(k, raw), 'agoda': t_agoda(k, raw),
                'expedia': t_google(k, raw, pick_expedia), 'avg': t_google(k, raw, pick_avg)}
        D = {'dates': dates, 'tables': {}, 'updated_by': {}, 'kept': {}}
        for sid, t in tabs.items():
            if t['ok'] >= max(1, len(dates) // 2):
                D['tables'][sid] = t; D['updated_by'][sid] = fin
            elif prev.get('tables', {}).get(sid):
                D['tables'][sid] = prev['tables'][sid]; D['updated_by'][sid] = prev['updated_by'].get(sid); D['kept'][sid] = True
            print(k, sid, 'ok', t['ok'], 'kept' if D['kept'].get(sid) else '')
        D['updated'] = max([v for v in D['updated_by'].values() if v] or [fin])
        all_D[k] = D
    if not all_D: print('nothing to build'); sys.exit(3)
    os.makedirs(os.path.join(site, 'data'), exist_ok=True)
    for k, D in all_D.items():
        json.dump(D, open(os.path.join(site, 'data', f'{k.lower()}.json'), 'w'), ensure_ascii=False)
        os.makedirs(os.path.join(site, k.lower()), exist_ok=True)
        open(os.path.join(site, k.lower(), 'index.html'), 'w').write(hotel_page(k, D, None))
    open(os.path.join(site, 'index.html'), 'w').write(home(all_D))
    print('built', ', '.join(all_D))

if __name__ == '__main__':
    main()
