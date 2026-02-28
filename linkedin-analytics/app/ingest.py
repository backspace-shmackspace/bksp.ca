"""LinkedIn analytics export ingestion pipeline.

Parses XLS/XLSX exports from LinkedIn's creator analytics page,
deduplicates records, and loads them into the SQLite database.

Format assumptions (PROVISIONAL - based on third-party docs, not a verified export):
  Sheet "DISCOVERY"   -> daily impressions per date
  Sheet "ENGAGEMENT"  -> per-post reactions, comments, shares, clicks
  Sheet "TOP POSTS"   -> top posts with aggregate metrics
  Sheet "FOLLOWERS"   -> daily follower snapshots
  Sheet "DEMOGRAPHICS"-> audience breakdown by category
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models import DailyMetric, DemographicSnapshot, FollowerSnapshot, Post, Upload

logger = logging.getLogger(__name__)

# Maximum file size: 50 MB
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Allowed file extensions
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

# Sheet names expected in the LinkedIn export (PROVISIONAL)
SHEET_DISCOVERY = "DISCOVERY"
SHEET_ENGAGEMENT = "ENGAGEMENT"
SHEET_TOP_POSTS = "TOP POSTS"
SHEET_FOLLOWERS = "FOLLOWERS"
SHEET_DEMOGRAPHICS = "DEMOGRAPHICS"


@dataclass
class ParsedExport:
    """Structured result from parsing a LinkedIn analytics export file."""

    posts: list[dict[str, Any]] = field(default_factory=list)
    daily_metrics: list[dict[str, Any]] = field(default_factory=list)
    follower_snapshots: list[dict[str, Any]] = field(default_factory=list)
    demographic_snapshots: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportStats:
    """Statistics from a completed import operation."""

    posts_upserted: int = 0
    daily_metrics_upserted: int = 0
    follower_snapshots_upserted: int = 0
    demographic_snapshots_upserted: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return (
            self.posts_upserted
            + self.daily_metrics_upserted
            + self.follower_snapshots_upserted
            + self.demographic_snapshots_upserted
        )


class IngestError(Exception):
    """Raised when ingestion cannot proceed."""


class DuplicateFileError(IngestError):
    """Raised when the exact same file has already been imported."""


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file for deduplication.

    Args:
        file_path: Path to the file.

    Returns:
        Hex-encoded SHA256 digest string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_upload(file_path: Path) -> None:
    """Validate an uploaded file before parsing.

    Args:
        file_path: Path to the uploaded file.

    Raises:
        IngestError: If the file fails validation.
    """
    if not file_path.exists():
        raise IngestError(f"File not found: {file_path}")

    if file_path.stat().st_size == 0:
        raise IngestError("Uploaded file is empty.")

    if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise IngestError(
            f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    suffix = file_path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise IngestError(
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def _detect_engine(file_path: Path) -> str:
    """Detect which pandas Excel engine to use based on file extension.

    Args:
        file_path: Path to the file.

    Returns:
        Engine name string for pandas.read_excel().
    """
    suffix = file_path.suffix.lower()
    if suffix == ".xlsx":
        return "openpyxl"
    if suffix == ".xls":
        return "xlrd"
    # Treat .csv separately; this function only handles Excel
    raise IngestError(f"Cannot determine Excel engine for extension '{suffix}'.")


def _safe_int(value: Any, default: int = 0) -> int:
    """Convert a value to int, returning default on failure."""
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning default on failure."""
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_date(value: Any) -> date | None:
    """Parse a date value from various formats."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _load_sheets(file_path: Path) -> dict[str, pd.DataFrame]:
    """Load all sheets from an Excel file or a single CSV.

    Args:
        file_path: Path to the file.

    Returns:
        Dict mapping sheet name -> DataFrame. For CSV files, the
        single sheet is keyed by the file stem.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path, dtype=str)
        return {file_path.stem.upper(): df}

    engine = _detect_engine(file_path)
    xl = pd.ExcelFile(file_path, engine=engine)
    sheets: dict[str, pd.DataFrame] = {}
    for sheet_name in xl.sheet_names:
        try:
            df = xl.parse(sheet_name, dtype=str)
            sheets[sheet_name.strip().upper()] = df
        except Exception as exc:
            logger.warning("Could not parse sheet '%s': %s", sheet_name, exc)
    return sheets


def _parse_discovery_sheet(df: pd.DataFrame, warnings: list[str]) -> list[dict]:
    """Parse DISCOVERY sheet into daily account-level metrics.

    Expected columns (PROVISIONAL): Date, Impressions, Members Reached
    """
    records: list[dict] = []
    col_map = {c.strip().upper(): c for c in df.columns}

    date_col = col_map.get("DATE")
    impressions_col = col_map.get("IMPRESSIONS")

    if not date_col:
        warnings.append("DISCOVERY sheet: 'Date' column not found. Skipping sheet.")
        return records

    for idx, row in df.iterrows():
        row_date = _parse_date(row.get(date_col))
        if not row_date:
            continue

        record: dict[str, Any] = {
            "metric_date": row_date,
            "post_id": None,
            "impressions": _safe_int(row.get(impressions_col, 0)) if impressions_col else 0,
            "members_reached": _safe_int(row.get(col_map.get("MEMBERS REACHED", ""), 0)),
        }
        records.append(record)

    return records


def _parse_engagement_sheet(df: pd.DataFrame, warnings: list[str]) -> list[dict]:
    """Parse ENGAGEMENT sheet into per-post engagement metrics.

    Expected columns (PROVISIONAL): Post Title, Post Date/Published, Impressions,
    Reactions, Comments, Shares, Clicks
    """
    records: list[dict] = []
    col_map = {c.strip().upper(): c for c in df.columns}

    # Try several common column name variants for the date field
    date_col = (
        col_map.get("POST DATE")
        or col_map.get("DATE")
        or col_map.get("PUBLISHED")
        or col_map.get("POST PUBLISHED DATE")
    )

    if not date_col:
        warnings.append("ENGAGEMENT sheet: date column not found. Skipping sheet.")
        return records

    title_col = col_map.get("POST TITLE") or col_map.get("TITLE") or col_map.get("POST TEXT")

    for idx, row in df.iterrows():
        row_date = _parse_date(row.get(date_col))
        if not row_date:
            continue

        title_raw = str(row.get(title_col, "")) if title_col else ""
        title = title_raw.strip()[:100] if title_raw else None

        impressions = _safe_int(row.get(col_map.get("IMPRESSIONS", ""), 0))
        reactions = _safe_int(row.get(col_map.get("REACTIONS", ""), 0))
        comments = _safe_int(row.get(col_map.get("COMMENTS", ""), 0))
        shares = _safe_int(row.get(col_map.get("SHARES", ""), 0))
        clicks = _safe_int(row.get(col_map.get("CLICKS", ""), 0))
        members_reached = _safe_int(row.get(col_map.get("MEMBERS REACHED", ""), 0))

        engagement_rate = 0.0
        if impressions > 0:
            engagement_rate = (reactions + comments + shares) / impressions

        record: dict[str, Any] = {
            "post_date": row_date,
            "title": title,
            "impressions": impressions,
            "reactions": reactions,
            "comments": comments,
            "shares": shares,
            "clicks": clicks,
            "members_reached": members_reached,
            "engagement_rate": engagement_rate,
            "post_type": None,
            "linkedin_post_id": None,
        }

        # Extract LinkedIn post ID if present (e.g. from a URL column)
        post_id_col = col_map.get("POST ID") or col_map.get("LINKEDIN POST ID")
        if post_id_col:
            raw_id = str(row.get(post_id_col, "")).strip()
            if raw_id and raw_id != "nan":
                record["linkedin_post_id"] = raw_id

        post_type_col = col_map.get("POST TYPE") or col_map.get("TYPE") or col_map.get("CONTENT TYPE")
        if post_type_col:
            raw_type = str(row.get(post_type_col, "")).strip()
            if raw_type and raw_type != "nan":
                record["post_type"] = raw_type

        records.append(record)

    return records


def _parse_top_posts_sheet(df: pd.DataFrame, warnings: list[str]) -> list[dict]:
    """Parse TOP POSTS sheet.

    TOP POSTS often has the same columns as ENGAGEMENT but is filtered to
    the best-performing posts. Reuse the same parsing logic.
    """
    return _parse_engagement_sheet(df, warnings)


def _parse_followers_sheet(df: pd.DataFrame, warnings: list[str]) -> list[dict]:
    """Parse FOLLOWERS sheet into follower snapshots.

    Expected columns (PROVISIONAL): Date, Total Followers, New Followers
    """
    records: list[dict] = []
    col_map = {c.strip().upper(): c for c in df.columns}

    date_col = col_map.get("DATE")
    total_col = (
        col_map.get("TOTAL FOLLOWERS")
        or col_map.get("FOLLOWERS")
        or col_map.get("TOTAL")
    )

    if not date_col:
        warnings.append("FOLLOWERS sheet: 'Date' column not found. Skipping sheet.")
        return records

    if not total_col:
        warnings.append("FOLLOWERS sheet: total followers column not found. Skipping sheet.")
        return records

    new_col = col_map.get("NEW FOLLOWERS") or col_map.get("NET NEW FOLLOWERS")

    for idx, row in df.iterrows():
        row_date = _parse_date(row.get(date_col))
        if not row_date:
            continue

        total = _safe_int(row.get(total_col, 0))
        if total == 0:
            continue

        records.append(
            {
                "snapshot_date": row_date,
                "total_followers": total,
                "new_followers": _safe_int(row.get(new_col, 0)) if new_col else 0,
            }
        )

    return records


def _parse_demographics_sheet(df: pd.DataFrame, warnings: list[str]) -> list[dict]:
    """Parse DEMOGRAPHICS sheet into demographic snapshots.

    Expected layout (PROVISIONAL): multiple blocks per category.
    Each block has a header row (category name) followed by value/percentage rows.
    """
    records: list[dict] = []
    snapshot_date = date.today()
    col_map = {c.strip().upper(): c for c in df.columns}

    # Try structured columns first (category, value, percentage)
    cat_col = col_map.get("CATEGORY")
    val_col = col_map.get("VALUE") or col_map.get("SEGMENT")
    pct_col = col_map.get("PERCENTAGE") or col_map.get("%")

    if cat_col and val_col and pct_col:
        for idx, row in df.iterrows():
            category = str(row.get(cat_col, "")).strip()
            value = str(row.get(val_col, "")).strip()
            pct = _safe_float(row.get(pct_col, 0.0))
            if category and value and category.lower() != "nan" and value.lower() != "nan":
                records.append(
                    {
                        "snapshot_date": snapshot_date,
                        "category": category.lower(),
                        "value": value,
                        "percentage": pct,
                    }
                )
        return records

    # Fall back to heuristic parsing: detect category headers and data rows
    current_category: str | None = None
    for idx, row in df.iterrows():
        row_values = [str(v).strip() for v in row.values if str(v).strip() and str(v).strip() != "nan"]
        if not row_values:
            continue

        # Single non-numeric cell = category header
        if len(row_values) == 1 and not row_values[0].replace(".", "").replace("%", "").isnumeric():
            current_category = row_values[0].lower()
            continue

        if current_category and len(row_values) >= 2:
            label = row_values[0]
            try:
                pct = float(row_values[1].replace("%", "").strip())
            except ValueError:
                continue
            records.append(
                {
                    "snapshot_date": snapshot_date,
                    "category": current_category,
                    "value": label,
                    "percentage": pct,
                }
            )

    if not records:
        warnings.append("DEMOGRAPHICS sheet: could not parse any demographic records.")

    return records


def parse_linkedin_export(file_path: Path) -> ParsedExport:
    """Parse a LinkedIn analytics export file into structured data.

    Args:
        file_path: Path to the .xlsx, .xls, or .csv file.

    Returns:
        ParsedExport dataclass containing parsed records and any warnings.

    Raises:
        IngestError: If the file cannot be parsed.
    """
    validate_upload(file_path)

    result = ParsedExport()

    try:
        sheets = _load_sheets(file_path)
    except Exception as exc:
        raise IngestError(f"Failed to read file '{file_path.name}': {exc}") from exc

    if not sheets:
        raise IngestError("No sheets found in file.")

    sheet_names = set(sheets.keys())
    logger.info("Loaded sheets: %s", sorted(sheet_names))

    # DISCOVERY sheet -> daily account-level metrics
    if SHEET_DISCOVERY in sheet_names:
        result.daily_metrics.extend(
            _parse_discovery_sheet(sheets[SHEET_DISCOVERY], result.warnings)
        )
    else:
        result.warnings.append(f"Sheet '{SHEET_DISCOVERY}' not found.")

    # ENGAGEMENT sheet -> posts
    if SHEET_ENGAGEMENT in sheet_names:
        result.posts.extend(
            _parse_engagement_sheet(sheets[SHEET_ENGAGEMENT], result.warnings)
        )
    elif SHEET_TOP_POSTS in sheet_names:
        result.warnings.append(
            f"Sheet '{SHEET_ENGAGEMENT}' not found; falling back to '{SHEET_TOP_POSTS}'."
        )

    # TOP POSTS sheet -> merge into posts (dedup by date+title during DB load)
    if SHEET_TOP_POSTS in sheet_names:
        top_posts = _parse_top_posts_sheet(sheets[SHEET_TOP_POSTS], result.warnings)
        # Add only records not already captured by ENGAGEMENT sheet
        existing_keys = {
            (p["post_date"], p["title"]) for p in result.posts
        }
        for record in top_posts:
            key = (record["post_date"], record["title"])
            if key not in existing_keys:
                result.posts.append(record)
                existing_keys.add(key)

    # FOLLOWERS sheet -> follower snapshots
    if SHEET_FOLLOWERS in sheet_names:
        result.follower_snapshots.extend(
            _parse_followers_sheet(sheets[SHEET_FOLLOWERS], result.warnings)
        )
    else:
        result.warnings.append(f"Sheet '{SHEET_FOLLOWERS}' not found.")

    # DEMOGRAPHICS sheet -> demographic snapshots
    if SHEET_DEMOGRAPHICS in sheet_names:
        result.demographic_snapshots.extend(
            _parse_demographics_sheet(sheets[SHEET_DEMOGRAPHICS], result.warnings)
        )
    else:
        result.warnings.append(f"Sheet '{SHEET_DEMOGRAPHICS}' not found.")

    logger.info(
        "Parsed: %d posts, %d daily metrics, %d follower snapshots, %d demographic records",
        len(result.posts),
        len(result.daily_metrics),
        len(result.follower_snapshots),
        len(result.demographic_snapshots),
    )

    return result


def _upsert_post(session: Session, record: dict[str, Any]) -> Post:
    """Insert or update a Post record using UPSERT semantics.

    The higher value wins for cumulative metrics when updating an existing post.
    """
    existing: Post | None = None

    # Try LinkedIn post ID first (most reliable)
    if record.get("linkedin_post_id"):
        existing = session.query(Post).filter_by(
            linkedin_post_id=record["linkedin_post_id"]
        ).first()

    # Fall back to composite key: post_date + title[:100]
    if not existing and record.get("post_date") and record.get("title"):
        existing = (
            session.query(Post)
            .filter_by(post_date=record["post_date"], title=record["title"])
            .first()
        )

    # Fall back to date-only match when title is None
    if not existing and record.get("post_date") and not record.get("title"):
        existing = (
            session.query(Post)
            .filter_by(post_date=record["post_date"], title=None)
            .first()
        )

    if existing:
        # Higher value wins for cumulative metrics
        existing.impressions = max(existing.impressions or 0, record.get("impressions", 0))
        existing.members_reached = max(existing.members_reached or 0, record.get("members_reached", 0))
        existing.reactions = max(existing.reactions or 0, record.get("reactions", 0))
        existing.comments = max(existing.comments or 0, record.get("comments", 0))
        existing.shares = max(existing.shares or 0, record.get("shares", 0))
        existing.clicks = max(existing.clicks or 0, record.get("clicks", 0))
        if record.get("linkedin_post_id") and not existing.linkedin_post_id:
            existing.linkedin_post_id = record["linkedin_post_id"]
        if record.get("post_type") and not existing.post_type:
            existing.post_type = record["post_type"]
        existing.recalculate_engagement_rate()
        return existing

    post = Post(
        linkedin_post_id=record.get("linkedin_post_id"),
        title=record.get("title"),
        post_date=record["post_date"],
        post_type=record.get("post_type"),
        impressions=record.get("impressions", 0),
        members_reached=record.get("members_reached", 0),
        reactions=record.get("reactions", 0),
        comments=record.get("comments", 0),
        shares=record.get("shares", 0),
        clicks=record.get("clicks", 0),
        engagement_rate=record.get("engagement_rate", 0.0),
    )
    session.add(post)
    return post


def _upsert_daily_metric(session: Session, record: dict[str, Any]) -> None:
    """Insert or update a DailyMetric record."""
    post_id = record.get("post_id")
    if post_id is None:
        # SQLite treats NULL != NULL, so filter_by(post_id=None) won't match.
        # Use explicit IS NULL filter for account-level metrics.
        from sqlalchemy import null
        existing = (
            session.query(DailyMetric)
            .filter(
                DailyMetric.post_id.is_(None),
                DailyMetric.metric_date == record["metric_date"],
            )
            .first()
        )
    else:
        existing = (
            session.query(DailyMetric)
            .filter_by(post_id=post_id, metric_date=record["metric_date"])
            .first()
        )
    if existing:
        existing.impressions = max(existing.impressions or 0, record.get("impressions", 0))
        existing.members_reached = max(existing.members_reached or 0, record.get("members_reached", 0))
        existing.reactions = max(existing.reactions or 0, record.get("reactions", 0))
        existing.comments = max(existing.comments or 0, record.get("comments", 0))
        existing.shares = max(existing.shares or 0, record.get("shares", 0))
        existing.clicks = max(existing.clicks or 0, record.get("clicks", 0))
        return

    metric = DailyMetric(
        post_id=record.get("post_id"),
        metric_date=record["metric_date"],
        impressions=record.get("impressions", 0),
        members_reached=record.get("members_reached", 0),
        reactions=record.get("reactions", 0),
        comments=record.get("comments", 0),
        shares=record.get("shares", 0),
        clicks=record.get("clicks", 0),
    )
    session.add(metric)


def _upsert_follower_snapshot(session: Session, record: dict[str, Any]) -> None:
    """Insert or update a FollowerSnapshot record."""
    existing = (
        session.query(FollowerSnapshot)
        .filter_by(snapshot_date=record["snapshot_date"])
        .first()
    )
    if existing:
        existing.total_followers = record["total_followers"]
        existing.new_followers = record.get("new_followers", 0)
        return

    snapshot = FollowerSnapshot(
        snapshot_date=record["snapshot_date"],
        total_followers=record["total_followers"],
        new_followers=record.get("new_followers", 0),
    )
    session.add(snapshot)


def _upsert_demographic_snapshot(session: Session, record: dict[str, Any]) -> None:
    """Insert or update a DemographicSnapshot record."""
    existing = (
        session.query(DemographicSnapshot)
        .filter_by(
            snapshot_date=record["snapshot_date"],
            category=record["category"],
            value=record["value"],
        )
        .first()
    )
    if existing:
        existing.percentage = record["percentage"]
        return

    snapshot = DemographicSnapshot(
        snapshot_date=record["snapshot_date"],
        category=record["category"],
        value=record["value"],
        percentage=record["percentage"],
    )
    session.add(snapshot)


def load_to_db(session: Session, parsed: ParsedExport) -> ImportStats:
    """Load parsed export data into the database.

    Uses UPSERT semantics: higher value wins for cumulative metrics.

    Args:
        session: SQLAlchemy session.
        parsed: ParsedExport from parse_linkedin_export().

    Returns:
        ImportStats with counts of upserted records.
    """
    stats = ImportStats(warnings=list(parsed.warnings))

    # Upsert posts
    for record in parsed.posts:
        try:
            _upsert_post(session, record)
            stats.posts_upserted += 1
        except Exception as exc:
            msg = f"Failed to upsert post (date={record.get('post_date')}): {exc}"
            logger.warning(msg)
            stats.warnings.append(msg)

    session.flush()  # Ensure post IDs are available for daily metrics

    # Upsert daily account-level metrics (post_id=None)
    for record in parsed.daily_metrics:
        try:
            _upsert_daily_metric(session, record)
            stats.daily_metrics_upserted += 1
        except Exception as exc:
            msg = f"Failed to upsert daily metric (date={record.get('metric_date')}): {exc}"
            logger.warning(msg)
            stats.warnings.append(msg)

    # Upsert follower snapshots
    for record in parsed.follower_snapshots:
        try:
            _upsert_follower_snapshot(session, record)
            stats.follower_snapshots_upserted += 1
        except Exception as exc:
            msg = f"Failed to upsert follower snapshot (date={record.get('snapshot_date')}): {exc}"
            logger.warning(msg)
            stats.warnings.append(msg)

    # Upsert demographic snapshots
    for record in parsed.demographic_snapshots:
        try:
            _upsert_demographic_snapshot(session, record)
            stats.demographic_snapshots_upserted += 1
        except Exception as exc:
            msg = f"Failed to upsert demographic (category={record.get('category')}): {exc}"
            logger.warning(msg)
            stats.warnings.append(msg)

    session.commit()

    logger.info(
        "Import complete: %d posts, %d daily metrics, %d follower snapshots, %d demographics",
        stats.posts_upserted,
        stats.daily_metrics_upserted,
        stats.follower_snapshots_upserted,
        stats.demographic_snapshots_upserted,
    )

    return stats


def ingest_file(
    session: Session,
    file_path: Path,
    original_filename: str,
) -> tuple[Upload, ImportStats]:
    """Full ingestion pipeline: validate, deduplicate, parse, and load.

    Args:
        session: SQLAlchemy session.
        file_path: Path to the saved upload file.
        original_filename: Original filename from the HTTP upload.

    Returns:
        Tuple of (Upload record, ImportStats).

    Raises:
        DuplicateFileError: If the file has already been imported.
        IngestError: If ingestion fails for any other reason.
    """
    # File-level deduplication via SHA256
    file_hash = compute_file_hash(file_path)
    existing_upload = session.query(Upload).filter_by(file_hash=file_hash).first()
    if existing_upload:
        raise DuplicateFileError(
            f"File '{original_filename}' has already been imported "
            f"(uploaded as '{existing_upload.filename}' on {existing_upload.upload_date})."
        )

    parsed = parse_linkedin_export(file_path)
    stats = load_to_db(session, parsed)

    upload = Upload(
        filename=original_filename,
        file_hash=file_hash,
        records_imported=stats.total_records,
        status="completed",
    )
    session.add(upload)
    session.commit()

    return upload, stats
