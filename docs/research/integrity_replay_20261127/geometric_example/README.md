# A mirror ambiguity in range-based localisation

Run the analytic example with Python 3.8 or newer. It needs only the standard library, generates its measurements from the range equation, and writes the results to standard output.

    python3 reproduce.py

Four collinear anchors measure distances to a point 2 m from the anchor line. Reflecting the point across that line leaves every distance unchanged. An additive bias on the fourth link can vary within ±0.60 m. The test recomputes the best allowed bias separately for the exact ranges and for their first-order approximation about the original point.

| Quantity | Expected result |
|---|---:|
| Nonlinear standardised squared residual cost at the reflected point | 0 |
| Linearised cost at the same point | 12,764.739952 |
| Illustrative four-range cost budget | 9.488 |
| Separation between the two feasible points | 4.00 m |
| Lower bound on the radius of any disk containing both | 2.00 m |

The Jacobian at the original point has full column rank. Its linearisation nevertheless excludes the second feasible position. Half the distance between the two positions bounds the required radius for every possible disk centre.

The script also checks three nominal noise gates. At fixed true positions and biases, the sum of squares of independent, correctly standardised Gaussian errors has a chi-square distribution. Its upper tails for (degrees of freedom, budget) equal 0.00229179121 for (8, 24), 0.00204298966 for (9, 26) and 0.00105029973 for (8, 26). If the true bias lies within the fitted interval, profiling can only reduce the true-position score, so the nominal tail gives an upper bound on the exclusion probability under those assumptions. These are single-observation noise events.
