from flask import jsonify, make_response

# --- Helper Function for JSON Responses ---
def create_response(data, status_code, headers=None):
    """Creates a Flask JSON response."""
    response = jsonify(data)
    response.status_code = status_code
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    return response

# --- Helper to convert Oracle rows to Dictionaries ---
def rows_to_dicts(cursor):
    """Converts cursor results to a list of dictionaries."""
    # Column names need to be lowercase for consistent JSON keys
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor]
