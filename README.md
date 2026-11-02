# Reliability Workbench

[中文介绍](README.zh-CN.md)

An engineering workbench for reliability analysis and field failure risk assessment, connecting data preparation, test-condition checks, lifetime modeling, and reproducible reports, with configurable domain knowledge and model parameters.

## What is available here

This repository currently contains project documentation. **No installable public source release or installation package is available yet.** A small accelerated-life calculation candidate has passed a synthetic example and six focused tests in a fresh Windows/Python 3.10.11 x64 virtual environment, with fixed PyPI wheel hashes checked and dependency consistency verified. Source provenance and license review remain open. This does not validate the complete workbench, all models, or field predictions.

The first public calculation milestone will target a reproducible synthetic case with explicit inputs, units, assumptions, reference results, and limitations. Full analysis workflows, visual reports, AI integration, and field-risk forecasting have not been released or validated as a public version in this repository.

## Analysis and validation principles

- Numerical results must come from reviewable methods; AI-assisted input and explanation do not replace numerical validation.
- Accelerated extrapolation requires a suitable failure mechanism, model, test conditions, and supporting data.
- Missing conditions must be identified rather than filled with invented real-world parameters.
- Example parameters are demonstrations, not recommendations for real products.
- Engineering analysis is not a product-life guarantee; field predictions require appropriate validation.

## Next steps

1. Review independent dependencies, third-party copyright, and license obligations.
2. Verify synthetic numerical examples, repeatability, and boundary cases.
3. Provide Chinese and English installation instructions, examples, and result-checking steps.
4. Publish installation packages and checksums tied to validated source versions.

## License and discussion

The project license has not been selected. Public visibility alone does not grant an open-source license. Source publication follows scope, third-party notice, and validation review.

Documentation and methodology feedback is welcome through GitHub Issues. Do not submit real customer data, internal company material, sensitive personal information, or secrets. Prefer publicly shareable synthetic data when reporting problems.
