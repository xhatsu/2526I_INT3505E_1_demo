import os
import requests
import jwt
from dotenv import load_dotenv # type: ignore
from flask import Flask, request, jsonify

app = Flask(__name__)

load_dotenv()  # Load environment variables from a .env file if present

# Get the internal URL of your main application from an environment variable
# Example: 'http://my-app-service.default.svc.cluster.local:8080'
FORWARD_URL = os.environ.get('FORWARD_URL')
SECRET_KEY = os.environ.get('SECRET_KEY')

if not FORWARD_URL or not SECRET_KEY:
    raise RuntimeError("FORWARD_URL environment variable is not set.")

# --- JWT Validation Logic ---

def validate_jwt(auth_header):
    """
    Validates a JWT from the 'Authorization: Bearer <token>' header.
    Returns True if valid, False otherwise.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        raise jwt.InvalidTokenError("Missing or malformed Authorization header")
    token = auth_header.split(" ")[1]
    try:
        # Decode the token. This automatically checks the signature and expiration.
        jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return True
    except jwt.ExpiredSignatureError:
        # Token has expired
        raise
    except jwt.InvalidTokenError:
        # Any other error (e.g., invalid signature, malformed token)
        raise

# def is_token_valid(token):
#     """
#     Placeholder for your actual token validation logic.
#     - Decode a JWT
#     - Look up an API key in a database
#     - Call an external auth service
#     """
#     # For this example, we'll just check for a static secret token.
#     # In a real application, NEVER do this. Use a secure method.
#     return token == "Bearer my-super-secret-token"

# --- Gateway Routing ---

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def gateway(path):
    """
    Intercepts all requests, validates the JWT, and forwards if valid.
    """
    # Exclude auth routes from the JWT check
    if path in ['register', 'login']:
        # Forward registration and login requests directly without auth check
        pass
    else:
        # For all other routes, perform the JWT validation
        auth_header = request.headers.get('Authorization')
        try:
            if not validate_jwt(auth_header):
                return jsonify({"message": "Authentication failed or token is not accepted"}), 401
        except jwt.ExpiredSignatureError as e:
                return jsonify({"message": f"{str(e)}"}), 401
        except jwt.InvalidTokenError as e:
                return jsonify({"message": f"Token invalid: {str(e)}"}), 401

    # Construct the full internal URL
    full_url = f"{FORWARD_URL}/{path}"

    try:
        # Forward the request
        forward_headers = {key: value for (key, value) in request.headers if key != 'Host'}
        resp = requests.request(
            method=request.method,
            url=full_url,
            headers=forward_headers,
            data=request.get_data(),
            params=request.args,
            stream=True,
            timeout=30
        )
        # Return the response from the upstream service
        return (resp.content, resp.status_code, resp.headers.items())

    except requests.exceptions.RequestException as e:
        return jsonify({"message": "Error connecting to the upstream service", "error": str(e)}), 503


if __name__ == '__main__':
    # Use Gunicorn in production, not this.
    app.run(host='0.0.0.0', port=5000)