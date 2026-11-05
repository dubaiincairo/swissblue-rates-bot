// Collect 31 nights of prices for ONE hotel: Booking.com (all nearby), Agoda (all nearby), Google Hotels
// (all platforms for the hand-picked competitors). Usage: node collect.cjs <Hotel> <out.json>
const fs = require('fs');
let pw; try { pw = require('playwright-core'); } catch { pw = require('playwright'); }
const H = JSON.parse(fs.readFileSync(__dirname + '/hotels.json', 'utf8'));
const KEY = process.argv[2], OUTF = process.argv[3], h = H[KEY];
const DAYS = +(process.env.DAYS || 31);
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36';
const sleep = ms => new Promise(r => setTimeout(r, ms));
function riyadhToday() { return new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10); }
function addDays(d, n) { const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); }
const D0 = riyadhToday(); const DATES = Array.from({ length: DAYS }, (_, i) => addDays(D0, i));

// Google Hotels date token (same as the research scripts)
function varint(n) { const o = []; while (n > 127) { o.push((n & 127) | 128); n >>>= 7; } o.push(n); return o; }
function fld(num, t, p) { return t === 0 ? [...varint(num << 3), ...varint(p)] : [...varint(num << 3 | 2), ...varint(p.length), ...p]; }
function gdate(d) { const [y, m, dd] = d.split('-').map(Number); return [...fld(1, 0, y), ...fld(2, 0, m), ...fld(3, 0, dd)]; }
function gts(ci, co) {
  const adult = fld(1, 0, 3), f2 = [...fld(1, 2, adult), ...fld(1, 2, adult), ...fld(2, 0, 0)];
  const dates = [...fld(1, 2, gdate(ci)), ...fld(2, 2, gdate(co)), ...fld(3, 0, 1)];
  const f3 = [...fld(1, 2, fld(3, 2, [])), ...fld(2, 2, [...fld(2, 2, dates), ...fld(6, 2, fld(2, 0, 0))])];
  const f5 = [...fld(1, 2, fld(7, 2, [...Buffer.from('SAR')])), ...fld(3, 2, [])];
  return Buffer.from([...fld(1, 0, 1), ...fld(2, 2, f2), ...fld(3, 2, f3), ...fld(5, 2, f5)]).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// Runs jobs on n tabs; stops starting new jobs after `budgetMin` minutes so one slow site cannot eat the whole run.
async function pool(ctx, n, jobs, fn, budgetMin) {
  let i = 0; const out = []; const end = Date.now() + budgetMin * 60e3;
  await Promise.all(Array.from({ length: n }, async () => {
    let p = await ctx.newPage();
    while (i < jobs.length && Date.now() < end) {
      const j = jobs[i++]; let timer;
      const limit = new Promise((_, rej) => { timer = setTimeout(() => rej(new Error('job took over 75 s')), 75e3); });
      try { out.push(await Promise.race([fn(p, j), limit])); }
      catch (e) { out.push({ ...j, error: e.message.slice(0, 80) }); if (/75 s/.test(e.message)) { await p.close().catch(() => {}); p = await ctx.newPage(); } }
      finally { clearTimeout(timer); }
    }
    await p.close().catch(() => {});
  }));
  if (i < jobs.length) console.log('time budget reached, skipped', jobs.length - i, 'of', jobs.length);
  return out;
}

const BK_EXTRACT = () => {
  const t = (el, s) => el.querySelector(s)?.innerText?.replace(/\s+/g, ' ').trim() || null;
  return [...document.querySelectorAll('[data-testid="property-card"]')].map(c => ({
    name: t(c, '[data-testid="title"]'), price: t(c, '[data-testid="price-and-discounted-price"]'), score: t(c, '[data-testid="review-score"]'),
    dist: t(c, '[data-testid="distance"]'), room: t(c, '[data-testid="recommended-units"]'),
    url: (c.querySelector('a[data-testid="title-link"]')?.href || '').split('?')[0] || null }));
};
async function booking(p, d) {
  const url = `https://www.booking.com/searchresults.html?latitude=${h.lat}&longitude=${h.lon}&dest_type=latlong&checkin=${d}&checkout=${addDays(d, 1)}&group_adults=2&no_rooms=1&group_children=0&selected_currency=SAR&lang=en-gb&order=distance_from_search`;
  await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
  let cards = [];
  for (let i = 0; i < 20; i++) { await sleep(1000); cards = await p.evaluate(BK_EXTRACT); if (cards.length && i > 3) break; }
  if (cards.length) {
    for (let k = 0; k < 3; k++) {
      await p.mouse.wheel(0, 8000); await sleep(1500);
      const more = p.getByRole('button', { name: /Load more results/i }).first();
      if (k < 2 && await more.count()) { await more.click({ timeout: 3000 }).catch(() => {}); await sleep(2500); }
    }
    cards = await p.evaluate(BK_EXTRACT);
  }
  return { src: 'booking', date: d, cards };
}

async function agoda(p, d) {
  const props = new Map(); const on = async r => { if (!r.url().includes('/graphql/search')) return; try { const j = await r.json(); const d0 = j?.data || {}; for (const k of Object.keys(d0)) for (const x of (d0[k]?.properties || [])) if (x?.propertyId) props.set(x.propertyId, x); } catch {} };
  p.on('response', on);
  for (const area of (h.agoda_areas || [h.agoda_area])) {
    const url = `https://www.agoda.com/search?area=${area}&selectedproperty=${h.agoda_own}&checkIn=${d}&los=1&rooms=1&adults=2&children=0&currency=SAR&locale=en-us&cid=-1`;
    await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(9000);
    for (let i = 0; i < 3; i++) { await p.mouse.wheel(0, 3000); await sleep(1500); }
  }
  if (!props.has(h.agoda_own)) {  // our listing is not in the area list: open a search for our own property
    await p.goto(`https://www.agoda.com/search?city=${h.agoda_city}&selectedproperty=${h.agoda_own}&checkIn=${d}&los=1&rooms=1&adults=2&children=0&currency=SAR&locale=en-us&cid=-1`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(7000);
  }
  p.off('response', on);
  const cards = [...props.values()].map(x => {
    const ci = x.content?.informationSummary || {}; const geo = ci.geoInfo || {};
    const ro = x.pricing?.offers?.[0]?.roomOffers?.[0]?.room; const pr = ro?.pricing?.[0]?.price?.perRoomPerNight;
    return { id: x.propertyId, name: ci.displayName || ci.defaultName, lat: geo.latitude, lon: geo.longitude, type: ci.accommodation?.accommodationName || ci.propertyType,
      score: x.content?.reviews?.cumulative?.score ?? null, link: ci.propertyLinks?.propertyPage || null,
      available: !!x.pricing?.isAvailable, net: pr?.exclusive?.display ?? null, gross: pr?.inclusive?.display ?? null };
  });
  return { src: 'agoda', date: d, cards };
}

function gparse(t) {
  let s = t.indexOf('All options'); let blk = s >= 0 ? t.slice(s + 11) : '';
  const ends = ['Sponsored', 'Currency', 'View more options', 'Similar hotels', 'Nearby hotels'].map(x => blk.indexOf(x)).filter(i => i > 0);
  blk = blk.slice(0, ends.length ? Math.min(...ends) : blk.length);
  const offers = []; let prov = null;
  for (const l of blk.split('\n').map(x => x.trim()).filter(Boolean)) {
    const m = l.match(/^SAR\s?([\d,]+)$/);
    if (m) { if (prov && !offers.find(o => o.p === prov)) offers.push({ p: prov, v: +m[1].replace(/,/g, '') }); prov = null; continue; }
    if (l === 'Visit site' || /^(Get price|View prices|Check availability)$/i.test(l) || l === ',' || /guests?$/.test(l) || /^·/.test(l) || /cancellation/i.test(l) || /left$/.test(l) || /^Total|^Nightly/i.test(l)) continue;
    if (/^Official site$/i.test(l)) { if (prov) prov += ' (official site)'; continue; }
    if (!prov) prov = l;
  }
  return { offers, mode: t.includes('Nightly total') ? 'total' : (t.includes('Nightly price') ? 'price' : '?') };
}
let gcaptcha = 0;
const STOP = new Set(['hotel', 'hotels', 'apartments', 'apartment', 'serviced', 'suites', 'suite', 'residence', 'residences', 'the', 'by', 'al', 'el', 'and', 'riyadh', 'jeddah', 'units', 'furnished', 'hospitality', 'للشقق', 'المخدومة', 'المخدومه', 'فندق', 'شقق', 'الفندقية']);
function toks(n) { return (n || '').toLowerCase().replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/).filter(w => w.length > 1 && !STOP.has(w)); }
function same(a, b) { const A = toks(a), B = new Set(toks(b)); if (!A.length || !B.size) return false; const hit = A.filter(w => B.has(w)).length; return hit / A.length >= 0.6 || (hit >= 2 && hit / A.length >= 0.4); }
async function resolve(p, name) {
  await p.goto('https://www.google.com/travel/search?q=' + encodeURIComponent(name + ' ' + h.city) + '&hl=en&gl=sa&curr=SAR', { waitUntil: 'domcontentloaded', timeout: 45000 });
  await sleep(4000);
  const t = await p.evaluate(() => document.body.innerText.slice(0, 2000));
  if (/unusual traffic|not a robot/i.test(t)) { gcaptcha++; return undefined; }
  const cands = await p.evaluate(() => { const r = [], seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/travel/hotels/entity/"]')) { const id = (a.getAttribute('href').match(/entity\/([A-Za-z0-9_-]{10,})/) || [])[1]; if (!id || seen.has(id)) continue; seen.add(id);
      const lab = (a.getAttribute('aria-label') || '').replace(/^Open | in a new tab\.?$/g, ''); let c = a, nm = lab; for (let i = 0; i < 8 && c && !nm; i++) { const hh = c.querySelector && c.querySelector('h2,h3'); if (hh) nm = hh.innerText; c = c.parentElement; }
      r.push({ id, name: nm || lab }); } return r; });
  const hit = cands.find(c => same(name, c.name) || same(c.name, name));
  return hit ? hit.id : null;
}
async function google(p, j) {
  if (gcaptcha >= 3) return { ...j, skipped: true };
  await p.goto(`https://www.google.com/travel/hotels/entity/${j.id}/prices?hl=en&gl=sa&curr=SAR&ts=${gts(j.date, addDays(j.date, 1))}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await sleep(3500);
  let t = await p.evaluate(() => document.body.innerText);
  if (/unusual traffic|not a robot/i.test(t)) { gcaptcha++; return { ...j, captcha: true }; }
  const more = p.getByText(/View more options/).first();
  if (await more.count()) { await more.click({ timeout: 3000 }).catch(() => {}); await sleep(1200); t = await p.evaluate(() => document.body.innerText); }
  return { ...j, ...gparse(t) };
}

(async () => {
  const t0 = Date.now();
  const b = await pw.chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME, args: ['--no-sandbox'] } : {});
  const ctx = await b.newContext({ locale: 'en-US', viewport: { width: 1366, height: 1000 }, userAgent: UA });
  const only = (process.env.ONLY || 'booking,agoda,google').split(',');
  const res = { hotel: KEY, dates: DATES, started: new Date().toISOString() };
  const save = () => fs.writeFileSync(OUTF, JSON.stringify({ ...res, finished: new Date().toISOString() }));
  // Watchdog: whatever happens, save what we have and stop after 30 minutes (GitHub step limit is 38).
  setTimeout(() => { console.log('watchdog: 30 minutes reached, saving partial results'); save(); process.exit(0); }, +(process.env.HARD_LIMIT_MIN || 30) * 60e3).unref();
  if (only.includes('booking')) { res.booking = await pool(ctx, 3, DATES, booking, +(process.env.BUDGET_BOOKING || 9)); save(); console.log(KEY, 'booking', res.booking.filter(r => r.cards?.length).length, '/', DATES.length, Math.round((Date.now() - t0) / 1000) + 's'); }
  if (only.includes('agoda')) { res.agoda = await pool(ctx, 4, DATES, agoda, +(process.env.BUDGET_AGODA || 10)); save(); console.log(KEY, 'agoda', res.agoda.filter(r => r.cards?.length).length, '/', DATES.length, Math.round((Date.now() - t0) / 1000) + 's'); }
  if (only.includes('google')) {
    // nearest places: from the last published Booking.com + Agoda tables of this hotel (within the radius)
    let prev = {}, gmap = {}; try { prev = JSON.parse(fs.readFileSync(process.env.PREV, 'utf8')); } catch {} try { gmap = JSON.parse(fs.readFileSync(process.env.GMAP, 'utf8')); } catch {}
    const seen = new Map();
    for (const sid of ['booking', 'agoda']) for (const r of (prev.tables?.[sid]?.rows || [])) { const k = toks(r.name).join(' '); if (!k || r.km == null || r.km > h.radius) continue; if (!seen.has(k) || seen.get(k).km > r.km) seen.set(k, { name: r.name, km: r.km }); }
    const cand = [...seen.values()].sort((a, b) => a.km - b.km);
    const own = h.google.find(c => c.seg === 'own'); const ents = []; const rp = await ctx.newPage(); res.gmap = {};
    const now = Date.now();
    for (const c of cand) {
      if (ents.length >= 20 || gcaptcha >= 3) break;
      let e = gmap[c.name];
      if (!e || (e.id === null && now - (e.t || 0) > 7 * 864e5)) { let id; try { id = await resolve(rp, c.name); } catch { id = undefined; } if (id === undefined) continue; e = { id, t: now }; }
      res.gmap[c.name] = e;
      if (e.id && e.id !== own.id && !ents.find(x => x.id === e.id)) ents.push({ key: 'g' + ents.length, name: c.name, id: e.id, km: Math.round(c.km * 100) / 100, seg: 'near' });
    }
    await rp.close();
    res.gents = [{ ...own, km: 0 }, ...ents];
    console.log(KEY, 'google places', ents.length, 'of', cand.length, 'candidates');
    const from = +(process.env.DAY_FROM || 0), to = +(process.env.DAY_TO || DATES.length);
    const jobs = []; for (const d of DATES.slice(from, to)) for (const c of res.gents) jobs.push({ key: c.key, id: c.id, date: d });
    res.google = await pool(ctx, 6, jobs, google, +(process.env.BUDGET_GOOGLE || 22));
    console.log(KEY, 'google', res.google.filter(r => r.offers?.length).length, '/', jobs.length, 'captcha', gcaptcha, Math.round((Date.now() - t0) / 1000) + 's');
  }
  res.finished = new Date().toISOString();
  fs.writeFileSync(OUTF, JSON.stringify(res));
  await b.close();
})();
