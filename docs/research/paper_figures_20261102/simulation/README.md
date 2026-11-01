# Controlled simulation and auxiliary field-summary figures

`figures/pr92_paired_main_ieee` is the four-panel controlled PR92 simulation figure, not a static field experiment. It uses the committed 96 configuration-level robot rows and 16 paired contrast rows. `plot_figures.py` independently checks D/C/T arithmetic and produces PDF/PNG/SVG figures.

`figures/field_interaction_summary_ieee` is an auxiliary plot of the rounded v003 manuscript summary. Its values and reference-sensitivity bounds have now been cross-checked against the full-precision uploaded field summaries, with maximum difference 4.80e-7 m². Prefer the per-bag figures in `../static/` for the main manuscript. The older missing-data state has been resolved; no blank input template is retained here.

Reproduce with `python3 plot_figures.py`. Both scripts require NumPy and Matplotlib; no solver is called. Historical source documents remain at their existing repository locations; they are not duplicated here. Source versions and URLs are listed in `source_manifest.json`; entries marked bundled=false are external provenance links. Their earlier missing-input statements are archival, not current task status.

The simulation removes an injected fixed Car2 range-bias vector exactly and reinitializes each treatment. Its placement interaction is a processing-chain effect, not an isolated steady-state peer-factor effect. The Robot 1 interaction direction differs from the field result and remains visible. The auxiliary field whiskers are conditional reference sensitivity, not confidence intervals.
