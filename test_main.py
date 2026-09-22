import pytest
import os
from fastapi.testclient import TestClient

# Use isolated test database
os.environ["DB_PATH"] = "test_books.db"

import database
from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    if os.path.exists("test_books.db"):
        os.remove("test_books.db")
    database.init_db()
    yield
    if os.path.exists("test_books.db"):
        os.remove("test_books.db")

def test_read_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "BookLister" in response.text

def test_add_and_get_books():
    # Initially empty
    response = client.get("/books")
    assert response.status_code == 200
    assert "No books in your list yet." in response.text

    # Add a reading book
    response = client.post("/books", data={"title": "The Hobbit", "author": "J.R.R. Tolkien", "status": "reading"})
    assert response.status_code == 200
    assert response.headers.get("HX-Trigger") == "booksUpdated"

    # List reading books
    response = client.get("/books?status=reading")
    assert response.status_code == 200
    assert "The Hobbit" in response.text
    assert "J.R.R. Tolkien" in response.text
    assert "Currently Reading" in response.text

def test_add_and_get_books_with_dates():
    response = client.post(
        "/books",
        data={
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "status": "finished",
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
        },
    )
    assert response.status_code == 200

    response = client.get("/books?status=finished")
    assert response.status_code == 200
    assert "The Great Gatsby" in response.text
    assert "Started: 2023-01-01" in response.text
    assert "Ended: 2023-01-10" in response.text

    books = database.get_books(status="finished")
    assert books[0]["start_date"] == "2023-01-01"
    assert books[0]["end_date"] == "2023-01-10"

def test_db_migration():
    import sqlite3
    db_file = "test_migration.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'reading',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

    old_db_path = os.environ.get("DB_PATH")
    try:
        os.environ["DB_PATH"] = db_file
        database.init_db()
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(books)")
        cols = [r["name"] for r in cursor.fetchall()]
        conn.close()
        assert "start_date" in cols
        assert "end_date" in cols
    finally:
        if old_db_path:
            os.environ["DB_PATH"] = old_db_path
        if os.path.exists(db_file):
            os.remove(db_file)

def test_update_book_status():
    client.post("/books", data={"title": "1984", "author": "George Orwell", "status": "reading"})
    books = database.get_books()
    book_id = books[0]["id"]

    # Mark as finished
    response = client.post(f"/books/{book_id}/status?status=finished")
    assert response.status_code == 200

    books = database.get_books()
    assert books[0]["status"] == "finished"

    # Mark as unfinished
    response = client.patch(f"/books/{book_id}/status?status=unfinished")
    assert response.status_code == 200

    books = database.get_books()
    assert books[0]["status"] == "unfinished"

def test_search_read_books():
    client.post("/books", data={"title": "Dune", "author": "Frank Herbert", "status": "finished"})
    client.post("/books", data={"title": "Foundation", "author": "Isaac Asimov", "status": "reading"})

    # Search match
    response = client.get("/books/search?q=Dune")
    assert response.status_code == 200
    assert "Dune" in response.text
    assert "Foundation" not in response.text

    # Search non-match
    response = client.get("/books/search?q=NonExistent")
    assert response.status_code == 200
    assert "No finished books found matching" in response.text

def test_stats_endpoint():
    client.post("/books", data={"title": "Book 1", "author": "Author 1", "status": "finished"})
    client.post("/books", data={"title": "Book 2", "author": "Author 2", "status": "reading"})
    client.post("/books", data={"title": "Book 3", "author": "Author 3", "status": "unfinished"})

    response = client.get("/stats")
    assert response.status_code == 200
    assert "1" in response.text  # Finished: 1, Reading: 1, Unfinished: 1

def test_delete_book():
    client.post("/books", data={"title": "To Delete", "author": "Author", "status": "reading"})
    books = database.get_books()
    book_id = books[0]["id"]

    response = client.delete(f"/books/{book_id}")
    assert response.status_code == 200

    books = database.get_books()
    assert len(books) == 0
