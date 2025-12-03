import os
import requests
import jwt
from dotenv import load_dotenv # type: ignore
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)
load_dotenv()  # Load environment variables from a .env file if present

# Get the internal URL of your main application from an environment variable
# IMPORTANT: This should be the *base* URL, e.g., 'http://my-app-service:5000'
# It should NOT include '/api/v1'
FORWARD_URL = os.environ.get('FORWARD_URL')
SECRET_KEY = os.environ.get('SECRET_KEY')

if not FORWARD_URL or not SECRET_KEY:
    raise RuntimeError("FORWARD_URL and/or SECRET_KEY environment variables are not set.")

# --- Public Routes ---
# Define the exact paths that should bypass JWT validation.
# The 'path' variable from Flask will not include a leading slash.
PUBLIC_PATHS = [
    'metrics',            # Prometheus metrics endpoint
    'health',               # Your main app's health check
    'api/v1/register',      # The v1 register route
    'api/v1/login'          # The v1 login route
]

# --- JWT Validation Logic ---

def validate_jwt(auth_header):
    """
    Validates a JWT from the 'Authorization: Bearer <token>' header.
    Returns True if valid, raises an error otherwise.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        raise jwt.InvalidTokenError("Missing or malformed Authorization header")
    
    token = auth_header.split(" ")[1]
    
    # Decode the token. This automatically checks the signature and expiration.
    # An error will be raised if invalid.
    jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    return True

# --- Gateway Routing ---

@app.route('/')
def index():
    """A simple route for the gateway itself."""
    return jsonify({"message": "API Gateway is running."}), 200

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def gateway(path):
    """
    Intercepts all requests, validates the JWT, and forwards if valid.
    """
    
    # Check if the requested path is one of the public, auth-exempt routes
    if path in PUBLIC_PATHS:
        # Forward directly without auth check
        pass
    else:
        # For all other routes, perform the JWT validation
        auth_header = request.headers.get('Authorization')
        try:
            validate_jwt(auth_header)
        except jwt.ExpiredSignatureError as e:
            return jsonify({"message": f"Token expired: {str(e)}"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"message": f"Token invalid: {str(e)}"}), 401

    # Construct the full internal URL
    full_url = f"{FORWARD_URL}/{path}"

    try:
        # Forward the request, using stream=True to handle large/chunked responses
        forward_headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}
        
        resp = requests.request(
            method=request.method,
            url=full_url,
            headers=forward_headers,
            data=request.get_data(),
            params=request.args,
            stream=True,  # Use streaming to avoid loading all data into memory
            timeout=30
        )

        # --- Streamed Response ---
        # This is a more robust way to forward the response.
        # It streams the content from the upstream service back to the client.
        
        # Exclude headers that are set by the proxy/WSGI server
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [
            (key, value) for (key, value) in resp.raw.headers.items()
            if key.lower() not in excluded_headers
        ]

        # Return a new streaming Response
        return Response(stream_with_context(resp.iter_content(chunk_size=1024)), resp.status_code, headers)

    except requests.exceptions.RequestException as e:
        return jsonify({"message": "Error connecting to the upstream service", "error": str(e)}), 503


if __name__ == '__main__':
    # Use Gunicorn in production, not this.
    app.run(host='0.0.0.0', port=5000)
