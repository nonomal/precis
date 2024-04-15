from calendar import timegm
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import List

from ruamel.yaml import YAML

from app.constants import CONFIG_DIR
from app.db import DB
from app.models import Feed, FeedEntry
from app.notification.engine import notification_handler

logger = getLogger("uvicorn.error")

db = DB()


def load_feeds() -> None:
    with open(Path(CONFIG_DIR, "feeds.yml").resolve(), "r") as fp:
        yaml = YAML(typ="safe")
        configs = yaml.load(fp)
        
    db.clear_active_feeds()
    for config in configs:
        feed = Feed(**config)
        logger.info(f"Found feed id {feed.id} with contents {feed.dict()}")

        db.insert_feed(feed)


async def check_feeds() -> List:

    now = int(datetime.now(tz=timezone.utc).timestamp())
    logger.info(f"Checking feeds starting at time {now}")

    for feed in db.get_feeds():
        logger.info(f"Polling feed {feed.id}: {feed.name}")

        poll_state = db.get_poll_state(feed)
        if poll_state:
            entries = feed.rss.entries
        else:
            # if we have no history, take the first 5
            entries = feed.rss.entries[0:5]

            earliest_init_entry = min([timegm(i.published_parsed) for i in entries])
            db.set_feed_start_ts(feed=feed, start_ts=earliest_init_entry)

        counter = 0
        start_ts = db.get_feed_start_ts(feed=feed)
        for entry in entries:
            published_time = timegm(entry.published_parsed)
            feed_entry = FeedEntry(
                **{
                    "title": entry.title,
                    "url": entry.link,
                    "published_at": timegm(entry.published_parsed),
                    "updated_at": timegm(entry.updated_parsed),
                    "preview": entry.summary,
                    "feed_id": feed.id,
                    "authors": (
                        [i["name"] for i in entry.authors] if "authors" in entry else []
                    ),
                }
            )

            if published_time >= (
                start_ts if start_ts else 0
            ) and not db.feed_entry_exists(feed_entry.id):
                await add_feed_entry(feed=feed, entry=feed_entry)
                counter += 1

        db.update_poll_state(feed=feed, now=now)

        logger.info(f"Found {counter} new item(s) for feed {feed.name}")


async def add_feed_entry(feed: Feed, entry: FeedEntry) -> None:

    logger.info(f"Upserting entry from {feed.name}: {entry.title} - id {entry.id}")

    db.upsert_feed_entry(feed=feed, entry=entry)

    if not feed.preview_only:
        await db.get_entry_content(entry=entry)

    if feed.notify:
        await notification_handler.send_notification(feed=feed, entry=entry)
