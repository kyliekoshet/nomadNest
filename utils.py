from google.cloud import storage, bigquery
import os
import uuid

storage_client = storage.Client()
client = bigquery.Client(project='nomads-nest') 
DATASET_NAME = 'NomadNest'
BUCKET_NAME = "nomads-nest-profile-pics"
TABLE_NAME = 'users'

def upload_image_to_gcs(file, user_id):
    """Upload image to Google Cloud Storage and return public URL"""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Create a unique filename using user_id
        extension = os.path.splitext(file.filename)[1]
        blob_name = f"profile_pics/{user_id}{extension}"
        
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file)
        
        # Make the file publicly readable
        blob.make_public()
        
        return blob.public_url
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None

def check_id_exists(table, column, value):
    """Check if a given ID already exists in a specified table and column."""
    query = f"""
        SELECT COUNT(*) AS count
        FROM `{client.project}.{DATASET_NAME}.{table}`
        WHERE {column} = @value
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("value", "STRING", value)]
    )
    query_job = client.query(query, job_config=job_config)
    result = list(query_job.result())
    return result[0].count > 0

def generate_unique_id(table, column):
    """Generate a unique ID for a given table and column."""
    while True:
        unique_id = str(uuid.uuid4())
        try:
            exists = check_id_exists(table, column, unique_id)
            if not exists:
                return unique_id
        except Exception as e:
            print(f"Error in check_id_exists: {str(e)}")
            raise

def get_user_by_email(email):
    """Get user details from database by email."""
    query = f"""
        SELECT user_id, email, password_hash
        FROM `{client.project}.{DATASET_NAME}.{TABLE_NAME}`
        WHERE email = @email
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("email", "STRING", email)
        ]
    )
    query_job = client.query(query, job_config=job_config)
    results = list(query_job.result())
    return results[0] if results else None