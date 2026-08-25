import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("DB_PATH", "books.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'reading',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_book(title: str, author: str, status: str = "reading") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO books (title, author, status) VALUES (?, ?, ?)",
        (title.strip(), author.strip(), status)
    )
    conn.commit()
    book_id = cursor.lastrowid
    conn.close()
    return book_id

def get_books(status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM books WHERE status = ? ORDER BY id DESC", (status,))
    else:
        cursor.execute("SELECT * FROM books ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_book_status(book_id: int, status: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE books SET status = ? WHERE id = ?", (status, book_id))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

def delete_book(book_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    return rows_affected > 0

def search_read_books(query: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    search_term = f"%{query.strip()}%"
    cursor.execute(
        "SELECT * FROM books WHERE status = 'finished' AND (title LIKE ? OR author LIKE ?) ORDER BY id DESC",
        (search_term, search_term)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_stats() -> Dict[str, int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'finished'")
    finished_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'reading'")
    reading_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM books WHERE status = 'unfinished'")
    unfinished_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM books")
    total_count = cursor.fetchone()[0]
    conn.close()
    return {
        "finished": finished_count,
        "reading": reading_count,
        "unfinished": unfinished_count,
        "total": total_count
    }
