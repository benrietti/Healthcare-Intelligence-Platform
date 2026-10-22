import unittest
import tempfile
from pathlib import Path
import pandas as pd
from healthcare_capstone.ml.features import chronological_split, available_events, ADMISSION_FEATURES
from healthcare_capstone.ml.monitoring import population_stability_index, drift_report
from healthcare_capstone.operations import reconcile_beds
from healthcare_capstone.edi import submission_segment,remittance_segment,parse_segments
from healthcare_capstone.demo import quality_checks,fit_model

class PortfolioTests(unittest.TestCase):
    def test_features_exclude_future_outcomes_and_keep_row_identity(self):
        x=pd.DataFrame(dict(admission_ts=pd.date_range('2024-01-01',periods=10,tz='UTC')[::-1],facility_id=['a']*10,length_of_stay_hours=range(10),readmitted_30d=[0,1]*5,paid_amount=1000,discharge_disposition='home'),index=range(30,40))
        result=chronological_split(x,'readmitted_30d')
        self.assertEqual(list(result.X_train.columns),['facility_id'])
        self.assertEqual(list(result.X_test.index),[31,30])
    def test_late_documentation_and_missing_time_excluded(self):
        events=pd.DataFrame(dict(encounter_id=['e']*4,event_ts=['2024-01-01','2024-01-01','2024-01-03',None],ingested_at=['2024-01-01','2024-01-03','2024-01-03','2024-01-01']))
        cutoff=pd.DataFrame(dict(encounter_id=['e'],prediction_ts=['2024-01-02']))
        self.assertEqual(len(available_events(events,cutoff)),1)
    def test_psi_detects_shift_and_unseen_categories(self):
        self.assertAlmostEqual(population_stability_index(range(100),range(100)),0)
        self.assertGreater(population_stability_index(range(100),range(1000,1100)),.2)
        self.assertGreater(population_stability_index(['a']*100,['b']*100),.2)
        self.assertIsNone(population_stability_index([],[]))
        self.assertGreater(population_stability_index([1]*100,[10]*100),.2)
    def test_missing_cleaning_prevents_ready_bed(self):
        x=pd.DataFrame(dict(administrative_discharge_ts=['2024-01-01T10:00Z']*2,transport_departure_ts=['2024-01-01T10:20Z']*2,cleaning_complete_ts=['2024-01-01T11:00Z',None]))
        out=reconcile_beds(x)
        self.assertEqual(out.loc[0,'turnover_minutes'],60)
        self.assertTrue(pd.isna(out.loc[1,'bed_ready_ts']))
    def test_mixed_iso_precision_is_not_a_missing_event(self):
        events=pd.DataFrame(dict(encounter_id=['e']*2,event_ts=['2024-01-01T00:00:00Z','2024-01-01T00:00:00.123Z'],ingested_at=['2024-01-01T00:01:00Z']*2))
        cutoff=pd.DataFrame(dict(encounter_id=['e'],prediction_ts=['2024-01-02T00:00:00Z']))
        self.assertEqual(len(available_events(events,cutoff)),2)
    def test_synthetic_edi_roundtrip(self):
        claim=dict(claim_id='SYN-C-1',billed_amount=1250.25,paid_amount=0,claim_status='denied')
        out=parse_segments(submission_segment(claim)+remittance_segment(claim))
        self.assertEqual(out[0]['claim_id'],'SYN-C-1')
        self.assertEqual(out[1]['status_code'],'4')
        self.assertEqual(float(out[0]['billed_amount']),1250.25)
        with self.assertRaises(ValueError):parse_segments('CLP*id~')
    def test_training_labels_must_precede_cutoff(self):
        n=100
        x=pd.DataFrame(dict(encounter_id=range(n),prediction_ts=pd.date_range('2024-01-01',periods=n,tz='UTC'),label_ts=pd.date_range('2024-01-01',periods=n,tz='UTC')+pd.Timedelta(days=10),amount=range(n),target=[0,1]*50))
        with tempfile.TemporaryDirectory() as t:
            _,m=fit_model(x,['amount'],'target','prediction_ts','label_ts','test',Path(t))
        self.assertEqual(m['n_purged'],10)
        self.assertEqual(m['features'],['amount'])

if __name__=='__main__':unittest.main()
