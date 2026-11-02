# 安装与验证预览版

已测试 Windows x64、Python 3.10.11 x64；其他平台及版本尚未验证。本预览从项目目录运行模块，尚未支持或测试 `pip install` 项目本身。依赖从官方 PyPI 下载，wheel 哈希仅适用于上述组合；需要网络，建议预留 500 MiB。

在全新项目目录打开 PowerShell，完整运行下方代码。默认从官方 PyPI 下载；也可设置 `RELIABILITY_OFFLINE_WHEELS` 指向先前下载的官方 wheel 目录，仍会检查固定 SHA256。若 `.venv` 或 `.wheelhouse` 已存在则停止，不覆盖；每步失败即停止，下载时检查哈希，仅安装 wheel，不修改全局 Python。

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
