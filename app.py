from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
from google.cloud import bigquery
from google.cloud import storage
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Setup JWT
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

# Initialize BigQuery client
client = bigquery.Client(project=os.getenv('GOOGLE_CLOUD_PROJECT'))
DATASET_NAME = 'nomads-nest'
TABLE_NAME = 'users'

# Add this to your existing imports and setup
storage_client = storage.Client()
BUCKET_NAME = "nomads-nest-profile-pics"  # You'll need to create this bucket

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

@app.route('/')
def index():
    return "<h1>Hello World</h1>"

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

# Protected route example
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({"logged_in_as": current_user}), 200

@app.route('/users')
def show_users():
    return jsonify({"users": list(users.keys()), "passwords": list(users.values())})

if __name__ == '__main__':
    create_users_table()
    app.run(debug=True)
