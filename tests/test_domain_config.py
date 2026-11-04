import copy
import json
import unittest
from app.validators.domain_config import validate_domain_config, parse_domain_config_json


def sample():
    return {'schema_version':'0.1-draft','mechanism':{'name':'Synthetic','description':'Fictional'},
            'model':{'name':'Example','scope':'Only an example'},'parameters':[{'name':'x','value':None,
            'unit':'unit','source':None,'valid_range':None,'validation_status':'unverified',
            'limitations':['No supplied value']}],'references':[],'known_limitations':['Not validated']}


class DomainConfigChecks(unittest.TestCase):
    def test_unknowns_are_explicit_and_input_unchanged(self):
        a=sample(); before=copy.deepcopy(a); r=validate_domain_config(a)
        self.assertEqual(a,before); self.assertEqual(r['engineering_validity'],'not_assessed')
        json.dumps(r,allow_nan=False)
    def test_verified_requires_value_source_range(self):
        a=sample(); x=a['parameters'][0]; x['validation_status']='verified_by_user'
        with self.assertRaises(ValueError): validate_domain_config(a)
        x.update(value=2,source='Synthetic reference',valid_range={'min':1,'max':3})
        self.assertTrue(validate_domain_config(a)['format_valid'])
    def test_missing_unknown_and_duplicate_fields(self):
        for mutate in (lambda a:a.pop('references'), lambda a:a.update(extra=1),
                       lambda a:a['parameters'].append(copy.deepcopy(a['parameters'][0]))):
            a=sample(); mutate(a)
            with self.assertRaises(ValueError): validate_domain_config(a)
    def test_invalid_sources_and_numbers(self):
        for field,value in [('source','  '),('source','\u200b'),('source',4),('value',True),('value',float('nan')),
                            ('value',float('inf')),('value',10**400),('validation_status','verified')]:
            a=sample(); a['parameters'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError): validate_domain_config(a)
    def test_range_and_version(self):
        for bounds in ({'min':3,'max':1},{'min':0,'max':float('inf')},{'min':0}):
            a=sample(); a['parameters'][0]['valid_range']=bounds
            with self.assertRaises(ValueError): validate_domain_config(a)
        a=sample(); a['parameters'][0].update(value=5,valid_range={'min':0,'max':2})
        with self.assertRaises(ValueError): validate_domain_config(a)
        a=sample(); a['schema_version']='future'
        with self.assertRaises(ValueError): validate_domain_config(a)

    def test_strict_json_parsing(self):
        a=sample(); self.assertEqual(parse_domain_config_json(json.dumps(a)), a)
        for raw in ('{"schema_version":"a","schema_version":"b"}', '{"x":NaN}', '[' * 2000 + ']' * 2000, ' ' * 1000001):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError): parse_domain_config_json(raw)
    def test_size_bounds(self):
        a=sample(); a.update({str(i):i for i in range(10000)})
        with self.assertRaises(ValueError): validate_domain_config(a)
        a=sample(); a['references']=['x']*101
        with self.assertRaises(ValueError): validate_domain_config(a)
        a=sample(); a['parameters'][0]['source']='x'*2001
        with self.assertRaises(ValueError): validate_domain_config(a)
