# Service availability and recovery on the 20 Hz display clock

After [the source-epoch replay](README.md), calculate display-time service availability at a 1 m alert limit and assess service recovery at a 1.5 m limit. The scorer needs only Python's standard library, the two numerical monitors' source levels and decisions, and their measured per-update wall times.

```sh
python score_availability.py --epochs /tmp/uwb-lunar-replay/source_epochs.csv.gz --out /tmp/uwb-lunar-replay/clock
```

The default transport delay is 0.020 s **each way**. The following command reuses exactly the same estimator outputs and host measurements with 0.100 s each way. The speed bound is in m/s. Reducing it below the actual speed can invalidate the motion allowance.

```sh
python score_availability.py --epochs /tmp/uwb-lunar-replay/source_epochs.csv.gz --out /tmp/uwb-lunar-replay/clock-slower --delay-s 0.100 --speed-bound 0.25
```

**Clock.** For each method and run, the simulated worker starts a joint job once the observation has arrived and the preceding job has finished. A result reaches both rovers after the recorded host runtime plus the assumed return transport delay. At each 0.05 s tick the display uses the latest received decision. A rejection withdraws the preceding level immediately. An accepted source from time *s* remains eligible through *s* + 2 s. The display holds the source position and adds the speed bound times its age to the source HPL. The 0.25 m/s allowance follows the bound on these generated horizontal paths. A tick declares service when the aged radius meets the selected limit. These calculations describe declared service. Comparing the moving rover's actual error against its displayed radius would additionally require the position estimates and same-time reference positions.

**Availability.** `clock_availability.csv` counts all 1,800 display ticks in [0, 90) s per rover and run, including startup, rejection, expiry and above-limit time. The update at 90 s remains part of the source analysis and has no display interval in this scoring window. The twelve primary runs and three separate screen runs are pooled separately. The detector-only monitor supplies no radius. Use `--service-limit-m` to change the default 1 m limit.

**Recovery.** `clock_recovery.csv` classifies each rover in the six injected runs and three screen runs for each numerical monitor. The injected bias begins at 30 s and is removed at 60 s. In the screen trial, the first missing range is at 33 s and the first complete set after the interruption is at 55 s. A recovery delay is reported only if service was available immediately before onset, was interrupted, and remained unavailable immediately before removal. The first qualifying post-removal tick must use an observation sourced at or after removal. Cases already unavailable at onset, receiving no service beforehand, remaining uninterrupted or regaining service before removal are separately identified. Use `--recovery-limit-m` to change the illustrative 1.5 m limit. These transitions also depend on geometry and position uncertainty.

**Reference run.** At 1 m and the default delay, the archived primary run yielded 4,797 and 5,684 available ticks out of 21,600 for the selective monitor (Rovers 1 and 2). The nine-bias baseline yielded 16,826 and 14,966. At 1.5 m, three of twelve primary fault-run rover traces met the selective-monitor recovery criterion and recovered 4.10–5.10 s after removal. In the screen runs, the nine-bias baseline recovered at the 55.05 s display tick for both rovers in all three runs. Replaying a fixed epoch file reproduces its clock results; rerunning the estimators measures new host wall times and may change the tick of delivery. Onboard compute time and over-the-air delay have not been measured here.
