# Nomads Nest 

A property rental platform built with Flask and Google Cloud services.

## Quick Start

### Prerequisites
- Python 3.8 or higher
- Google Cloud account
- Service account key file

### Environment Setup
1. Clone the repository:
```bash
git clone <repository-url>
cd nomads-nest
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Configuration
1. Create a `.env` file in the root directory:
```text
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
JWT_SECRET_KEY=your-secret-key-here
GOOGLE_CLOUD_PROJECT=nomads-nest
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
STORAGE_BUCKET_NAME=nomads-nest-profile-pics
```

## Project Structure
```
nomads-nest/
├── .env                    # Environment variables
├── .gitignore             # Git ignore file
├── app.py                 # Main Flask application
├── generate_users.py      # Script to generate sample users
├── requirements.txt       # Project dependencies
├── README.md             # This file
└── TODO.txt              # Future improvements and tasks
```

## Authentication Endpoints
- `POST /register` - Create new user account
- `POST /login` - User login
- `GET /protected` - Example protected route

## Development
Run the development server:
```bash
flask run
```
Visit http://localhost:5000 to access the application.

## Testing
Generate sample users:
```bash
python generate_users.py
```

## Tech Stack
- Flask (Web Framework)
- Google Cloud BigQuery (Database)
- Google Cloud Storage (File Storage)
- Flask-JWT-Extended (Authentication)