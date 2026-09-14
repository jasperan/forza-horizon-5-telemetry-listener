# Driver's instrument panel

## Capture notes

Actual browser captures of the vanilla HTML/CSS/Canvas dashboard. Telemetry, the track trace, and the labeled sample coach note are synthetic fixtures. The compact capture is the existing overlay mode.

Web captures use Chromium at 1440 × 1080 (desktop) and 390 × 1080 (mobile), with reduced motion enabled. Screenshots are real rendered interfaces, not image-generated UI mockups. Raster renderer examples retain their native dimensions.

## Verification — 2026-09-14

`node --check dashboard/app.js` passed. Browser checks cover five widths, synthetic telemetry rendering, coach/telemetry connection independence, the mode button, and the M shortcut. No game UDP, Oracle, or Ollama integration was exercised.

Only the existing visual surfaces were changed. The screenshots are not evidence of end-to-end service availability, accessibility certification, or production performance.
