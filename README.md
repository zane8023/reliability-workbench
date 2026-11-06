# Reliability Workbench

[中文](README.zh-CN.md) | [Install and verify](INSTALL.md) | [Examples](examples/README.md)

An early reliability-engineering preview. It supports **forward Arrhenius acceleration factors with optional life conversion**, **fixed-parameter Weibull and exponential reliability metrics** (reliability, failure probability, hazard and quantile), and **exponential point estimation** from exact failures and right-censored observations. A local HTML report can display selected fields from saved results without rerunning a calculator; charts are not included. Users supply the parameters; the examples use invented values. Other acceleration models and the generic parameter-solver entry point are blocked. Weibull fitting, lifetime parameter confidence intervals, calibration and field forecasting are not included.

On Windows x64/Python 3.10.11, three numerical examples and 46 focused tests passed in an isolated environment using fixed, hash-verified official PyPI wheels. Other environments and broader models are unverified. Run modules from the project directory; `pip install` of this project is not provided or tested. See [installation and verification](INSTALL.md).

The exponential estimate assumes independent identically distributed exponential lifetimes and independent, non-informative censoring. It does not validate these assumptions; few failures can produce imprecise estimates. A synthetic check does not validate the failure mechanism, parameters, product life, field prediction, or fitness for a decision. Domain knowledge, comprehensive illustrated reports, field-risk workflows and AI integration remain future goals, not part of this preview.

This preview also provides [Kaplan–Meier point estimates](examples/KAPLAN_MEIER.md) for exact failures and right-censored observations. It assumes independent non-informative censoring and does not provide confidence intervals or extrapolation. The 60-test suite and synthetic examples passed in an isolated Windows x64/Python 3.10.11 environment using fixed, hash-verified wheels.

An optional [domain configuration format checker](examples/DOMAIN_CONFIG.md) checks an illustrative metadata record without connecting to calculations. Format validation does not establish source authenticity or engineering suitability.

**Experimental [zero-failure one-sided binomial bound](examples/ZERO_FAILURE.md)** is available. It is a one-sided confidence upper bound for test-window probability, not a rate or field forecast. The 65-test suite was checked in the documented Windows/Python 3.10.11 environment.

The maintainer selected Apache-2.0 for project content they can authorize. Third-party components retain their own terms; see [LICENSE](LICENSE), [NOTICE](NOTICE) and [third-party review](THIRD_PARTY_REVIEW.md).

## Local in-memory CSV flow candidate

This experimental in-process source preview connects synthetic CSV bytes to the existing exponential point estimator and selected-field HTML report on reviewed public baseline c2a0101. It preserves the newer input-validation and report fixes, adds no file, storage, network or web service, and retains the original adapters unchanged. The original candidate has historical Windows/Python 3.10.11 validation; that does not constitute Windows validation of this integration revision. The revised integration passed 67 targeted Linux checks; it has not had a new full-suite, Windows or visual validation. This is not a complete workbench, a project-installable package or a validated field forecast. See [the English example and CSV contract](examples/LOCAL_CSV_FLOW.md) and [Chinese example](examples/LOCAL_CSV_FLOW.zh-CN.md).
