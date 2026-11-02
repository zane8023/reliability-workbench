# Synthetic examples

The Arrhenius example and fixed-parameter Weibull example use invented inputs; they are not recommendations or validated field predictions. In the fixed-parameter example, time and scale share the declared unit; an exponential rate is expressed per that unit. The quantile is the time at a user-supplied failure probability. At time zero with a Weibull shape below one, hazard is singular and returned as `null` with a warning. A hazard or positive quantile outside floating-point representation is rejected; probabilities may round to zero or one at extreme exposure.

These examples do not fit data, calibrate a mechanism, or validate a market forecast. See the tests and installation instructions for the checked scope.
