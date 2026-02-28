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
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())

    daily_metrics = relationship(
        "DailyMetric", back_populates="post", cascade="all, delete-orphan"
    )

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
