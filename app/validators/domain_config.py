"""Validate a draft metadata record; never authorize engineering calculations."""
import math
import json
import unicodedata


def parse_domain_config_json(raw):
    """Parse a bounded JSON string, rejecting duplicate keys and NaN/Infinity."""
    if not isinstance(raw, str) or len(raw) > 1000000:
        raise ValueError("JSON must be text of at most 1000000 characters")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("non-finite JSON number")
    try:
        data = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except RecursionError as exc:
        raise ValueError("JSON nesting too deep") from exc
    validate_domain_config(data)
    return data


def validate_domain_config(data):
    """Return a validation summary or raise ValueError; never modify data."""
    def obj(value, keys, label):
        if not isinstance(value, dict) or len(value) != len(keys) or set(value) != set(keys):
            raise ValueError(f"{label}: missing or unknown fields")
    def text(value, label):
        if not isinstance(value, str) or len(value) > 2000 or not any(not c.isspace() and not unicodedata.category(c).startswith("C") for c in value):
            raise ValueError(f"{label}: expected non-empty text (max 2000 characters)")
    def texts(value, label):
        if not isinstance(value, list) or len(value) > 100:
            raise ValueError(f"{label}: expected a list of at most 100 strings")
        for item in value:
            text(item, label)
    def number(value, label):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label}: expected a finite number")
        try:
            if not math.isfinite(value):
                raise ValueError(f"{label}: expected a finite number")
        except OverflowError as exc:
            raise ValueError(f"{label}: number out of range") from exc
    obj(data, ('schema_version', 'mechanism', 'model', 'parameters', 'references', 'known_limitations'), 'config')
    if data['schema_version'] != '0.1-draft':
        raise ValueError('unsupported schema_version')
    obj(data['mechanism'], ('name', 'description'), 'mechanism')
    obj(data['model'], ('name', 'scope'), 'model')
    for k, v in data['mechanism'].items(): text(v, 'mechanism.' + k)
    for k, v in data['model'].items(): text(v, 'model.' + k)
    texts(data['references'], 'references')
    texts(data['known_limitations'], 'known_limitations')
    params = data['parameters']
    if not isinstance(params, list) or not 1 <= len(params) <= 100:
        raise ValueError('parameters: expected 1 to 100 entries')
    names = set()
    for param in params:
        obj(param, ('name', 'value', 'unit', 'source', 'valid_range', 'validation_status', 'limitations'), 'parameter')
        for k in ('name', 'unit'): text(param[k], 'parameter.' + k)
        name = param['name'].strip()
        if name in names: raise ValueError('parameter: duplicate name')
        names.add(name)
        value, source, bounds = param['value'], param['source'], param['valid_range']
        if value is not None: number(value, 'parameter.value')
        if source is not None: text(source, 'parameter.source')
        if bounds is not None:
            obj(bounds, ('min', 'max'), 'parameter.valid_range')
            number(bounds['min'], 'parameter.valid_range.min')
            number(bounds['max'], 'parameter.valid_range.max')
            if bounds['min'] > bounds['max']: raise ValueError('parameter.valid_range: min exceeds max')
            if value is not None and not bounds['min'] <= value <= bounds['max']:
                raise ValueError('parameter.value outside supplied range')
        if param['validation_status'] not in ('unverified', 'verified_by_user'):
            raise ValueError('parameter.validation_status: unsupported status')
        if param['validation_status'] == 'verified_by_user' and (value is None or source is None or bounds is None):
            raise ValueError('verified_by_user requires value, source and range')
        texts(param['limitations'], 'parameter.limitations')
    return {'schema_version': '0.1-draft', 'format_valid': True,
            'engineering_validity': 'not_assessed', 'parameter_count': len(params)}
