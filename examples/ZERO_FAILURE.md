# Zero-failure binomial bound — experimental preview

This experiment computes the one-sided exact binomial upper confidence limit for zero observed events in a defined test window. It assumes independent units with a common probability and known binary outcomes over the same window. It is a probability for that test, not a failure rate, a Bayesian credible interval, the rule-of-three approximation, or a field forecast. Labels are user-supplied and not validated as true.

Run from the project root using the documented Windows environment:

```powershell
.\.venv\Scripts\python.exe -c "from app.services.zero_failure_binomial import zero_failure_upper; print(zero_failure_upper(100,0.95,event_definition='Synthetic failure',observation_window='Synthetic fixed window'))"
```

For synthetic n=100 and confidence 0.95, the upper probability is approximately 0.02951304960704. Inputs outside the explicit range and outputs too small for a normal floating-point number are rejected. This is an experimental feature, not an engineering guarantee.
