"""Build the season slide (result.html) from web/data/stats.json."""
import json, sys, datetime as dt
stats = json.load(open(sys.argv[1])); out = sys.argv[2]; demo = len(sys.argv) > 3 and sys.argv[3] == 'demo'
cc = stats['crosscheck']; by = {d['date']: d for d in cc['by_date']}
d0 = dt.date(2026, 6, 18)
slots = [d0 + dt.timedelta(days=12 * i) for i in range(12)]          # includes the missing 5 Aug pass
W, H, BASE, SCALE = 1664, 380, 370, 140
POST_GAP = '2026-08-17'   # first pass after the missing early-August acquisition (24-day gap)
CAP = 250                 # px: tallest normal bar; the post-gap bar is clipped above this
sw = W / 12
x = lambda i: sw * (i + 0.5)
xd = lambda day: sw * ((day - d0).days / 12 + 0.5)
svg = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
# act separators
for i in (6, 11):
    svg.append(f'<line x1="{sw*i:.1f}" y1="0" x2="{sw*i:.1f}" y2="{BASE}" stroke="#232B36" stroke-width="2"/>')
svg.append(f'<line x1="0" y1="{BASE}" x2="{W}" y2="{BASE}" stroke="#5A6575" stroke-width="2"/>')
# PSI milestones
for day in (dt.date(2026, 9, 4), dt.date(2026, 10, 9)):
    svg.append(f'<line x1="{xd(day):.1f}" y1="40" x2="{xd(day):.1f}" y2="{BASE}" stroke="#FF8A65" stroke-width="2" stroke-dasharray="6 8"/>')
others = [d['change_km2'] for d in cc['by_date'] if d['date'] != POST_GAP]
vmax = max(others + [0]) or max(d['change_km2'] for d in cc['by_date']) or 1
scale = min(SCALE, CAP / vmax)
gap_top = None
for i, day in enumerate(slots):
    d = by.get(day.isoformat())
    if d is None:
        svg.append(f'<rect x="{x(i)-32:.1f}" y="{BASE-40}" width="64" height="40" fill="none" stroke="#5A6575" stroke-width="2" stroke-dasharray="4 6"/>')
        continue
    rec = max(d['change_km2'] - d['no_hotspot_km2'], 0); unr = d['no_hotspot_km2']
    hr, hu = rec * scale, unr * scale
    post_gap = d['date'] == POST_GAP
    op = ' fill-opacity="0.45"' if post_gap else ''
    clip = post_gap and hr + hu > CAP + 30
    if clip:  # keep the season readable: draw to CAP+30 and mark the break
        hu = max(CAP + 30 - hr, 0)
    if hr > 0.5: svg.append(f'<rect x="{x(i)-32:.1f}" y="{BASE-hr:.1f}" width="64" height="{hr:.1f}" fill="#FFB020"{op}/>')
    if hu > 0.5: svg.append(f'<rect x="{x(i)-32:.1f}" y="{BASE-hr-hu:.1f}" width="64" height="{hu:.1f}" fill="#A78BFA"{op}/>')
    if hr + hu <= 0.5: svg.append(f'<rect x="{x(i)-32:.1f}" y="{BASE-3}" width="64" height="3" fill="#4CC9F0"/>')
    if post_gap:
        top = BASE - hr - hu
        if clip:
            yb = top + 18
            svg.append(f'<path d="M{x(i)-36:.1f} {yb+6:.1f} L{x(i)-12:.1f} {yb-4:.1f} L{x(i)+12:.1f} {yb+6:.1f} L{x(i)+36:.1f} {yb-4:.1f}" fill="none" stroke="#000000" stroke-width="8"/>')
        gap_top = (i, top, d['change_km2'])
svg.append('</svg>')
missing = [i for i, day in enumerate(slots) if day.isoformat() not in by]
lab = lambda day: f"{day.day} {day.strftime('%b')}"
share = cc['no_hotspot_share'] * 100; lo, hi = cc['mc']['p05'] * 100, cc['mc']['p95'] * 100
# the date where the record was quietest: most no-hotspot area, leaving out the post-gap pass
q = max([d for d in cc['by_date'] if d['date'] != POST_GAP] or cc['by_date'], key=lambda d: d['no_hotspot_km2'])
rest = [d for d in cc['by_date'] if d['date'] != POST_GAP]
rest_total = sum(d['change_km2'] for d in rest)
share_wo = 100 * sum(d['no_hotspot_km2'] for d in rest) / rest_total if rest_total else None
excluded = cc.get('excluded_flags') or []
qd = dt.date.fromisoformat(q['date'])
hs = lambda n: f"{n} hotspot" + ("" if n == 1 else "s")
pinned = [
    f'<p class="label" style="position:absolute; left:16px; top:0; color:var(--radar);">DRY</p>',
    f'<p class="label" style="position:absolute; left:{sw*6+16:.0f}px; top:0; color:var(--unrecorded);">FIRE</p>',
    f'<p class="label" style="position:absolute; left:{sw*11+16:.0f}px; top:0; color:var(--radar);">RAIN</p>',
    f'<p class="label" style="position:absolute; left:{xd(dt.date(2026,9,4))+12:.0f}px; top:40px; color:var(--haze);">4 SEP · PSI UNHEALTHY</p>',
    f'<p class="label" style="position:absolute; left:{xd(dt.date(2026,10,9))-252:.0f}px; top:76px; width:240px; text-align:right; color:var(--haze);">9 OCT · PSI 192</p>',
] + [f'<p class="label" style="position:absolute; left:{x(i)-60:.0f}px; top:{BASE-84}px; width:120px; text-align:center;">NO PASS</p>' for i in missing]
if gap_top:
    gi, gt, gkm = gap_top
    pinned.append(f'<p class="label" style="position:absolute; left:{x(gi)+44:.0f}px; top:{max(gt, 110):.0f}px; width:230px; color:var(--ink-muted);">{gkm:.0f}&#160;KM² · FIRST PASS AFTER A 24-DAY GAP</p>')
dates = ''.join(f'<p class="label" style="flex:1; text-align:center;{" color:var(--ink-faint);" if i in missing else " color:var(--ink-muted);"}">{lab(day)}</p>' for i, day in enumerate(slots))
hots = ''.join(f'<p class="label" style="flex:1; text-align:center; color:var(--hotspot);">{by[day.isoformat()]["n_hotspots"] if day.isoformat() in by else "n/a"}</p>' for day in slots)
pill = '<p class="demo">DEMO VALUES</p>' if demo else ''
html = f'''<section id="result" data-transition="fade">
  <div style="display:flex; gap:24px; align-items:center;">
    <p class="eyebrow" style="margin-bottom:0; color:var(--unrecorded);">The season</p>
    {pill}
  </div>
  <div style="display:flex; gap:48px; align-items:center; margin-top:24px;">
    <p class="metric" style="font-size:176px; color:var(--unrecorded);">{share:.0f}%</p>
    <div style="display:flex; flex-direction:column; flex:1;">
      <h3 style="font-size:44px;">of radar-detected change had no fire hotspot recorded.</h3>
      <p class="body" style="margin-top:16px;">Range {lo:.0f}% to {hi:.0f}%, across {cc["total_change_km2"]:.0f}&#160;km² of change{" (" + " and ".join(excluded) + " patches left out)" if excluded else ""}.{f" Without 17 Aug, the first pass after a 24-day gap: {share_wo:.0f}%." if share_wo is not None else ""} On {lab(qd)}, radar found {q["change_km2"]:.1f}&#160;km² of change; the record held {hs(q["n_hotspots"])}.</p>
    </div>
  </div>
  <div style="position:relative; width:{W}px; height:{H}px; margin-top:40px;">
    {"".join(svg)}
    {"".join(pinned)}
  </div>
  <div style="display:flex; margin-top:8px;">{dates}</div>
  <div style="display:flex; margin-top:4px;">{hots}</div>
  <div class="footer">
    <p class="source"><span style="color:var(--unrecorded);">Violet</span>: no hotspot recorded · <span style="color:var(--recorded);">Amber</span>: hotspot recorded · <span style="color:var(--hotspot);">Numbers</span>: FIRMS hotspots since the last pass</p>
    <p class="source pageno"></p>
  </div>
  <aside>This is the season, one radar pass every 12 days. Through the dry months the radar sees a calm baseline. Then the fire season starts. Some change lines up with hotspots, in amber. But look at {lab(qd)}: the radar found {q["change_km2"]:.1f} square kilometres of change, and the record held {hs(q["n_hotspots"])}. Over the whole season, {share:.0f} percent of the change radar found had no hotspot recorded. Not a point: a range, {lo:.0f} to {hi:.0f} percent. The faded bar on 17 August is the first pass after a 24-day gap and looks like seasonal drying, so we also give the share without it: {share_wo:.0f} percent.{" (DEMO values from synthetic test data. After the integration run, rebuild this slide from web/data/stats.json.)" if demo else ""}</aside>
</section>
'''
open(out, 'w').write(html)
print(len(html), 'scale', scale)
