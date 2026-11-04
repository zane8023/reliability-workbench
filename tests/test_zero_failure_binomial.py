import json
import math
import unittest
from decimal import Decimal,localcontext
from scipy.stats import beta
from app.services.zero_failure_binomial import zero_failure_upper

def call(n,c):return zero_failure_upper(n,c,event_definition="Synthetic event",observation_window="Synthetic window")

class ZeroBinomialTests(unittest.TestCase):
    def test_decimal_reference_and_beta(self):
        with localcontext() as ctx:
            ctx.prec=80
            for n,c in ((1,0.95),(10,0.95),(100,0.95),(10_000_000,0.95),(10_000_000,1e-12)):
                exact=1-((1-Decimal.from_float(c)).ln()/Decimal(n)).exp()
                p=call(n,c)["failure_probability_upper"]
                self.assertTrue(math.isclose(p,float(exact),rel_tol=2e-14,abs_tol=0))
                if c>0.01:self.assertTrue(math.isclose(p,float(beta.ppf(c,1,n)),rel_tol=2e-12))
    def test_n_and_confidence_monotonic(self):
        self.assertGreater(call(10,.95)["failure_probability_upper"],call(100,.95)["failure_probability_upper"])
        self.assertGreater(call(100,.99)["failure_probability_upper"],call(100,.95)["failure_probability_upper"])
    def test_near_limits_and_underflow_rejected(self):
        p=call(1,math.nextafter(1.0,0.0))["failure_probability_upper"];self.assertTrue(0<p<=1)
        with self.assertRaisesRegex(ValueError,"not representable"):call(10_000_000,math.ulp(0.0))
        with self.assertRaisesRegex(ValueError,"positive normal"):call(2,3*math.ulp(0.0))
    def test_invalid_and_boolean(self):
        for n in (0,-1,1.0,True,10_000_001):
            with self.assertRaises(ValueError):call(n,.95)
        for c in (0,1,-.1,float("nan"),float("inf"),True,"0.95"):
            with self.assertRaises(ValueError):call(10,c)
        for event,window in (("", "w"),("\u200b","w"),("e"," "),("e","x"*501),("x\ud800","w")):
            with self.assertRaises(ValueError):zero_failure_upper(10,.95,event_definition=event,observation_window=window)
    def test_repeatability_and_json(self):
        x=call(10,.95);self.assertEqual(x,call(10,.95));json.dumps(x,allow_nan=False)
        self.assertEqual(x["failure_count"],0);self.assertEqual(x["method"],"exact_one_sided_binomial")
