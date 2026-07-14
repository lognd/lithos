# Bring-up procedure: la_jig8

Tap header: `tap_header_2x08_254` (2x8 2.54mm shrouded box header (Wurth WR-BHD 61201621621 class), 8 channel(s), channel N on odd pin 2N+1 (1,3,..,15); ground on every even pin (2,4,..,16), ground interleaved return: one ground pin adjacent to every signal pin (ribbon-cable GS pairing), keying shrouded polarizing notch + pin-1 corner marking). Reference: Wurth Elektronik WR-BHD 2.54mm shrouded box header series drawing (16-pin, 61201621621); ground-interleave/keying assignment is this repo's DFT taxonomy (WO-125, charter 40 sec. 4).

## Power-on order (safety-relevant first: rails, then clocks, buses, other signals)

- Probe TP0 / channel 0 (connector pin 1), target `LaJigSi.usb_dp_dm` (bus): no verified expectation -- claim `usb_diff_z0.lo` declared but not discharged (claim status=deferred: not model-backed discharged (calc book carries no resolved numeric for this tap -- WO117-F2 territory) -- emitted without a fabricated number). [REGOLITH-TAP ch=0 target=LaJigSi.usb_dp_dm]

## Unallocated candidates

(none -- every claim-named candidate was allocated a channel)
