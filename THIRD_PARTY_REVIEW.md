# Third-party dependencies and notices

The tested Windows/Python 3.10.11 environment uses the following pinned distributions. The project license does not relicense them. This describes upstream project metadata, not a complete inventory of bundled binary notices.

| Distribution | Version | Upstream license | Official project |
| --- | --- | --- | --- |
| SciPy | 1.15.3 | BSD-3-Clause | https://pypi.org/project/scipy/1.15.3/ |
| NumPy | 2.2.6 | BSD-3-Clause | https://pypi.org/project/numpy/2.2.6/ |
| Pydantic | 2.12.5 | MIT | https://pypi.org/project/pydantic/2.12.5/ |
| pydantic-core | 2.41.5 | MIT | https://pypi.org/project/pydantic-core/2.41.5/ |
| annotated-types | 0.7.0 | MIT | https://pypi.org/project/annotated-types/0.7.0/ |
| typing-inspection | 0.4.2 | MIT | https://pypi.org/project/typing-inspection/0.4.2/ |
| typing-extensions | 4.16.0 | PSF-2.0 | https://pypi.org/project/typing-extensions/4.16.0/ |

No wheels or virtual environment are bundled with this source preview. When downloading or redistributing distributions, review and retain applicable copyright and license texts, including binary notices such as OpenBLAS, LAPACK and GCC where applicable. Consult the license files of actual distributions. The wider original project uses a separate LGPLv3 reliability library; this preview does not directly depend on or distribute it. Source provenance review remains limited.

Nelson–Aalen addition (2026-11-06): this source preview reuses this project's published Kaplan–Meier risk-set rows and the standard grouped `d/n` method. It does not import the separate `reliability` library or include the original full nonparametric service. See the example documentation for the mathematical reference and limitations. The narrow comparison with one installed upstream version does not establish the complete history of all related code; applicable third-party rights remain separate.
