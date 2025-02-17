
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration settings
PROJECT_ID = 'nomads-nest'
DATASET_NAME = 'NomadNest'
TABLE_NAME = 'users'
BUCKET_NAME = "nomads-nest-profile-pics"

# Initialize clients
from google.cloud import bigquery, storage

client = bigquery.Client(project=PROJECT_ID)
storage_client = storage.Client()