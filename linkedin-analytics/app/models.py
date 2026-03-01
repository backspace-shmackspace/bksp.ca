"""SQLAlchemy ORM models for the LinkedIn analytics database."""

from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "posts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_post_id: str | None = Column(String, unique=True, nullable=True)
    post_url: str | None = Column(String, nullable=True)
    draft_id: str | None = Column(String(20), nullable=True)
    title: str | None = Column(String(100), nullable=True)
    post_date: date = Column(Date, nullable=False)
    post_type: str | None = Column(String, nullable=True)
    impressions: int = Column(Integer, default=0)
    members_reached: int = Column(Integer, default=0)
    reactions: int = Column(Integer, default=0)
    comments: int = Column(Integer, default=0)
    shares: int = Column(Integer, default=0)
    clicks: int = Column(Integer, default=0)
    engagement_rate: float = Column(Float, default=0.0)
    topic: str | None = Column(String(50), nullable=True)
    content_format: str | None = Column("content_format", String(30), nullable=True)
    hook_style: str | None = Column(String(30), nullable=True)
    length_bucket: str | None = Column(String(20), nullable=True)
    post_hour: int | None = Column(Integer, nullable=True)
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())

    # Post body content (stored when composed via the dashboard composer)
    content: str | None = Column("content", Text, nullable=True)

    # Post lifecycle status: "draft", "published", "analytics_linked", or None (imported)
    status: str | None = Column("status", String(20), nullable=True)

    # Additional per-post metrics from per-post XLSX exports
    saves: int | None = Column(Integer, nullable=True, default=0)
    sends: int | None = Column(Integer, nullable=True, default=0)
    profile_views: int | None = Column(Integer, nullable=True, default=0)
    followers_gained: int | None = Column(Integer, nullable=True, default=0)
    reposts: int | None = Column(Integer, nullable=True, default=0)

    daily_metrics = relationship(
        "DailyMetric", back_populates="post", cascade="all, delete-orphan"
    )
    demographics = relationship(
        "PostDemographic", back_populates="post", cascade="all, delete-orphan"
    )

    @property
    def display_title(self) -> str:
        """Human-readable title for display. Falls back to draft_id or date + ID."""
        if self.title:
            return self.title
        if self.draft_id:
            return f"#{self.draft_id} ({self.post_date})"
        if self.linkedin_post_id:
            return f"Post {self.post_date} (#{self.linkedin_post_id[-6:]})"
        return f"Post {self.post_date}"

    @property
    def weighted_score(self) -> float:
        """Quality-weighted engagement score.

        Formula: ((1 * reactions) + (3 * comments) + (4 * shares)) / impressions
        Comments weighted 3x (signal deeper engagement).
        Shares weighted 4x (signal advocacy/amplification).
        """
        if not self.impressions or self.impressions == 0:
            return 0.0
        return (
            (1 * (self.reactions or 0))
            + (3 * (self.comments or 0))
            + (4 * (self.shares or 0))
        ) / self.impressions

    def recalculate_engagement_rate(self) -> None:
        """Recalculate engagement_rate from raw metrics."""
        if self.impressions and self.impressions > 0:
            self.engagement_rate = (
                (self.reactions or 0) + (self.comments or 0) + (self.shares or 0)
            ) / self.impressions
        else:
            self.engagement_rate = 0.0

    def __repr__(self) -> str:
        return f"<Post id={self.id} date={self.post_date} impressions={self.impressions}>"


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    post_id: int | None = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True
    )
    metric_date: date = Column(Date, nullable=False)
    impressions: int = Column(Integer, default=0)
    members_reached: int = Column(Integer, default=0)
    reactions: int = Column(Integer, default=0)
    comments: int = Column(Integer, default=0)
    shares: int = Column(Integer, default=0)
    clicks: int = Column(Integer, default=0)
    created_at: datetime = Column(DateTime, default=func.now())

    post = relationship("Post", back_populates="daily_metrics")

    __table_args__ = (
        UniqueConstraint("post_id", "metric_date", name="uq_post_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyMetric post_id={self.post_id} date={self.metric_date}>"


class FollowerSnapshot(Base):
    __tablename__ = "follower_snapshots"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: date = Column(Date, nullable=False, unique=True)
    total_followers: int = Column(Integer, nullable=False)
    new_followers: int = Column(Integer, default=0)
    created_at: datetime = Column(DateTime, default=func.now())

    def __repr__(self) -> str:
        return f"<FollowerSnapshot date={self.snapshot_date} total={self.total_followers}>"


class DemographicSnapshot(Base):
    __tablename__ = "demographic_snapshots"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: date = Column(Date, nullable=False)
    category: str = Column(String, nullable=False)
    value: str = Column(String, nullable=False)
    percentage: float = Column(Float, nullable=False)
    created_at: datetime = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "snapshot_date", "category", "value", name="uq_demo_snapshot"
        ),
    )

    def __repr__(self) -> str:
        return f"<DemographicSnapshot date={self.snapshot_date} {self.category}={self.value}>"


class PostDemographic(Base):
    """Per-post demographic breakdown from LinkedIn per-post XLSX exports.

    Stores category/value/percentage triples for each post. Categories include:
    - "company_size": e.g., "10,001+ employees", "1001-5000 employees"
    - "job_title": e.g., "Software Engineer", "Security Engineer"
    - "location": e.g., "Fredericton", "Greater Toronto Area, Canada"
    - "company": e.g., "IBM", "OCAS"

    The "company_size" and "company" categories are new (only available in
    per-post exports, not in the aggregate DISCOVERY/ENGAGEMENT export).
    """

    __tablename__ = "post_demographics"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    post_id: int = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    category: str = Column(String, nullable=False)
    value: str = Column(String, nullable=False)
    percentage: float = Column(Float, nullable=False)
    created_at: datetime = Column(DateTime, default=func.now())

    post = relationship("Post", back_populates="demographics")

    __table_args__ = (
        UniqueConstraint("post_id", "category", "value", name="uq_post_demo"),
    )

    def __repr__(self) -> str:
        return f"<PostDemographic post={self.post_id} {self.category}={self.value}>"


class Upload(Base):
    __tablename__ = "uploads"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    filename: str = Column(String, nullable=False)
    file_hash: str = Column(String, nullable=False, unique=True)
    upload_date: datetime = Column(DateTime, default=func.now())
    records_imported: int = Column(Integer, default=0)
    status: str = Column(String, default="completed")

    def __repr__(self) -> str:
        return f"<Upload id={self.id} file={self.filename} status={self.status}>"


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    provider: str = Column(String, nullable=False, default="linkedin", unique=True)
    access_token_encrypted: str = Column(String, nullable=False)
    refresh_token_encrypted: str = Column(String, nullable=False)
    access_token_expires_at: datetime = Column(DateTime, nullable=False)
    refresh_token_expires_at: datetime = Column(DateTime, nullable=False)
    scopes: str = Column(String, nullable=False)  # space-separated scope list
    linkedin_member_id: str | None = Column(String, nullable=True)  # URN sub from /userinfo
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<OAuthToken provider={self.provider} expires_at={self.access_token_expires_at}>"
