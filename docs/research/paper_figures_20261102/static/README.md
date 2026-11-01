# Static field figures

Reviewed figures: `figures/static_five_bag_main_ieee` and `figures/static_calibration_effects_ieee`, in PDF/PNG/SVG. English captions are in CAPTIONS_EN.txt.

`make_figures.py` regenerates the figures from the operator's compact CSV at `data/selected_five_bag_metrics.csv`. That non-public input is deliberately not included in this figure-only PR. Use the existing local plotting table; the script does not run a localization solver. Requires Python, NumPy and Matplotlib.

Saved-summary arithmetic and rendered layouts were checked locally. Original trajectory epoch identities were not independently rechecked. Whiskers are conditional reference sensitivity, not confidence intervals. See the captions for interpretation.
