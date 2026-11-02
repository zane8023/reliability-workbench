# Reliability Workbench

[中文](README.zh-CN.md) | [Install and verify](INSTALL.md) | [Examples](examples/README.md)

An early reliability-engineering preview. It supports **forward Arrhenius acceleration factors with optional life conversion**, **fixed-parameter Weibull and exponential reliability metrics** (reliability, failure probability, hazard and quantile), and **exponential point estimation** from exact failures and right-censored observations. Users supply the parameters; the example uses invented values. Other acceleration models and all parameter solving are blocked at public entry points. Weibull fitting, interval estimates, calibration and field forecasting are not included.

On Windows x64/Python 3.10.11, three synthetic examples and 37 focused tests passed in an isolated environment using fixed, hash-verified official PyPI wheels. Other environments and broader models are unverified. Run modules from the project directory; `pip install` of this project is not provided or tested. See [installation and verification](INSTALL.md).

The exponential estimate assumes independent identically distributed exponential lifetimes and independent, non-informative censoring. It does not validate these assumptions; few failures can produce imprecise estimates. A synthetic check does not validate the failure mechanism, parameters, product life, field prediction, or fitness for a decision. Domain knowledge, reports, field-risk workflows and AI integration remain future goals, not part of this preview.

The maintainer selected Apache-2.0 for project content they can authorize. Third-party components retain their own terms; see [LICENSE](LICENSE), [NOTICE](NOTICE) and [third-party review](THIRD_PARTY_REVIEW.md).
