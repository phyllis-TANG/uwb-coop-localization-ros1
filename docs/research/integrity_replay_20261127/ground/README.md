# Ground simulation studies

The three experiments ask how a rover's two-dimensional position bound changes during a missing UWB update, with a complementary heading sensor, and with bounded calibration errors on the anchor links. The position estimator, return-to-service decision and geometric covering-radius question have different denominators.

## Running the studies

Python 3.12, NumPy, SciPy and pandas are sufficient. Run the two synthetic motion controls directly from this directory. They generate straight and constant-turn trajectories, a noisy wheel model, simulated angular rate and calibration samples. The CSV reports displacement and heading statistics.

```sh
python gyro/replay.py --controls-only --out /tmp/uwb-motion-controls
```

For a matched replay using a locally held copy of the experiment archive, supply its path. The runner loads the required inputs from that archive into a temporary directory, invokes the source files in this directory and prints each study's results. With `--out`, it also writes aggregate CSV tables. Select one experiment using `--study age`, `--study gyro` or `--study anchor`.

```sh
python replay.py --local-archive /path/to/UWB_Simulation_Extension_Replay.zip --out /tmp/uwb-ground-results
```

## Experiments

| Study | Comparison | Result on the tested inputs |
|---|---|---|
| UWB update age | A 20 Hz display uses only received odometry and a valid numerical source. With a four-second communications cycle, two source-epoch slots suppress numerical packets. Alerts have a priority path. The specified source-age validity ends after 2.00 s. | On the primary phase, the selective monitor covered the observed error at all 2,214 issued ticks per robot between 1.10 s (exclusive) and 2.00 s (inclusive). Exactly 123 of these ticks per robot occurred at 2.00 s. These ticks reuse eight held-out scenario runs from two independent noise realisations. |
| Synthetic angular rate | A common wheeled trajectory and frozen UWB solution are replayed with wheel heading, calibrated angular rate and three sensor stress cases. The estimator propagates angular uncertainty and the time since the last usable packet. | At the 50 cm alert limit, wheel-only availability was 43.87% and 39.34% for Robots 1 and 2. The nominal synthetic gyro gave 44.18% and 39.76%. With a 160 ms gyro delay, availability fell to 42.51% and 38.54%. The twelve gyro draws per robot reuse the two wheel-noise realisations. |
| Anchor bias and a 20 cm radius | Eight anchor links have independent bounded offsets and the inter-robot offset can vary by ±5 cm. An exact interval search checks whether a disk centred on the reported position covers all feasible positions. Two feasible joint states can rule out the target for every possible centre. | For this single square-layout crossing epoch, both reported-centre disks were certified at 0 and ±2 cm anchor allowance. At ±5 cm the feasible pairs exclude a 20 cm disk for both robots. The change across the three tested allowances is conditional on this geometry, measurement budget and fixed epoch. |

The residual budget in the anchor study is 26 for nine range observations with 0.04 m nominal standard deviation. Each range residual is minimised over its prescribed bias interval. A feasible pair supplies a lower bound, while subdivision with outward-rounded slant distances provides the reported-centre certificate. The gyro study uses simulated angular-rate readings and 100 stationary calibration samples. The tested ground outputs describe simulated vehicle motion and empirical display-time coverage. The shared interval-arithmetic code carries the repository's MIT notice in `LICENSE.upstream`.
