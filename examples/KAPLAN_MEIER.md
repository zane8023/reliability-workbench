# Kaplan–Meier point estimate (preview)

From the project root, after following INSTALL.md:

```powershell
.\.venv\Scripts\python.exe -c "from app.services.kaplan_meier import kaplan_meier; import json; print(json.dumps(kaplan_meier([1,2,2],[2,3],time_unit='hour'), indent=2))"
```

Synthetic observations: three failures at 1, 2 and 2 hours and two right-censored observations at 2 and 3 hours. Survival after 1 hour is 0.8 and after 2 hours is 0.4; subjects censored at a failure time remain at risk for that time. This is a point estimate under independent non-informative right censoring, not a confidence interval, fitted lifetime model or prediction. No delayed entry, left or interval censoring is supported.

Provide time values at appropriate numeric precision: a float already rounded by the caller cannot be restored. Integer times that cannot be represented exactly as a float are rejected.
