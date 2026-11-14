# Judge Q&A sheet

One page. Answers come from `docs/BRIEF.md` sections 3, 5, 6 and 10. Keep each answer to two or three sentences, then offer to show it in the app.

**Is this proof of illegal burning?**
No. BlindSpot shows where land changed under the smoke and whether the hotspot record saw a fire there. A patch with no hotspot recorded is a place to look, not proof of fire: holding anyone responsible needs ownership records and checks on the ground by the authorities. We use no concession or ownership data, by design.

**How do you know it is fire and not clearing?**
On its own, we don't, and we say so. Every patch has two separate labels: the automatic observation (hotspot recorded, none, or insufficient fire data) and, after review, an interpretation (fire supported, other disturbance, unresolved). Review uses optical imagery from clear days, RADD alerts and the HH band, which rises over flooding.

**Why not just use RADD?**
RADD is a C-band Sentinel-1 alert system for forest disturbance; it does not audit the fire record. We use RADD as an independent check on our change patches, and NISAR's L-band sees deeper into the canopy than C-band, which in Indonesian peatland separated burned land at 93 to 96% accuracy (Sudiana et al., 2025).

**What about rain and the wet season?**
Rain and soil moisture shift backscatter, so each date is normalised against the June and July reference, detection leads with HV, and a change must persist for two dates. Patches with rain influence are flagged, and the app shows GPM IMERG rainfall beside each patch's radar history.

**How sure are you of the headline number?**
It is a range, not a point. A Monte Carlo run varies hotspot positions within their pixel footprint, the matching buffer (0.5 to 2 km) and the time window, and reports the 5th to 95th percentile. A labelled reference sample gives the error-adjusted change area with a 95% interval (Olofsson et al., 2014), and synthetic burns injected into real radar data measure what we can detect.

**Why only one track and one area?**
Scope, honesty and time: 11 dual-polarisation NISAR dates exist on one track over a 2026 fire cluster near Sampit. One area done properly, with validation, is worth more than many done loosely. The pipeline is the same for any track.

**What would it take to scale?**
NISAR images most of the Earth's land every 12 days, and the pipeline streams only the window it needs and reruns in minutes on a laptop. Scaling means running it per track across Sumatra and Kalimantan through the season, so analysts see where the fire record went quiet within days, not months.

**Why does Singapore care?**
Singapore's 24-hour PSI went unhealthy on 4 September 2026 for the first time since 2023 and peaked at 192 on 9 October, with NEA tracing the smoke to Sumatra and Kalimantan. Fire evidence comes from the same hotspot record we audit. We do not link any patch to Singapore's air.

**Is the NISAR data final?**
No: most dates are NISAR's provisional release (processing P05023), and 28 October comes from a newer version (P05036). We normalise per date and flag any calibration jump, and the app says it is a research prototype.
