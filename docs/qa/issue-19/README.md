# Public access test from Pakistan · #19

Issue: [fredyxander/bailarines-del-sar#19](https://github.com/fredyxander/bailarines-del-sar/issues/19) (`T10`).

| | |
|---|---|
| Date | 16 November 2026 |
| Time | about 03:56 PKT |
| Place | Pakistan |
| Device | Desktop. Browser and operating system were **not recorded** |
| Tester | Moneeb Hussain |
| Page load time | **Not recorded** |

## Objective

Check that the live Surface Dance app can be opened and used from Pakistan without a team login.

Live app: https://fredyxander.github.io/bailarines-del-sar/

## Scope

What this session covered: the live app, map tiles, NISAR imagery, the before/after view, HH and HV, the What changed view, Play while it was running, and the mission panel (dates, collection, CRID, change stats).

What this session did not cover is listed under remaining checks. The GitHub repository and the slide deck were not opened on their own.

## Results

| Check | Result | Basis |
|---|---|---|
| Live app opens from Pakistan without a team login | PASS | Tester confirmed the page loaded |
| Map tiles visible | PASS | Basemap is visible around the radar scene in all three screenshots |
| Real NISAR imagery visible | PASS | Tester confirmed it. Radar scene is on the map in all three screenshots |
| Before/after comparison | PASS | Tester confirmed it. [01-two-dates-hh.jpg](01-two-dates-hh.jpg) shows Two dates, 22 Jun 2026 and 20 Oct 2026 |
| HH channel | PASS | Tester confirmed it. HH is selected in the first and third screenshots |
| HV channel | PASS | Tester confirmed it. HV is selected in [02-what-changed-hv.jpg](02-what-changed-hv.jpg) |
| What changed view | PASS | Tester confirmed it. Second screenshot shows the red/blue change overlay, legend, and opacity control |
| Play running | PASS | [01-two-dates-hh.jpg](01-two-dates-hh.jpg) shows the control labelled **Pause**. The app uses that label only while playback is running. A separate click on Pause was not recorded |
| Mission details | PASS | Tester confirmed dates, collection, CRID, and change stats. The panel shows 22 Jun 2026 / 20 Oct 2026, PROVISIONAL, P05023, and the HH/HV change table |
| Open water line on the panel | PASS | Visible in the screenshots: 329.5 → 344 km² (+14.5 · +4.4%) |
| Change types view displayed | PASS | [03-change-types.jpg](03-change-types.jpg) shows that mode open, with the color overlay and the class legend. The classes were not checked against the source data in this test |
| Why it changed text visible | PASS | The lead line is visible in the first two screenshots. The third shows the expanded notes. EN/ES switching was not tested |
| Read the dance | NOT VERIFIED | The button is visible. It was not opened |
| Ask the radar | NOT VERIFIED | The button is visible. Guided questions and the free-question box were not used |
| GitHub repository without login | NOT VERIFIED | Not opened as its own check. The Source link in the header was not followed |
| Slide deck without login | NOT VERIFIED | Not opened |
| Phone | NOT VERIFIED | Not tested |
| Load time | NOT VERIFIED | Not recorded |

No broken control was seen in the checks marked PASS.

## Screenshots

The images are the original captures. They show only the public app. No account, password, token, or private path is visible.

| File | What it shows |
|---|---|
| [01-two-dates-hh.jpg](01-two-dates-hh.jpg) | Two dates, HH selected, radar over the basemap, slider, **Pause**, T+ 120 days, mission panel |
| [02-what-changed-hv.jpg](02-what-changed-hv.jpg) | What changed, HV selected, red/blue overlay, opacity slider, Play the dance (not running) |
| [03-change-types.jpg](03-change-types.jpg) | Change types view, class legend, and the expanded Why it changed notes |

Three images were supplied with the test notes. The request text said two.

## Remaining checks

These are still required before #19 can be closed:

- Open https://github.com/fredyxander/bailarines-del-sar in a browser that is not signed into a team account.
- Open the slide deck from #18 and confirm it does not ask for a login. Record the exact URL.
- Phone, if it can still be done.
- Optional for this issue’s comment thread: Read the dance, Ask the radar (including the first model download), and a timed page load.

## Verdict

The desktop live app passed the checks the tester confirmed, plus the views visible in the screenshots. This does **not** finish #19. The repository link, the slide deck, and phone access are still unverified.
