from flask import Blueprint, jsonify, request
from config import client, DATASET_NAME
from utils import check_id_exists, upload_image_to_gcs, generate_unique_id
import uuid
from datetime import datetime
from google.cloud import bigquery

entry_bp = Blueprint('entry', __name__)

def insert_text_entry(entry_id, form_data):
    
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
    """Handle photo uploads and return their URLs."""
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
    """Handle expenses and insert them into the database."""
    
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

@entry_bp.route('/entry-form')
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

@entry_bp.route('/api/entries', methods=['POST'])
def create_entry():
    
    try:
        # Generate entry ID
        entry_id = generate_unique_id("text_entries", "entry_id")
        
        # Insert text entry
        errors = insert_text_entry(entry_id, request.form)
        if errors:
            return jsonify({"error": f"Error inserting text entry: {errors}"}), 500

        # Handle photos
        photos = request.files.getlist("photos")
        photo_urls = handle_photos(entry_id, photos)

        # Handle expenses
        expenses = request.form.getlist("expenses")
        handle_expenses(entry_id, expenses)

        return jsonify({
            "message": "Entry created successfully",
            "entry_id": entry_id,
            "photo_urls": photo_urls,
            "expenses": expenses
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@entry_bp.route('/api/entries', methods=['GET'])
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

@entry_bp.route('/api/entries/search', methods=['GET'])
def search_entries():
    try:
        # Get search parameters from query string
        user_id = request.args.get('user_id')
        entry_id = request.args.get('entry_id')
        location = request.args.get('location')
        title = request.args.get('title')
        latitude = request.args.get('latitude')
        longitude = request.args.get('longitude')

        # Build query conditions
        conditions = []
        query_params = []

        if user_id:
            conditions.append("CAST(t.user_id AS STRING) = @user_id")
            query_params.append(bigquery.ScalarQueryParameter("user_id", "STRING", user_id))
            
        if entry_id:
            conditions.append("t.entry_id = @entry_id")
            query_params.append(bigquery.ScalarQueryParameter("entry_id", "INTEGER", int(entry_id)))
            
        if location:
            conditions.append("LOWER(t.location) LIKE CONCAT('%', LOWER(@location), '%')")
            query_params.append(bigquery.ScalarQueryParameter("location", "STRING", location))
            
        if title:
            conditions.append("LOWER(t.title) LIKE CONCAT('%', LOWER(@title), '%')")
            query_params.append(bigquery.ScalarQueryParameter("title", "STRING", title))
            
        if latitude:
            conditions.append("t.latitude = @latitude")
            query_params.append(bigquery.ScalarQueryParameter("latitude", "FLOAT64", float(latitude)))
            
        if longitude:
            conditions.append("t.longitude = @longitude")
            query_params.append(bigquery.ScalarQueryParameter("longitude", "FLOAT64", float(longitude)))

        # If no search params provided, return error
        if not conditions:
            return jsonify({
                "error": "Please provide at least one search parameter (user_id, entry_id, location, title, latitude, or longitude)"
            }), 400

        # Construct query
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
        WHERE {" AND ".join(conditions)}
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

        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
        query_job = client.query(query, job_config=job_config)
        entries = []

        for row in query_job:
            expenses = []
            for i in range(len(row.expense_categories or [])):
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
        print(f"Error searching entries: {e}")
        return jsonify({"error": str(e)}), 500