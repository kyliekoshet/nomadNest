from flask import Blueprint, jsonify, request
from google.cloud import bigquery
from config import client, DATASET_NAME

user_bp = Blueprint('user', __name__)

def read_users():
    query = f"""
        SELECT user_id, email, full_name, profile_pic_url, created_at, password_hash
        FROM `{client.project}.{DATASET_NAME}.users`
    """
    query_job = client.query(query)
    results = list(query_job.result())
    return results

@user_bp.route('/api/users', methods=['GET'])
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

@user_bp.route('/api/users/search', methods=['GET'])
def search_users():
    try:
        # Get search parameters from query string
        user_id = request.args.get('id')
        email = request.args.get('email') 
        name = request.args.get('name')

        # Build query conditions
        conditions = []
        query_params = []

        if user_id:
            conditions.append("user_id = @user_id")
            query_params.append(bigquery.ScalarQueryParameter("user_id", "STRING", user_id))
            
        if email:
            conditions.append("email = @email")
            query_params.append(bigquery.ScalarQueryParameter("email", "STRING", email))
            
        if name:
            conditions.append("LOWER(full_name) LIKE CONCAT('%', LOWER(@name), '%')")
            query_params.append(bigquery.ScalarQueryParameter("name", "STRING", name))

        # If no search params provided, return error
        if not conditions:
            return jsonify({"error": "Please provide at least one search parameter (id, email, or name)"}), 400

        # Construct query
        query = f"""
            SELECT user_id, email, full_name, profile_pic_url, created_at
            FROM `{client.project}.{DATASET_NAME}.users`
            WHERE {" OR ".join(conditions)}
        """

        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
        query_job = client.query(query, job_config=job_config)
        results = list(query_job.result())

        # Format results
        users = []
        for user in results:
            users.append({
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "profile_pic_url": user.profile_pic_url,
                "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None
            })

        return jsonify({
            "users": users,
            "count": len(users)
        }), 200

    except Exception as e:
        print(f"Error searching users: {e}")
        return jsonify({"error": str(e)}), 500

