# Model Speed Baselines
Author: Max Stoddard

This folder stores tracked baseline artifacts for the model-speed programme.

Allowed here:
- exact hash manifests
- benchmark summary snapshots
- tolerance-spec snapshots once a future parallel track is approved

Not allowed here:
- raw model outputs
- JFR recordings
- GC logs
- temporary comparison reports
- generated configs

Those transient artifacts belong under `tmp/model-speed/`.

Tracked baseline artifacts should be small, reviewable, and stable enough to support exact or tolerance-based regression checks.
