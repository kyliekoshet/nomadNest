from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from google.cloud import bigquery
from google.cloud import storage
import os
from dotenv import load_dotenv
import uuid

load_dotenv()


app = Flask(__name__)

# Initialize BigQuery client
client = bigquery.Client(project='nomads-nest') 
DATASET_NAME = 'NomadNest'
TABLE_NAME = 'users'

storage_client = storage.Client()
BUCKET_NAME = "nomads-nest-profile-pics"  # You'll need to create this bucket

@app.route('/')
def index():
    return "<h1>Hello World</h1>"

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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return '''
            <form method="POST" enctype="multipart/form-data">
                <h2>Register</h2>
                <div>
                    <label>Email:</label>
                    <input type="email" name="email" required>
                </div>
                <div>
                    <label>Password:</label>
                    <input type="password" name="password" required>
                </div>
                <div>
                    <label>Full Name:</label>
                    <input type="text" name="full_name" required>
                </div>
                <div>
                    <label>Profile Picture:</label>
                    <input type="file" name="profile_pic" accept="image/*">
                </div>
                <button type="submit">Register</button>
            </form>
        '''

    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    profile_pic = request.files.get('profile_pic')

    user_id = str(abs(hash(email)))[:10]
    profile_pic_url = None

    if profile_pic:
        profile_pic_url = upload_image_to_gcs(profile_pic, user_id)

    if not email or not password or not full_name:
        return jsonify({"error": "Missing required fields"}), 400

    # Check if user exists
    query = f"""
        SELECT email FROM `{client.project}.{DATASET_NAME}.{TABLE_NAME}`
        WHERE email = @email
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("email", "STRING", email)
        ]
    )
    query_job = client.query(query, job_config=job_config)
    results = list(query_job.result())
    
    if results:
        return jsonify({"error": "User already exists"}), 400

    # Insert new user
    user_data = {
        "user_id": user_id,
        "email": email,
        "password_hash": generate_password_hash(password),
        "full_name": full_name,
        "profile_pic_url": profile_pic_url,
        "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }

    table_id = f"{client.project}.{DATASET_NAME}.{TABLE_NAME}"
    errors = client.insert_rows_json(table_id, [user_data])
    
    if errors:
        return jsonify({"error": f"Error inserting user: {errors}"}), 500

    return jsonify({"message": "User created successfully"}), 201

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return '''
            <form method="POST">
                <h2>Login</h2>
                <div>
                    <label>Email:</label>
                    <input type="email" name="email" required>
                </div>
                <div>
                    <label>Password:</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit">Login</button>
            </form>
        '''

    email = request.form.get('email')
    password = request.form.get('password')

    # Query user from BigQuery
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

    if not results:
        return jsonify({"error": "User not found"}), 401

    user = results[0]
    if not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Wrong password"}), 401

    access_token = create_access_token(identity=user.user_id)
    return jsonify({"access_token": access_token}), 200


@app.route('/entry-form')
def entry_form():
    return '''
    <form action="/api/entries" method="post" enctype="multipart/form-data">
        <input type="text" name="title" placeholder="Title"><br>
        <textarea name="content" placeholder="Content"></textarea><br>
        <input type="text" name="location" placeholder="Location"><br>
        <input type="text" name="latitude" placeholder="Latitude"><br>
        <input type="text" name="longitude" placeholder="Longitude"><br>
        <input type="file" name="photos" multiple><br>
        <input type="text" name="expenses" placeholder="category:amount"><br>
        <input type="submit" value="Create Entry">
    </form>
    '''

@app.route('/api/entries', methods=['POST'])
def create_entry():
    try:
        # Generate unique entry_id
        while True:
            entry_id = str(uuid.uuid4())
            if not check_id_exists("text_entries", "entry_id", entry_id):
                break

        text_entry = {
            "entry_id": entry_id,
            "title": request.form.get("title"),
            "content": request.form.get("content"),
            "location": request.form.get("location"),
            "latitude": float(request.form.get("latitude")),
            "longitude": float(request.form.get("longitude")),
            "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        text_table_id = f"{client.project}.{DATASET_NAME}.text_entries"
        errors = client.insert_rows_json(text_table_id, [text_entry])
        if errors:
            return jsonify({"error": f"Error inserting text entry: {errors}"}), 500

        # Handle photos
        photos = request.files.getlist("photos")
        photo_urls = []
        for photo in photos:
            if photo:
                while True:
                    photo_id = str(uuid.uuid4())
                    if not check_id_exists("photos", "photo_id", photo_id):
                        break
                photo_url = upload_image_to_gcs(photo, entry_id)
                if photo_url:
                    photo_data = {
                        "photo_id": photo_id,
                        "entry_id": entry_id,
                        "photo_url": photo_url,
                        "uploaded_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    photos_table_id = f"{client.project}.{DATASET_NAME}.photos"
                    client.insert_rows_json(photos_table_id, [photo_data])
                    photo_urls.append(photo_url)

        # Handle expenses
        expenses = request.form.getlist("expenses")
        for expense in expenses:
            if expense:
                category, amount = expense.split(":")
                while True:
                    expense_id = str(uuid.uuid4())
                    if not check_id_exists("expenses", "expense_id", expense_id):
                        break
                expense_data = {
                    "expense_id": expense_id,
                    "entry_id": entry_id,
                    "category": category,
                    "amount": float(amount),
                    "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                }
                expenses_table_id = f"{client.project}.{DATASET_NAME}.expenses"
                client.insert_rows_json(expenses_table_id, [expense_data])

        return jsonify({
            "message": "Entry created successfully",
            "entry_id": entry_id,
            "photo_urls": photo_urls
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/entries', methods=['GET'])
def get_entries():
    try:
        query = f"""
        SELECT 
            t.entry_id,
            t.user_id,
            t.title,
            t.content,
            t.location,
            t.latitude,
            t.longitude,
            t.created_at,
            ARRAY_AGG(p.photo_url IGNORE NULLS) as photo_urls,
            ARRAY_AGG(e.category IGNORE NULLS) as expense_categories,
            ARRAY_AGG(e.amount IGNORE NULLS) as expense_amounts,
            ARRAY_AGG(e.currency IGNORE NULLS) as expense_currencies,
            u.full_name,
            u.profile_pic_url
        FROM `{client.project}.{DATASET_NAME}.text_entries` t
        LEFT JOIN `{client.project}.{DATASET_NAME}.photos` p 
            ON t.entry_id = p.entry_id
        LEFT JOIN `{client.project}.{DATASET_NAME}.expenses` e 
            ON t.entry_id = e.entry_id
        LEFT JOIN `{client.project}.{DATASET_NAME}.users` u 
            ON CAST(t.user_id AS STRING) = u.user_id
        GROUP BY 
            t.entry_id,
            t.user_id,
            t.title,
            t.content,
            t.location,
            t.latitude,
            t.longitude,
            t.created_at,
            u.full_name,
            u.profile_pic_url
        ORDER BY t.created_at DESC
        """

        query_job = client.query(query)
        entries = []

        for row in query_job:
            expenses = []
            for i in range(len(row.expense_categories)):
                if row.expense_categories[i]:
                    expenses.append({
                        "category": row.expense_categories[i],
                        "amount": row.expense_amounts[i],
                        "currency": row.expense_currencies[i]
                    })

            entry = {
                "entry_id": row.entry_id,
                "user_id": row.user_id,
                "title": row.title,
                "content": row.content,
                "location": row.location,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "created_at": row.created_at.strftime('%Y-%m-%d %H:%M:%S') if row.created_at else None,
                "author": {
                    "name": row.full_name,
                    "profile_pic": row.profile_pic_url
                } if row.full_name else None,
                "photos": [url for url in row.photo_urls if url is not None],
                "expenses": expenses
            }
            entries.append(entry)

        return jsonify({
            "entries": entries,
            "count": len(entries)
        }), 200

    except Exception as e:
        print("Error details:", e) 
        return jsonify({"error": str(e)}), 500
    
def read_users():
    query = f"""
        SELECT user_id, email, full_name, profile_pic_url, created_at, password_hash
        FROM `{client.project}.{DATASET_NAME}.users`
    """
    query_job = client.query(query)
    results = list(query_job.result())
    return results

@app.route('/api/users', methods=['GET'])  # /api/ for API endpoints
def get_users():
    try:
        users = read_users()
        user_list = []
        for user in users:
            user_data = {
                "user_id": user.user_id,
                "email": user.email,
                "password_hash": user.password_hash,
                "full_name": user.full_name,
                "profile_pic_url": user.profile_pic_url,
                "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None
            }
            user_list.append(user_data)
        return jsonify({"users": user_list}), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
