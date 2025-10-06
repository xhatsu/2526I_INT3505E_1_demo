import sqlite3

# Connect to the database file
connection = sqlite3.connect('library.db')
cursor = connection.cursor()

# --- Drop existing tables to start fresh ---
print("Dropping existing tables...")
cursor.execute("DROP TABLE IF EXISTS borrow_records")
cursor.execute("DROP TABLE IF EXISTS books")
cursor.execute("DROP TABLE IF EXISTS users")

# --- Create the 'users' table ---
print("Creating 'users' table...")
cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
""")

# --- Create the 'books' table ---
print("Creating 'books' table...")
cursor.execute("""
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity >= 0)
);
""")

# --- Create the 'borrow_records' table ---
print("Creating 'borrow_records' table...")
cursor.execute("""
CREATE TABLE borrow_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    return_date TEXT,
    FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
""")

# --- Insert some sample data into 'users' ---
print("Inserting sample users...")
sample_users = [
    ('Alice',),
    ('Bob',),
    ('Charlie',)
]
cursor.executemany("INSERT INTO users (name) VALUES (?)", sample_users)


# --- Insert some sample data into 'books' ---
print("Inserting sample data...")
sample_books = [
    ('The Hobbit', 'J.R.R. Tolkien', 5),
    ('1984', 'George Orwell', 3),
    ('Dune', 'Frank Herbert', 0),
    ('The Hitchhiker\'s Guide to the Galaxy', 'Douglas Adams', 10)
]
cursor.executemany("INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)", sample_books)

# --- Insert some sample borrow records ---
print("Inserting sample borrow records...")
sample_records = [
    (1, 1, '2025-09-01T10:00:00', '2025-09-15T14:30:00'), # Alice borrowed The Hobbit
    (2, 2, '2025-09-05T11:20:00', None), # Bob borrowed 1984
    (1, 4, '2025-09-20T16:00:00', None), # Alice borrowed Hitchhiker's Guide
]
cursor.executemany("INSERT INTO borrow_records (user_id, book_id, borrow_date, return_date) VALUES (?, ?, ?, ?)", sample_records)


# Commit the changes and close the connection
connection.commit()
connection.close()

print("Database 'library.db' initialized successfully with sample data.")

