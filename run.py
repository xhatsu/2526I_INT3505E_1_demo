# run.py
import os
from dotenv import load_dotenv # type: ignore
from api_endpoint import create_app

# Load .env file from the root directory
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("Warning: .env file not found.")

app = create_app()

if __name__ == '__main__':
    # Get host and port from environment or use defaults
    HOST = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    PORT = int(os.environ.get('FLASK_RUN_PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    
    app.run(host=HOST, port=PORT, debug=DEBUG)