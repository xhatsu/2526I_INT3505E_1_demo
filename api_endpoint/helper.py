from flask import jsonify, make_response, url_for, request
from .logger import api_logger
import functools

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

# --- HATEOAS Link Generation Helpers ---

def add_user_links(user):
    """Injects HATEOAS links into a user resource."""
    user['_links'] = {
        'self': {
            'href': url_for('users.get_user_by_id', user_id=user['id'], _external=True),
            'method': 'GET'
        },
        'history': {
            'href': url_for('users.get_user_borrow_history', user_id=user['id'], _external=True),
            'method': 'GET'
        },
        'collection': {
             'href': url_for('users.get_all_users', _external=True),
             'method': 'GET'
        }
    }
    return user

def add_book_links(book):
    """Injects HATEOAS links into a book resource."""
    book['_links'] = {
        'self': {
            'href': url_for('books.get_book_by_id', book_id=book['id'], _external=True),
            'method': 'GET'
        },
        'collection': {
             'href': url_for('books.get_all_books', _external=True),
             'method': 'GET'
        }
    }
    # Conditionally add the 'borrow' action link if the book is in stock
    if book.get('quantity', 0) > 0:
        book['_links']['borrow'] = {
            'href': url_for('library.borrow_book', _external=True),
            'method': 'POST',
            'schema': {'user_id': 'integer', 'book_id': 'integer'}
        }
    return book

def add_borrow_record_links(record):
    """Injects HATEOAS links into a borrow record resource."""
    record['_links'] = {
        'user': {
            'href': url_for('users.get_user_by_id', user_id=record['user_id'], _external=True),
            'method': 'GET'
        },
        'book': {
            'href': url_for('books.get_book_by_id', book_id=record['book']['id'], _external=True),
            'method': 'GET'
        }
    }
    # If the book hasn't been returned, provide the link to the 'return' action
    if record.get('return_date') is None:
        record['_links']['return'] = {
            'href': url_for('library.return_book', _external=True),
            'method': 'POST',
            'schema': {'user_id': 'integer', 'book_id': 'integer'}
        }
    return record


# --- Logging Decorator ---
def log_request(f):
    """Decorator to log request and response details."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        api_logger.info(
            f"[{request.method}] {request.path} - IP: {request.remote_addr} - Args: {request.args}"
        )
        try:
            result = f(*args, **kwargs)
            if isinstance(result, tuple):
                status_code = result[1]
            else:
                status_code = 200
            api_logger.info(f"Response Status: {status_code}")
            return result
        except Exception as e:
            api_logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            raise
    return decorated_function