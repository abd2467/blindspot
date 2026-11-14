# WS5: Web app


**Exact dataset links, filters and right/wrong checks:** [`docs/DATASETS.md`](../DATASETS.md). Use only those sources.

**Goal:** a fast, clear app that tells the story in under a minute and lets a judge click any patch to see the evidence.
**You own:** `web/` (except `web/data/`, which only S5 writes). **You produce:** the deployed site.

The app already works on fixture data: `web/index.html`, `web/app.js`, `web/style.css`. Plain HTML + Leaflet + Chart.js from CDNs, no build step, so it runs anywhere and deploys to GitHub Pages as-is.

## Steps

1. **Run it (5 min).**
   ```bash
   make demo      # makes fixture data in web/data
   make serve     # http://localhost:8000
   ```
   The red banner means demo data; it disappears when `manifest.json` says `"fixture": false`.

2. **Read the data contract (10 min).** `docs/CONTRACTS.md`, section `web/data/`. Your app may only rely on those files and fields. If you need a new field, ask the lead to add it in `s5_package/package.py`.

3. **Map and timeline (60 min).**
   - Make the timeline show the missing early-August date as a visible gap.
   - Add a play button that steps through dates (~1 s per date): this is the hero shot for the video.
   - Before/after: replace the "compare" checkbox with a proper swipe (e.g. the `leaflet-side-by-side` plugin) between the June baseline and the selected date.

4. **Headline panel (30 min).** Big number, range, eligible area and settings in plain words. One sentence under it: "Change with no hotspot recorded is not proof of a missed fire. Click a patch to see the evidence."

5. **Patch inspector (45 min).** Chart HV and HH against stable forest with a vertical line at the first-change date and markers for hotspot dates. Show the two labels (observation, interpretation) and the confidence tier as badges. Add rainfall as a faint bar series if `rain.json` exists.

6. **Why radar panel (30 min).** GIBS true colour for a smoky day (default 9 Oct 2026) next to the NISAR image of the nearest date. Check the GIBS WMS request works in your browser; if the image is blank, try another layer (`MODIS_Terra_CorrectedReflectance_TrueColor`) or date.

7. **Singapore panel (20 min).** PSI line with 100 (unhealthy) and annotations for 4 Sep and 9 Oct.

8. **Peat layer (20 min, optional).** If the lead adds `overlays/peat.png` to the manifest, add a toggle.

9. **Polish (60 min).** Mobile layout, loading states, legend, about/disclaimer always one click away, page title and favicon, credits for NASA data. Test in Chrome and Safari. Keep it fast: no heavy frameworks.

10. **Deploy (20 min).** The workflow `.github/workflows/pages.yml` publishes `web/` to GitHub Pages on every push to `main`. One-time setup by the repo owner: Settings → Pages → Source: **GitHub Actions**. The site appears at `https://abd2467.github.io/blindspot/`. Check it on a phone and give the URL to WS6 and the lead.

## Rules
- Words: "no hotspot recorded", never "missed fire" or "illegal". No company names, no concession maps.
- Every number on screen comes from `web/data/`; nothing typed by hand.
- Colour must not be the only signal (labels or patterns for colour-blind users).

## Done when
The deployed URL works on real data, a first-time user can find the headline, play the timeline, open a patch and read its evidence, and the disclaimer is visible.
