# Footgun: headless Chrome cannot render narrower than 500 px

Found on 2026-09-29 while checking the homepage at phone width.

## What happened

`chrome --headless=new --window-size=390,2600 --screenshot=...` produced a 390 px image, but the page content was **cut off on the right**. It looked like a horizontal-overflow bug in our CSS.

It was not. A test page that prints `innerWidth` showed **500** for `--window-size=390,...`. Headless Chrome lays the page out at a minimum width of 500 px, then crops the screenshot to the requested 390 px.

## What to do

- For "mobile" screenshots with plain headless Chrome, use `--window-size=500,...` (our ≤ 760 px breakpoint still applies).
- To test a true 390 px viewport, use a tool with device emulation (e.g. Chrome DevTools Protocol `Emulation.setDeviceMetricsOverride`, or Playwright's `viewport`).
- Before blaming the CSS, measure: print `innerWidth` from a tiny page with the same flags.
