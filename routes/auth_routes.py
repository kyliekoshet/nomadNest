from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from google.cloud import bigquery
from datetime import datetime
from config import client, DATASET_NAME, TABLE_NAME
from utils import upload_image_to_gcs, get_user_by_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
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
    if get_user_by_email(email):
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

@auth_bp.route('/login', methods=['GET', 'POST'])
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

    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid password"}), 401
    
    return jsonify({"message": "Login successful"}), 200
    
    
    