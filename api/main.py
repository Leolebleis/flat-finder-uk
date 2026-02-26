# api/main.py
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Header, HTTPException, Query, Request

from shared.models import init_db, get_connection, get_listings, insert_listing
from shared.config import DB_PATH, API_KEY


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db(DB_PATH)
    yield


app = FastAPI(title="Flat Finder API", root_path="/flat/api", lifespan=lifespan)

def _check_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/listings")
def list_listings(since: str | None = None, limit: int = Query(50, le=200),
                  offset: int = 0, x_api_key: str = Header(None)):
    _check_key(x_api_key)
    conn = get_connection(DB_PATH)
    listings = get_listings(conn, since=since, limit=limit, offset=offset)
    conn.close()
    return listings

@app.get("/listings/{listing_id}")
def get_listing(listing_id: str, x_api_key: str = Header(None)):
    _check_key(x_api_key)
    conn = get_connection(DB_PATH)
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404)
    return dict(row)

@app.post("/listings")
async def create_listings(request: Request, x_api_key: str = Header(None)):
    _check_key(x_api_key)
    listings = await request.json()
    if not isinstance(listings, list):
        raise HTTPException(status_code=400, detail="Expected a list of listings")
    conn = get_connection(DB_PATH)
    new_count = 0
    for listing in listings:
        if insert_listing(conn, listing):
            new_count += 1
    conn.close()
    return {"inserted": new_count, "total": len(listings)}

@app.get("/stats")
def stats(x_api_key: str = Header(None)):
    _check_key(x_api_key)
    conn = get_connection(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    today = date.today().isoformat()
    new_today = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE first_seen >= ?", (today,)
    ).fetchone()[0]
    avg_price = conn.execute(
        "SELECT AVG(price_pcm) FROM listings WHERE price_pcm IS NOT NULL"
    ).fetchone()[0]
    sources = {}
    for row in conn.execute("SELECT source, COUNT(*) as cnt FROM listings GROUP BY source"):
        sources[row["source"]] = row["cnt"]
    conn.close()
    return {
        "total_listings": total,
        "new_today": new_today,
        "avg_price": round(avg_price) if avg_price else None,
        "sources": sources,
    }
