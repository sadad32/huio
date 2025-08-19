import json
from flask import Flask, jsonify
from flask_cors import CORS

# --- Flask App Initialization ---
app = Flask(__name__)
# Enable CORS to allow requests from the frontend (running on a different origin)
CORS(app)

# --- Helper Function ---
def load_database():
    """Loads the mock database from database.json."""
    try:
        # Use utf-8 encoding to handle Arabic characters correctly
        with open('database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: database.json not found.")
        return None
    except json.JSONDecodeError:
        print("Error: Could not decode database.json.")
        return None

# --- API Endpoints ---

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """API endpoint to get the list of recommendations."""
    db = load_database()
    if db and 'recommendations' in db:
        return jsonify(db['recommendations'])
    return jsonify({"error": "Could not retrieve recommendations"}), 500

@app.route('/api/performance', methods=['GET'])
def get_performance():
    """API endpoint to get the performance history."""
    db = load_database()
    if db and 'performance_history' in db:
        return jsonify(db['performance_history'])
    return jsonify({"error": "Could not retrieve performance data"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    # To run this server:
    # 1. Make sure you have Flask and Flask-Cors installed (`pip install Flask Flask-Cors`).
    # 2. Run this script from your terminal: `python app.py`
    # The server will start on http://127.0.0.1:5000

    # The 'debug=True' option provides detailed error pages and reloads the server
    # automatically when you make changes to the code.
    # Note: Do not use debug mode in a production environment.
    app.run(debug=True)
