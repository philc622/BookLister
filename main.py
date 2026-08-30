from fastapi import FastAPI, Form, Query, Response, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from typing import Optional
from contextlib import asynccontextmanager
import html
import database

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield

app = FastAPI(title="BookLister", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="wwwroot"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("wwwroot/index.html")

def render_book_card(book: dict) -> str:
    book_id = book["id"]
    title = html.escape(book["title"])
    author = html.escape(book["author"])
    status = book["status"]

    status_badge_class = {
        "reading": "badge-reading",
        "finished": "badge-finished",
        "unfinished": "badge-unfinished"
    }.get(status, "badge-reading")

    status_label = {
        "reading": "Currently Reading",
        "finished": "Finished",
        "unfinished": "Unfinished"
    }.get(status, status)

    buttons_html = ""
    if status != "finished":
        buttons_html += f"""
        <button class="btn-action btn-finish"
                hx-post="/books/{book_id}/status?status=finished"
                hx-target="#book-item-{book_id}"
                hx-swap="outerHTML">
            Mark Finished
        </button>
        """
    if status != "reading":
        buttons_html += f"""
        <button class="btn-action btn-reading"
                hx-post="/books/{book_id}/status?status=reading"
                hx-target="#book-item-{book_id}"
                hx-swap="outerHTML">
            Mark Reading
        </button>
        """
    if status != "unfinished":
        buttons_html += f"""
        <button class="btn-action btn-unfinished"
                hx-post="/books/{book_id}/status?status=unfinished"
                hx-target="#book-item-{book_id}"
                hx-swap="outerHTML">
            Mark Unfinished
        </button>
        """

    buttons_html += f"""
    <button class="btn-action btn-delete"
            hx-delete="/books/{book_id}"
            hx-target="#book-item-{book_id}"
            hx-swap="outerHTML">
        Delete
    </button>
    """

    return f"""
    <div class="book-card" id="book-item-{book_id}">
        <div class="book-info">
            <h3 class="book-title">{title}</h3>
            <p class="book-author">by {author}</p>
            <span class="badge {status_badge_class}">{status_label}</span>
        </div>
        <div class="book-actions">
            {buttons_html}
        </div>
    </div>
    """

def render_book_list(books: list, empty_message: str = "No books found.") -> str:
    if not books:
        return f'<div class="empty-state"><p>{html.escape(empty_message)}</p></div>'
    return "".join(render_book_card(b) for b in books)

@app.post("/books", response_class=HTMLResponse)
async def create_book(title: str = Form(...), author: str = Form(...), status: str = Form("reading")):
    if not title.strip() or not author.strip():
        return HTMLResponse(content='<div class="error-message">Title and author are required.</div>', status_code=400)

    database.add_book(title, author, status)
    headers = {"HX-Trigger": "booksUpdated"}
    return HTMLResponse(content="", headers=headers)

@app.get("/books", response_class=HTMLResponse)
async def list_books(status: Optional[str] = Query(None)):
    books = database.get_books(status=status)
    empty_msg = f"No books with status '{status}'." if status else "No books in your list yet."
    return render_book_list(books, empty_message=empty_msg)

@app.post("/books/{book_id}/status", response_class=HTMLResponse)
@app.patch("/books/{book_id}/status", response_class=HTMLResponse)
async def update_status(book_id: int, status: str = Query(...)):
    success = database.update_book_status(book_id, status)
    if not success:
        return HTMLResponse(content='<div class="error-message">Book not found.</div>', status_code=404)

    headers = {"HX-Trigger": "booksUpdated"}
    # Return empty content because HX-Trigger will refresh the book lists and stats
    return HTMLResponse(content="", headers=headers)

@app.delete("/books/{book_id}", response_class=HTMLResponse)
async def delete_book_endpoint(book_id: int):
    success = database.delete_book(book_id)
    if not success:
        return HTMLResponse(content='<div class="error-message">Book not found.</div>', status_code=404)
    headers = {"HX-Trigger": "booksUpdated"}
    return HTMLResponse(content="", headers=headers)

@app.get("/books/search", response_class=HTMLResponse)
async def search_books(q: str = Query("")):
    if not q.strip():
        books = database.get_books(status="finished")
    else:
        books = database.search_read_books(q)

    empty_msg = f"No finished books found matching '{html.escape(q)}'." if q.strip() else "No finished books in your list yet."
    return render_book_list(books, empty_message=empty_msg)

@app.get("/stats", response_class=HTMLResponse)
async def get_stats_endpoint():
    stats = database.get_stats()
    return f"""
    <div class="stats-container">
        <div class="stat-box stat-read">
            <span class="stat-number">{stats['finished']}</span>
            <span class="stat-label">Books Read</span>
        </div>
        <div class="stat-box stat-reading">
            <span class="stat-number">{stats['reading']}</span>
            <span class="stat-label">Currently Reading</span>
        </div>
        <div class="stat-box stat-unfinished">
            <span class="stat-number">{stats['unfinished']}</span>
            <span class="stat-label">Unfinished</span>
        </div>
    </div>
    """
