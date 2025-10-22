import oracledb
import hashlib
import json
from flask import Blueprint, request, Response, url_for
from math import ceil
from .db import get_db
from .helper import * # Assumes helper.py is now in the same directory

bp = Blueprint('books_v2', __name__)

@bp.route('', methods=['GET'])
def get_all_books():
    """
    Fetches a paginated list of all books from the library.
    
    Accepts query parameters for filtering:
    - title: Filter by book title (case-insensitive, partial match)
    - author: Filter by author name (case-insensitive, partial match)
    - page: The page number (default 1)
    - limit: The number of items per page (default 10)
    """
    try:
        # --- Pagination ---
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        if page < 1 or limit < 1:
            raise ValueError
    except ValueError:
        return create_response({"error": "Invalid 'page' or 'limit'. Must be positive integers."}, 400)

    offset = (page - 1) * limit

    # --- Search / Filtering ---
    title_search = request.args.get('title')
    author_search = request.args.get('author')
    
    where_clauses = []
    bind_params = {} # Parameters for the SQL query

    # Use UPPER() for case-insensitive matching
    if title_search:
        where_clauses.append("UPPER(title) LIKE :title")
        bind_params['title'] = f"%{title_search.upper()}%"
    
    if author_search:
        where_clauses.append("UPPER(author) LIKE :author")
        bind_params['author'] = f"%{author_search.upper()}%"

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses) 

    db = get_db()
    try:
        with db.cursor() as cursor:
            # --- Get Total Count (with filtering) ---
            # The WHERE clause is applied to the count query
            count_query = f"SELECT COUNT(*) FROM books {where_sql}"
            cursor.execute(count_query, bind_params)
            
            total_items = cursor.fetchone()[0]
            if total_items == 0:
                return create_response({'data': [], 'total_items': 0, 'current_page': page, 'total_pages': 0}, 200)

            total_pages = ceil(total_items / limit)

            # --- Get Paginated Data (with filtering) ---
            # Add pagination parameters to the bind list
            data_params = bind_params.copy()
            data_params['offset'] = offset
            data_params['limit'] = limit

            # The WHERE clause is also applied to the main data query
            data_query = f"""
                SELECT * FROM books 
                {where_sql}
                ORDER BY id 
                OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
            """
            cursor.execute(data_query, data_params)
            
            books = rows_to_dicts(cursor)
            books = [add_book_links(book) for book in books]

            # --- Build Response ---
            response_data = {
                'total_items': total_items,
                'total_pages': total_pages,
                'current_page': page,
                'data': books
            }
            
            # --- Pagination Links (with search params) ---
            # Must pass the search params to url_for so they are preserved
            # on the next/prev page links.
            if page < total_pages:
                response_data['next_page_url'] = url_for('books_v2.get_all_books', 
                    page=page + 1, limit=limit, 
                    title=title_search, author=author_search, 
                    _external=True)
            if page > 1:
                response_data['prev_page_url'] = url_for('books_v2.get_all_books', 
                    page=page - 1, limit=limit, 
                    title=title_search, author=author_search, 
                    _external=True)

            header = {'Cache-Control': 'public, max-age=300'}
            return create_response(response_data, 200, header)
            
    except oracledb.Error as e:
        return create_response({"error": f"Database error: {e}"}, 500)


@bp.route('/<int:book_id>', methods=['GET'])
def get_book_by_id(book_id):
    """Fetches a single book by its ID."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM books WHERE id = :1', (book_id,))
        book_list = rows_to_dicts(cursor)
    if not book_list:
        return create_response({"error": "Book not found"}, 404)
    
    book = add_book_links(book_list[0])

    book_json_str = json.dumps(book, sort_keys=True).encode('utf-8')
    etag = hashlib.sha1(book_json_str).hexdigest()

    if request.headers.get('If-None-Match') == etag:
        return Response(status=304)

    headers = {'ETag': etag}
    return create_response(book, 200, headers)


@bp.route('', methods=['POST'])
def add_book():
    """Adds a new book to the library."""
    data = request.get_json()
    if not data or not all(k in data for k in ('title', 'author', 'quantity')):
        return create_response({"error": "Missing required fields: title, author, quantity"}, 400)

    try:
        title = data['title']
        author = data['author']
        quantity = int(data['quantity'])
    except (ValueError, TypeError):
        return create_response({"error": "Invalid data types for fields"}, 400)

    db = get_db()
    try:
        with db.cursor() as cursor:
            new_id_var = cursor.var(oracledb.DB_TYPE_NUMBER)
            sql = 'INSERT INTO books (title, author, quantity) VALUES (:1, :2, :3) RETURNING id INTO :4'
            cursor.execute(sql, (title, author, quantity, new_id_var))
            new_book_id = int(new_id_var.getvalue()[0])
            db.commit()

        new_book = {"id": new_book_id, "title": title, "author": author, "quantity": quantity}
        return create_response(new_book, 201)
    except oracledb.Error as e:
        db.rollback()
        return create_response({"error": f"Database error: {e}"}, 500)


@bp.route('/<int:book_id>', methods=['PUT'])
def update_book(book_id):
    """Updates an existing book's details."""
    db = get_db()
    book_to_update = db.cursor()
    book_to_update.execute('SELECT * FROM books WHERE id = :1', (book_id,))
    existing_book_data = rows_to_dicts(book_to_update)
    book_to_update.close()

    if not existing_book_data:
        return create_response({"error": "Book not found"}, 404)

    data = request.get_json()
    if not data:
        return create_response({"error": "Request body cannot be empty"}, 400)

    title = data.get('title', existing_book_data[0]['title'])
    author = data.get('author', existing_book_data[0]['author'])
    quantity = data.get('quantity', existing_book_data[0]['quantity'])

    with db.cursor() as cursor:
        cursor.execute('UPDATE books SET title = :1, author = :2, quantity = :3 WHERE id = :4',
                       (title, author, quantity, book_id))
    db.commit()

    with db.cursor() as cursor:
        cursor.execute('SELECT * FROM books WHERE id = :1', (book_id,))
        updated_book = rows_to_dicts(cursor)[0]

    return create_response(updated_book, 200)


@bp.route('/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Deletes a book from the library."""
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('DELETE FROM books WHERE id = :1', (book_id,))
        if cursor.rowcount == 0:
            return create_response({"error": "Book not found"}, 404)
    db.commit()
    return create_response({"message": f"Book with id {book_id} has been deleted."}, 200)
