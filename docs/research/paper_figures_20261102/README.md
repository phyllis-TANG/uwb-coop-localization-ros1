# English paper figures

This PR adds the four reviewed paper figures as PDF, PNG and editable SVG, with English captions and plotting scripts. It does not modify estimation code or experiments.

| Figure | PDF |
|---|---|
| Static field main figure | [PDF](static/figures/static_five_bag_main_ieee.pdf) |
| Static calibration-effect figure | [PDF](static/figures/static_calibration_effects_ieee.pdf) |
| Controlled PR92 simulation | [PDF](simulation/figures/pr92_paired_main_ieee.pdf) |
| Auxiliary field summary | [PDF](simulation/figures/field_interaction_summary_ieee.pdf) |

The scripts were locally rerun and the rendered layouts and PDF fonts inspected. Static-field input tables and detailed verification receipts are not published in this figure-only PR. Reproduction of the static plot requires the operator's existing compact plotting table. The simulation inputs are already-public PR92 values.

Static uncertainty whiskers denote conditional reference sensitivity, not statistical confidence intervals. The field and simulation figures have different scopes; use their corresponding captions.

[Remaining manuscript figure/table tasks](FIGURE_STATUS.md). No new data collection is requested by this delivery.

Automatic approval review rejected broader publication of a duplicate historical freeze manifest, full local result data, detailed static verification and metric-rich documentation. Those payloads are omitted. This PR is limited to authorized figures, captions, plotting code and already-public simulation inputs.
