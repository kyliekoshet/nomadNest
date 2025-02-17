from flask import Flask
from routes.auth_routes import auth_bp
from routes.entry_routes import entry_bp
from routes.user_routes import user_bp

app = Flask(__name__)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(entry_bp)
app.register_blueprint(user_bp)

@app.route('/')
def index():
    return "<h1>Hello World</h1>"

if __name__ == '__main__':
    app.run(debug=True)
