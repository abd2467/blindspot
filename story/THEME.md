# Story theme: "The quiet record"

One idea carries the whole submission: **heat sensors miss part of the fire season; radar keeps listening.** Every slide, line and picture serves that idea.

**What the real data showed (updated after the integration run):** most change with no hotspot recorded came at the *start* of the fire season. From late August to September, 82% of radar-detected change had no hotspot within 1 km; in October, when Singapore's haze peaked, 23%. So we do not claim the record goes quiet when the haze is worst. We say the first burns of the season are the ones the record misses most.

## The spine (say it the same way every time)

> In October 2026 Singapore's air hit PSI 192. The satellites that count Indonesia's fires see heat, and smoke, cloud and smouldering peat can hide it. NISAR's L-band radar sees through smoke. BlindSpot uses it to map where the land changed, checks every change against the hotspot record, and shows how much of that change had no hotspot recorded, with an honest range. On real data: 71% (range 61 to 75%) over the season, 59% without the 17 Aug pass, and most of it early in the fire season.

Short form (pitch, title slide, submission description): **NISAR's radar audits the fire hotspot record under Indonesia's 2026 haze.**

## Three acts

The season is the plot. The app's timeline, the deck and any video follow the same order.

| Act | Months | What happens | What the audience should feel |
|---|---|---|---|
| **Dry** | June to August | Peat dries out. Radar records a calm baseline: four reference dates, then the missing early-August acquisition. | Calm, measured. "We know what normal looks like." |
| **Fire** | September to October | Haze reaches Singapore (unhealthy from 4 Sep, PSI 192 on 9 Oct). Optical satellites see grey smoke. Radar shows patches of land changing; hotspots light up some of them and not others. | Tension. The record and the ground disagree. |
| **Rain** | Late October | The wet season returns. We count: how much change, how much of it had no hotspot recorded, and how sure we are. | Clarity. One number, with its range. |

## Who the story is for

The judges (Impact, Creativity, Validity, Relevance, Presentation, equal weight). Several lived through this haze in Singapore, so the hook is personal: they breathed it. The protagonist of the story is not the team or the tech; it is the **gap in the record**, and the radar that fills it.

## Voice

- Plain, exact, short. Number first, then what it means, then how sure we are.
- Say **"change with no hotspot recorded"**. Never "missed fires", "illegal", "culprit", or any company name.
- Radar change is a candidate disturbance until reviewed. Say "a place to look", not "proof".
- Every number comes from `web/data/stats.json` (our results) or a cited row in `docs/BRIEF.md` section 3 (context). If a number is not in either, it does not go on a slide.
- No exclamation marks, no emoji, no "revolutionary".

## Visual language (the BlindSpot design system)

- **Black space, one bright planet.** Dark slides, generous empty space, one idea and at most one big number per slide.
- **Colour means one thing everywhere:**
  - cyan `radar` #4CC9F0: the radar signal, NISAR, anything we measured
  - violet `unrecorded` #A78BFA: change with no hotspot recorded (the story's subject)
  - amber `recorded` #FFB020: change with a hotspot recorded
  - coral `haze` #FF8A65: Singapore's PSI and the smoke, nothing else
- **Type:** Space Grotesk for titles and the big numbers, Inter for sentences, JetBrains Mono for small labels and dates.
- **Motif:** the logo. A ring (the record around the Earth) with an opening (the gap smoke leaves) and a radar pulse reaching the spot at its centre (the change we found). The title and closing slides use it large; nowhere else.
- **Pictures:** real screens from the app (globe, map with patches, patch chart). No stock photos, no fire clip art, no photos of people.

## Lines we reuse

- "The first burns of the season are the ones the record misses most."
- "Radar keeps listening."
- "Not a change map: an audit of the fire record."
- "A place to look, not proof of fire."
- "Every NISAR track, every 12 days."

## What we never claim

That a patch was an illegal fire, who caused it, or that a specific patch caused Singapore's haze. BlindSpot shows where land changed under the smoke and what the hotspot record says about it.
