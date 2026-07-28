"""Per-source scrape health: latch failures and decide when to notify about them.

Kept apart from the run orchestration because it is a small state machine with
its own storage format and interval policy, and because the interesting
behaviour (re-alerting, legacy rows) deserves to be tested without driving a
whole scrape run.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from flat_finder import config
from flat_finder.listings.persistence import ScraperStateDB
from flat_finder.scraper.notifier import (
    format_failure_message,
    format_recovery_message,
    format_still_failing_message,
    send_ntfy,
)

log = logging.getLogger("flat-finder")


def get_scraper_state(session: Session, key: str) -> str | None:
    row = session.get(ScraperStateDB, key)
    return row.value if row else None


def set_scraper_state(session: Session, key: str, value: str) -> None:
    row = session.get(ScraperStateDB, key)
    if row is None:
        row = ScraperStateDB(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.flush()


def delete_scraper_state(session: Session, key: str) -> None:
    row = session.get(ScraperStateDB, key)
    if row:
        session.delete(row)
        session.flush()


def _notify_safe(fn: Callable[..., object], *args: object, **kwargs: object) -> None:
    try:
        fn(*args, **kwargs)
    except Exception:
        log.exception("Notification failed")


def _encode(reason: str, since: datetime, last_alert: datetime) -> str:
    """Serialise a failure record.

    `reason` is stored purely as an operator breadcrumb for inspecting the live
    DB (see CLAUDE.md); nothing reads it back.
    """
    return json.dumps({"error": reason, "since": since.isoformat(), "last_alert": last_alert.isoformat()})


def _decode(raw: str, now: datetime) -> tuple[datetime, datetime]:
    """Read (failing_since, last_alert) out of a stored failure record.

    Rows written before re-alerting existed hold the bare reason string; treat
    those as first seen now, so they re-alert one interval from here rather than
    firing immediately on upgrade.
    """
    try:
        data = json.loads(raw)
        return datetime.fromisoformat(data["since"]), datetime.fromisoformat(data["last_alert"])
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        return now, now


def handle_source_health(
    session: Session,
    ntfy_topic: str | None,
    source: str,
    failure_reason: str | None,
    now: datetime | None = None,
) -> None:
    """Latch a source's health and notify on the changes worth knowing about.

    Notifies on first failure and on recovery, plus a repeat every
    SCRAPER_REALERT_HOURS while a source stays broken. Without that repeat a
    permanently failing source alerts exactly once and thereafter looks
    identical to a healthy one — Rightmove returned nothing for 8 days that way.

    `failure_reason` is "why this source is unhealthy, or None if it is fine";
    today only raised exceptions produce one.
    """
    now = now or datetime.now(UTC)
    state_key = f"{source}_failing"
    stored = get_scraper_state(session, state_key)

    if not failure_reason:
        if stored is not None:
            delete_scraper_state(session, state_key)
            if ntfy_topic:
                _notify_safe(send_ntfy, ntfy_topic, *format_recovery_message(source))
        return

    if stored is None:
        set_scraper_state(session, state_key, _encode(failure_reason, now, now))
        if ntfy_topic:
            _notify_safe(send_ntfy, ntfy_topic, *format_failure_message(source, failure_reason))
        return

    since, last_alert = _decode(stored, now)
    interval = config.SCRAPER_REALERT_HOURS
    due = interval > 0 and now - last_alert >= timedelta(hours=interval)
    alert_at = now if due else last_alert
    # Rewritten every cycle, not just when due: this is what upgrades a legacy
    # bare-reason row to JSON. SQLAlchemy omits the UPDATE when nothing changed.
    set_scraper_state(session, state_key, _encode(failure_reason, since, alert_at))
    if due and ntfy_topic:
        _notify_safe(send_ntfy, ntfy_topic, *format_still_failing_message(source, failure_reason, now - since))
