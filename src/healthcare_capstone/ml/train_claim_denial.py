"""Train synthetic claim denial ranking with submission-time features only."""
from healthcare_capstone.ml.cloud import train_cloud_model
if __name__=='__main__':train_cloud_model('claim_denial')
