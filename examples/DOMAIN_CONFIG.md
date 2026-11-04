# Optional domain configuration: preview

`synthetic-domain-config.json` is fictional and contains no real parameter or recommendation. `app.validators.domain_config.validate_domain_config` checks the draft record in memory; it does not load files, access a network, or call a calculator. A valid format does not establish parameter accuracy, source authenticity, model suitability or engineering safety. `verified_by_user` is a user assertion, not independently verified evidence. Null values are accepted only with `unverified`; no defaults are generated. Source text and references are not fetched or authenticated and must be assessed separately.

From the project directory, using the installed environment:

```powershell
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; from app.validators.domain_config import validate_domain_config, parse_domain_config_json; print(validate_domain_config(parse_domain_config_json(Path('examples/synthetic-domain-config.json').read_text(encoding='utf-8'))))"
```

This draft has no configuration-to-calculation integration. Range values share the declared parameter unit; the checker only compares numbers and cannot verify units or scientific applicability.

Use `parse_domain_config_json` to reject duplicate keys and non-finite JSON numbers and limit input length; callers passing already parsed objects must ensure their parser has not discarded duplicate keys.

The character limit applies after the caller has read the text into memory. Limit input bytes before reading untrusted files or network data.
