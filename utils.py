from google.cloud import storage, bigquery
import os
import uuid
from datetime import datetime

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

def delete_photos_from_storage(conditions, query_params):
    """Helper function to delete photos from both storage and database"""
    photo_query = f"""
    SELECT photo_id, photo_url
    FROM `{client.project}.{DATASET_NAME}.photos`
    WHERE {" AND ".join(conditions)}
    """

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    query_job = client.query(photo_query, job_config=job_config)

    deleted_photos = []
    errors = []
    
    bucket = storage_client.bucket(BUCKET_NAME)
    for row in query_job:
        try:
            if row.photo_url:
                blob_name = f"entry_photos/{row.photo_url.split('/')[-1]}"
                blob = bucket.blob(blob_name)
                if blob.exists():
                    blob.delete()
                deleted_photos.append(row.photo_id)
        except Exception as e:
            errors.append(f"Error deleting photo {row.photo_id}: {str(e)}")

    return deleted_photos, errors

def insert_text_entry(entry_id, form_data):
    """Insert a new text entry into the database"""
    try:
        text_entry = {
            "entry_id": entry_id,
            "title": form_data.get("title"),
            "content": form_data.get("content"),
            "location": form_data.get("location"),
            "latitude": float(form_data.get("latitude")) if form_data.get("latitude") else 0.0,
            "longitude": float(form_data.get("longitude")) if form_data.get("longitude") else 0.0,
            "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        text_table_id = f"{client.project}.{DATASET_NAME}.text_entries"
        errors = client.insert_rows_json(text_table_id, [text_entry])
        return errors
    except Exception as e:
        print(f"Error in insert_text_entry: {str(e)}")
        raise

def handle_photos(entry_id, photos):
    """Handle photo uploads and return their URLs"""
    photo_urls = []
    
    try:
        for i, photo in enumerate(photos):
            if photo:
                photo_id = generate_unique_id("photos", "photo_id")
                photo_url = upload_image_to_gcs(photo, entry_id)
                
                if photo_url:
                    photo_data = {
                        "photo_id": photo_id,
                        "entry_id": entry_id,
                        "photo_url": photo_url,
                        "user_id": 1,
                        "uploaded_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    photos_table_id = f"{client.project}.{DATASET_NAME}.photos"
                    errors = client.insert_rows_json(photos_table_id, [photo_data])
                    
                    photo_urls.append(photo_url)
        return photo_urls
    except Exception as e:
        print(f"Error in handle_photos: {str(e)}")
        raise

def handle_expenses(entry_id, expenses):
    """Handle expenses and insert them into the database"""
    try:
        for i, expense in enumerate(expenses):
            if expense:
                category, amount = expense.split(":")
                expense_id = generate_unique_id("expenses", "expense_id")
                
                expense_data = {
                    "expense_id": expense_id,
                    "entry_id": entry_id,
                    "category": category,
                    "amount": float(amount),
                    "user_id": 1,
                    "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                expenses_table_id = f"{client.project}.{DATASET_NAME}.expenses"
                errors = client.insert_rows_json(expenses_table_id, [expense_data])
                print(f"Expense insert errors (if any): {errors}")
    except Exception as e:
        print(f"Error in handle_expenses: {str(e)}")
        raise