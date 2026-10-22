"""Cloud training entry point using the shared, purged admission-time pipeline."""
from healthcare_capstone.ml.cloud import train_cloud_model

def main():
    train_cloud_model("length_of_stay")

if __name__ == "__main__":main()
