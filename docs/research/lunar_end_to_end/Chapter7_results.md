# Chapter 7. Cooperative localization on reconstructed lunar terrain

### Terrain and route geometry

We simulated cooperative ranging on two short stretches of terrain reconstructed from the synthetic LiDAR point clouds of the LuSNAR Moon_1 sequence. Both stretches passed the same checks for point-cloud support and local height consistency along the vehicle footprints. Car 2 followed the source trajectory from 5.44 to 9.86 s on the main segment and from 109.66 to 114.00 s on the second segment. At each scene time, Car 1 occupied the pose 5 s farther along the same trajectory. The resulting antenna separations were 10.81–11.79 m and 10.75–12.55 m, respectively. Four synthetic anchors supplied eight simulated anchor-to-vehicle slant ranges per epoch, and a ninth range linked the two vehicles. The estimator used known terrain-derived antenna heights to estimate horizontal positions. Figure 1 locates both evaluation routes alongside a historical Isaac Lab replay. [Main route](continuous/ROUTE.json) · [Second route](replication/ROUTE.json) · [Route geometry and protocol](replication/REPORT.md)

### Effect of modelling a changing inter-vehicle range bias

For each vehicle, we compared the trajectory root-mean-square position error (RMSE) of a constant peer-bias model (M2) with that of a model that also estimates a linear change in peer bias (M3). We report the mean paired reduction, M2 minus M3, over all 10 finite seed pairs per condition and segment. With a 0.30 m ramp in the peer range, Car 1 and Car 2 gained **6.070 and 5.107 mm** on the main segment and **5.631 and 4.918 mm** on the second. On each segment, 10 of 10 seeds improved for Car 1 and 9 of 10 for Car 2. Adding a 0.15 m error to one Car 2 motion increment during the ramp gave respective gains of 6.180 and 4.217 mm on the main segment and 5.747 and 3.983 mm on the second. With zero injected peer bias, the normal-condition reductions were only +0.073 and +0.014 mm on the main segment and +0.170 and −0.100 mm on the second. With the motion error alone, they were +0.070 and +0.003 mm, and +0.163 and −0.105 mm, respectively. The negative values indicate a small increase in Car 2 error. All-finite means include one pair that failed numerical acceptance in the main segment’s combined condition and one in the second segment’s motion-only condition. [Original main-segment pairs](continuous/PAIRS.csv) · [Both segments, per-seed pairs and acceptance states](replication/PAIRS.csv)

### What the 10 cm protection requirement asks of a position fix

RMSE measures how closely an estimate follows the reference trajectory. A 10 cm horizontal protection disk must also cover every Car 1 position compatible with the observations under the stated model. At the first main-segment epoch, even with peer bias fixed at zero and antenna heights known, two joint positions for the vehicles satisfy the nine-range test at a 4 cm noise scale. Their weighted sums of squared residuals are at most 19.961 and 21.975, both below the threshold of 26. Projecting the two solutions onto Car 1 gives points approximately **31.04 cm apart** (Figure 2). By the triangle inequality, any disk covering both needs a radius of at least half their separation, giving a conservative lower bound of **15.51 cm** regardless of the center. A 10 cm disk therefore fails at this epoch even though the trend model improved mean RMSE in the ramp trials. The radius analysis covers four selected state times, at indices 0 and 11 on each segment. Vehicle-level online recovery rates and generalization to new routes remain questions for future work. [Joint positions](round2_radius/witnesses/main_start_normal.json) · [Exact numerical check](defense_figures/witness_check.json) · [Four-epoch radius comparison](round2_radius/attribution.csv)

## Figures and source data

### Figure 1. Evaluation routes and historical scene replay (main text)

Left, a frame at 7.00 s from the October 30 Isaac Lab demonstration video shows terrestrial rover tracks replayed on a LuSNAR-derived display mesh. The craters outside the cooperative area are decorative. Right, plan views drawn from the two evaluation segments show the antenna tracks and synthetic anchors in the local moon_map frame. Circles and diamonds identify indices 0 and 11 on each track. Both cars follow the same Moon_1 source trajectory, with Car 1 sampled 5 s later than Car 2 at each scene time. The evaluation uses synthetic slant ranges and known antenna heights. Green encodes gridded terrain elevation at observed cells, salmon marks filled cells, and white lies outside the archived crop.

[PNG](defense_figures/01_scene.png) · [PDF](defense_figures/01_scene.pdf)

**Sources**　[Archived replay frame](defense_figures/isaac_replay_7s.png) · Main segment [route and anchors](continuous/ROUTE.json), [terrain grid](continuous/terrain.npz) · Second segment [route and anchors](replication/ROUTE.json), [terrain grid](replication/terrain.npz)

### Figure 2. Minimum enclosing radius for two feasible positions (main text)

At the first main-segment epoch, two joint four-dimensional antenna positions satisfy the P4 threshold of 26 with known heights, zero peer bias and a 4 cm range standard deviation. The weighted sums of squared residuals have upper bounds of 19.961 and 21.975. The Car 1 projections are 31.04 cm apart (rounded). By the triangle inequality, every disk containing both has radius at least half their separation, exceeding 15.51 cm. The solid circle attains this bound for the pair. The dashed circle has radius 10 cm. Both are drawn about the pair midpoint.

[PNG](defense_figures/02_witness.png) · [PDF](defense_figures/02_witness.pdf)

**Sources**　[Witness coordinates](round2_radius/witnesses/main_start_normal.json) · [Nine-range input](round2_radius/inputs/zero/main_start_normal.json) · [Certified leaf boxes](radius_resolution/results/main_start_normal/fine_matched.json.gz)

### Figure 3. Sensitivity to ranging assumptions (backup for questions on noise)

Horizontal outer radii are measured about each vehicle’s published antenna position. The first two columns retain the original observations and 4 cm noise scale. Fixing peer bias to zero changes seven radii by zero at the displayed precision and reduces the eighth (Car 2 at the middle epoch of the second segment) by approximately 0.35 cm. Halving the assumed noise scale on the old observations yields two sub-10 cm radii for Car 2, but excludes the true joint position at both segment starts. With new observations generated at the matched 2 cm scale and new position fixes, the joint truth is feasible at all four epochs and the eight radii range from 10.68 to 16.43 cm. These four epochs measure state-time geometry only.

[PNG](defense_figures/03_assumptions.png) · [PDF](defense_figures/03_assumptions.pdf)

**Sources**　[Baseline, known-zero and assumed 2 cm columns](round2_radius/attribution.csv) · [Matched 2 cm column](round2_radius/matched.csv)
