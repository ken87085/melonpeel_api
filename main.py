import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="瓜之家 Blog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = "https://www.melonpeel.com.tw/wp-json/wp/v2"
HEADERS = {"User-Agent": "Mozilla/5.0"}

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret")
USERNAME = os.environ.get("API_USERNAME", "admin")
PASSWORD = os.environ.get("API_PASSWORD", "changeme")
print(f"[DEBUG] USERNAME={USERNAME}, PASSWORD={PASSWORD}")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != USERNAME or form.password != PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": create_token({"sub": form.username}), "token_type": "bearer"}


def format_post(post: dict) -> dict:
    return {
        "id": post["id"],
        "url": post["link"],
        "title": post["title"]["rendered"],
        "date": post["date"],
        "content": post["content"]["rendered"],
        "excerpt": post["excerpt"]["rendered"],
        "cover_image": post.get("yoast_head_json", {}).get("og_image", [{}])[0].get("url", ""),
        "categories": post.get("categories", []),
        "tags": post.get("tags", []),
    }


def fetch_posts(page: int, per_page: int) -> tuple[list, int, int]:
    r = requests.get(
        f"{BASE}/posts",
        headers=HEADERS,
        params={"page": page, "per_page": per_page, "_embed": 1},
        timeout=15,
    )
    total = int(r.headers.get("X-WP-Total", 0))
    total_pages = int(r.headers.get("X-WP-TotalPages", 0))
    return [format_post(p) for p in r.json()], total, total_pages


@app.get("/articles")
def list_articles(page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100), _=Depends(verify_token)):
    posts, total, total_pages = fetch_posts(page, per_page)
    return {"page": page, "per_page": per_page, "total": total, "total_pages": total_pages, "articles": posts}


@app.get("/articles/all")
def all_articles(_=Depends(verify_token)):
    _, _, total_pages = fetch_posts(1, 100)
    all_posts = []
    for p in range(1, total_pages + 1):
        posts, _, _ = fetch_posts(p, 100)
        all_posts.extend(posts)
    return {"total": len(all_posts), "articles": all_posts}


@app.get("/article/{post_id}")
def get_article(post_id: int, _=Depends(verify_token)):
    r = requests.get(f"{BASE}/posts/{post_id}", headers=HEADERS, timeout=10)
    return format_post(r.json())
