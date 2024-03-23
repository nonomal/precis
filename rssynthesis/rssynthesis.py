from pathlib import Path
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi_utils.tasks import repeat_every
from fastapi.responses import HTMLResponse
from fastapi.requests import Request

from contextlib import asynccontextmanager
from logging import getLogger
from tinydb import TinyDB

from rssynthesis.rss import load_feeds, check_feeds
from rssynthesis.ui import list_feeds, list_entries, get_entry_content

logger = getLogger("uvicorn.error")
base_path = Path(__file__).parent

db_path = Path(base_path, "../", "db.json").resolve()
db = TinyDB(db_path)

config_path = Path(base_path, "../", "feeds.yml").resolve()

templates = Jinja2Templates(directory=Path(base_path, "templates").resolve())


@repeat_every(seconds=60*5, logger=logger)
async def poll_feeds():
    logger.info("Checking feeds for updates")
    check_feeds()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_feeds(config_path=config_path)
    await poll_feeds()

    yield


app = FastAPI(lifespan=lifespan, title="RSSynthesis", openapi_url="/openapi.json")


@app.get("/", response_class=HTMLResponse)
def root(request: Request):

    return templates.TemplateResponse(
        "index.html", {"request": request, "feeds": list_feeds()}
    )


@app.get("/list-entries/{feed_id}", response_class=HTMLResponse)
def list_entries_by_feed(feed_id: str, request: Request):

    return templates.TemplateResponse(
        "entries.html",
        {"request": request, "entries": list(list_entries(feed_id=feed_id))},
    )


@app.get("/list-entries/", response_class=HTMLResponse)
def list_all_entries(request: Request):

    return templates.TemplateResponse(
        "entries.html",
        {"request": request, "entries": list(list_entries(feed_id=None))},
    )


@app.get("/read/{feed_entry_id}", response_class=HTMLResponse)
def read(feed_entry_id: str, request: Request, ):

    return templates.TemplateResponse(
        "read.html",
        {"request": request, "content": get_entry_content(feed_entry_id=feed_entry_id)},
    )
