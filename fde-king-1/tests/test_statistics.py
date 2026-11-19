import unittest
import numpy as np
import pandas as pd
from fdebench.statistics import estimate,paired_ratio,launch_interval

class StatisticalChecks(unittest.TestCase):
    def test_launches_not_pooled_observations(self):
        # A long launch must not dominate a short launch's weight.
        df=pd.DataFrame({'session':[1]*100+[2,3], 'value':[1.]*100+[10.,20.]})
        result=estimate(df,'value',np.random.default_rng(1),1000)
        self.assertEqual(result['median'],10.)
        self.assertEqual(result['sessions'],3)
        self.assertEqual(result['ci_scope'],'between_launch_order_statistics')
    def test_paired_launch_ratios(self):
        df=pd.DataFrame({'session':[1,1,2,2,3,3,4,4,5,5,6,6], 'group':['g']*12,
                         'method':['a','b']*6, 'value':[2.,1.,20.,10.,200.,100.,2.,1.,20.,10.,200.,100.]})
        r=paired_ratio(df,['group'],'value','method','a','b',np.random.default_rng(2),1000).iloc[0]
        self.assertEqual(r.ratio,2.)
        self.assertEqual(r.ci_low,2.)
        self.assertEqual(r.ci_high,2.)
    def test_single_observation_has_no_interval(self):
        r=estimate(pd.DataFrame({'session':[1], 'value':[12.]}),'value',np.random.default_rng(3),1000)
        self.assertEqual(r['median'],12.)
        self.assertTrue(np.isnan(r['ci_low']))
    def test_known_constant_series(self):
        r=estimate(pd.DataFrame({'session':[1]*20, 'value':[5.]*20}),'value',np.random.default_rng(4),1000)
        self.assertEqual((r['median'],r['ci_low'],r['ci_high']),(5.,5.,5.))

    def test_order_statistic_coverage(self):
        lo,hi,coverage=launch_interval([1,2,3,4,5,6])
        self.assertEqual((lo,hi),(1.,6.))
        self.assertEqual(coverage,.96875)
        self.assertTrue(np.isnan(launch_interval([1,2,3,4,5])[0]))
        lo,hi,coverage=launch_interval(range(1,11))
        self.assertEqual((lo,hi),(2.,9.))
        self.assertGreaterEqual(coverage,.95)
