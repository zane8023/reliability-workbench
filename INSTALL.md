# Install and verify the preview

Tested: Windows x64 and Python 3.10.11 x64. Other platforms and versions are unverified. This preview runs modules from the project directory; `pip install` of the project is not supported or tested. Dependencies come from official PyPI; wheel hashes apply only to this Windows/Python combination. Network access and 500 MiB free space are recommended.

From a fresh project directory in PowerShell, run the complete block. By default it downloads from official PyPI. Alternatively, set `RELIABILITY_OFFLINE_WHEELS` to a directory of previously downloaded official wheels; pinned SHA256 hashes are still checked. It refuses to overwrite an existing `.venv` or `.wheelhouse`, stops on failure, checks hashes and installs only wheels. It does not modify global Python.

```powershell
$ErrorActionPreference = 'Stop'
py -3.10 -c "import struct,sys; assert sys.version_info[:3] == (3,10,11) and struct.calcsize('P')*8 == 64"
if ($LASTEXITCODE -ne 0) { throw 'Requires Python 3.10.11 x64' }
if ((Test-Path -LiteralPath '.venv') -or (Test-Path -LiteralPath '.wheelhouse')) { throw 'Use a fresh directory: .venv or .wheelhouse already exists' }
py -3.10 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
New-Item -ItemType Directory -Path '.wheelhouse' | Out-Null
if ($env:RELIABILITY_OFFLINE_WHEELS) {
    & '.\.venv\Scripts\python.exe' -m pip --isolated download --disable-pip-version-check --no-cache-dir --only-binary=:all: --no-deps --require-hashes --no-index --find-links $env:RELIABILITY_OFFLINE_WHEELS --dest '.wheelhouse' -r requirements-win-py310.txt
} else {
    & '.\.venv\Scripts\python.exe' -m pip --isolated download --disable-pip-version-check --no-cache-dir --only-binary=:all: --no-deps --require-hashes --index-url 'https://pypi.org/simple' --dest '.wheelhouse' -r requirements-win-py310.txt
}
if ($LASTEXITCODE -ne 0) { throw 'wheel download or hash verification failed' }
& '.\.venv\Scripts\python.exe' -m pip --isolated install --disable-pip-version-check --no-index --no-deps --require-hashes --find-links '.wheelhouse' -r requirements-win-py310.txt
if ($LASTEXITCODE -ne 0) { throw 'offline wheel installation failed' }
& '.\.venv\Scripts\python.exe' -m pip check
if ($LASTEXITCODE -ne 0) { throw 'dependency check failed' }
& '.\.venv\Scripts\python.exe' -B -m examples.synthetic_arrhenius
if ($LASTEXITCODE -ne 0) { throw 'synthetic example failed' }
& '.\.venv\Scripts\python.exe' -B -m examples.synthetic_fixed_reliability
if ($LASTEXITCODE -ne 0) { throw 'fixed reliability example failed' }
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'test suite failed' }
```
