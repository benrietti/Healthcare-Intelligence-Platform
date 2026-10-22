import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
spec=importlib.util.spec_from_file_location('gate',Path(__file__).parents[1]/'scripts/quality_gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
class GateTests(unittest.TestCase):
 def test_missing_evidence_fails_closed(self):
  with tempfile.TemporaryDirectory() as t:self.assertTrue(gate.evaluate(Path(t),{}))
 def test_threshold_and_staleness_fail(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'reports').mkdir()
   for name in ['quality_checks','build_manifest']:(p/(name+'.json')).write_text('{"status":"passed"}')
   (p/'reports/rpt_data_quality_overview.csv').write_text('clinical_event_count,events_missing_timestamp,events_missing_department,events_arriving_over_24h_late\n10,8,0,0\n')
   policy=dict(freshness_hours=48,max_missing_timestamp_rate=.1,max_missing_department_rate=.1,max_late_arrival_rate=.1)
   failed=gate.evaluate(p,policy,datetime.now(timezone.utc)+timedelta(days=3))
   self.assertIn('stale build evidence',failed);self.assertIn('events_missing_timestamp exceeds threshold',failed)
