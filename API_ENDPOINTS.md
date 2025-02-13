# API Endpoints Documentation

## Authentication Endpoints

### Register User
- **Endpoint:** `/register`
- **Method:** POST
- **Description:** Register a new user
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "password123",
    "name": "User Name"
  }
  ```
- **Response:** Returns JWT token on successful registration

### Login
- **Endpoint:** `/login`
- **Method:** POST
- **Description:** Authenticate existing user
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response:** Returns JWT token on successful login

