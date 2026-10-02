# landing/ — marketing page

A static page: React 18 UMD with in-browser Babel, and no build step. Preview it with the `landing` entry in `.claude/launch.json`.

- **Every claim must match what the code does today.** Don't add accuracy, latency or throughput figures, and don't describe a live mode as shipped. The owner chose facts over marketing numbers.
- **`app/data.js` is real pipeline data.** `export_data.py` generates it; run `ai/.venv/bin/python landing/export_data.py` from the repo root. Never hand-edit it. It holds keypoints only and no video frames, because the fight footage isn't ours to publish.
- **Red and blue always mean corners, and orange is only the brand and CTA colour**, so a strike mark never reads as a corner. Corner blue here is `#4f93ea`, not the app's `#60a5fa`, because the lighter blue fails the dataviz lightness band on this dark surface.
- **Upload is admin-only in the backend**, so the page's only call to action is signing in, not uploading.
- **Each scroll moves exactly one section.** With a mouse, trackpad or keyboard, `app/pager.js` handles it and CSS snapping stays off. On touch screens, native mandatory snapping handles it. Both read their stops from each element's `scroll-snap-align` in `app/site.css`, so a new section needs one; without it, both paths jump straight past the section.
