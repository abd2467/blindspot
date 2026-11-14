# WS1: Radar ingest (S1)


**Exact dataset links, filters and right/wrong checks:** [`docs/DATASETS.md`](../DATASETS.md). Use only those sources.

**Goal:** turn 11 NISAR GCOV granules (about 5 GB each) into one small `data/interim/stack.nc` on the shared 60 m grid, without downloading whole granules.
**You own:** `src/blindspot/s1_ingest/`. **You produce:** `stack.nc` (see `docs/CONTRACTS.md`).
**Downstream:** WS2 needs your file by **Gate 1, 09:00**. Everyone else works on fixtures until then.

Starting code: `src/blindspot/s1_ingest/ingest.py` (written from the product docs, not yet run on a real granule).

## Steps

1. **Set up access (15 min).**
   - Create an Earthdata login: https://urs.earthdata.nasa.gov/users/new
   - Approve the ASF DAAC application in your Earthdata profile if asked.
   - `pip install -r requirements.txt` (includes `earthaccess`, `h5py`).
   - Put credentials in `~/.netrc` (`machine urs.earthdata.nasa.gov login USER password PASS`) or run `python -c "import earthaccess; earthaccess.login(persist=True)"`.

2. **Find the granules (15 min).**
   ```bash
   python -m blindspot.s1_ingest.ingest search
   ```
   This writes `data/raw/granules.json`. Check every name: dual-pol (`4005_DHDH`), **track 061, descending, frame 090**. Delete any other track or frame from the JSON by hand. You should get 11 dates: 18 Jun, 30 Jun, 12 Jul, 24 Jul, 17 Aug, 29 Aug, 10 Sep, 22 Sep, 4 Oct, 16 Oct, 28 Oct. Post the list in the team chat.

3. **Check the file layout (20 min).** Open one granule remotely and print its tree:
   ```python
   import earthaccess, h5py, json
   earthaccess.login()
   g = json.load(open("data/raw/granules.json"))[0]
   f = h5py.File(earthaccess.open([g["urls"][0]])[0], "r")
   f.visit(lambda n: print(n) if "frequencyA" in n else None)
   ```
   Fix `GCOV_PATHS` in `ingest.py` if the names differ (HH, HV, x and y coordinates, projection). Note the pixel spacing and whether values are γ⁰ or σ⁰; write it in `attrs['notes']`.

4. **Confirm coverage (10 min).** Check the granule's x/y range covers the study box (`config.GRID_BOUNDS` in EPSG:32749). If track 061 frame 090 does not cover it, tell the lead immediately: the box moves (lead edits `config.py`) or we use track 125 ascending.

5. **Test on two dates (20 min).**
   ```bash
   python -m blindspot.s1_ingest.ingest build --limit 2
   python -m blindspot.contracts stack
   ```
   Open the result (`xarray.open_dataset`) and plot `10*log10(hv[0])`: you should see forest around -12 dB, rivers below -20 dB. If values are around 0.05 to 0.1 they are linear (correct); if around -12 they are already dB (wrong: convert back).

6. **Water mask (20 min).** Replace the fallback (dark HV) with the NISAR water mask product (`NISAR_WATERMASK` in Earthdata Search) resampled to the grid with nearest-neighbour. Keep the fallback if the product is not available.

7. **Run all dates (long: start early).** `python -m blindspot.s1_ingest.ingest build`. Leave it running. If the network is slow, run dates in batches and concatenate along `time`.

8. **Calibration check (15 min).** The 28 Oct granule comes from a newer processing version (P05036 vs P05023). Pick a stable forest area, compare median HV on 16 Oct vs 28 Oct. Report the jump in dB in the PR. S2 normalises it, but the number goes in the brief.

9. **Share the file.**
   ```bash
   gh release create data-v1 --title "data v1" --notes "NISAR stack" || true
   gh release upload data-v1 data/interim/stack.nc --clobber
   ```
   Post in the chat: "stack.nc uploaded, N dates, notes: …".

10. **PR.** Commit only code (never `data/interim`). Fill in the PR template, add the granule list and calibration check to the description.

## Fallbacks
- Slow downloads: drop to 6 dates (18 Jun, 17 Aug, 10 Sep, 22 Sep, 4 Oct, 16 Oct) and set them in the PR; tell WS2.
- h5py streaming fails: download whole granules to `data/raw/` for 2 or 3 dates only, or use ASF Vertex subsetting / the ASF NISAR Cookbook notebooks from the challenge resources.
- Wrong track coverage: switch to ascending track 125 frame 176 (10 dates).

## Done when
`python -m blindspot.contracts stack` passes on the real file, it is on the `data-v1` release, and WS2 has confirmed it opens.
