"""Seed the database with 90 days of realistic sample data for development and testing.

Usage:
    python scripts/seed_sample.py
    python scripts/seed_sample.py --reset  # drop all data first

Generates:
    - 20 sample posts with varied metrics
    - 90 days of daily impression metrics
    - 90 daily follower snapshots
    - Demographic snapshots for 4 categories
"""

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure the app package is importable when running from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, init_db
from app.models import Base, DailyMetric, DemographicSnapshot, FollowerSnapshot, Post

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 42
random.seed(SEED)

NUM_POSTS = 20
DAYS = 90
BASE_DATE = date.today() - timedelta(days=DAYS)

POST_TITLES = [
    "The commitment-without-execution loop in enterprise security",
    "Quantify or kill: how to make risk legible to executives",
    "I built an AI red team that argues with itself",
    "From HackTheBox to the boardroom",
    "Why vulnerability management is a data problem",
    "The real cost of a CVE your team deprioritized",
    "DevSecOps is not a team name",
    "How to run a PSIRT that teams actually trust",
    "Risk registers are lying to you",
    "The anatomy of a security program that doesn't slow delivery",
    "What 80 engineers taught me about security culture",
    "Treat your security backlog like technical debt",
    "Building AI agents for risk operations: week 1 notes",
    "Why I practice offensive security as a hobby",
    "The difference between compliance and security",
    "When your threat model is wrong from the start",
    "Five patterns I've seen fail in every SIEM rollout",
    "How to brief a CISO without putting them to sleep",
    "The security program that scales: lessons from IBM",
    "Automating the boring parts of risk management",
]

POST_TYPES = ["text", "text", "text", "article", "image"]

DEMOGRAPHICS = {
    "industry": [
        ("Information Technology", 32.5),
        ("Financial Services", 18.2),
        ("Cybersecurity", 14.0),
        ("Healthcare", 8.5),
        ("Manufacturing", 5.8),
        ("Other", 21.0),
    ],
    "job_title": [
        ("Director", 22.0),
        ("Manager", 18.5),
        ("Individual Contributor", 30.0),
        ("Executive", 12.0),
        ("Consultant", 10.5),
        ("Other", 7.0),
    ],
    "seniority": [
        ("Senior", 40.0),
        ("Director", 25.0),
        ("Entry", 15.0),
        ("VP", 12.0),
        ("C-Suite", 8.0),
    ],
    "location": [
        ("United States", 55.0),
        ("Canada", 12.0),
        ("United Kingdom", 9.5),
        ("India", 8.0),
        ("Germany", 4.5),
        ("Other", 11.0),
    ],
}


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_posts() -> list[Post]:
    posts = []
    post_interval = DAYS // NUM_POSTS
    for i in range(NUM_POSTS):
        post_date = BASE_DATE + timedelta(days=i * post_interval + random.randint(0, 2))
        impressions = random.randint(800, 6000)
        reactions = random.randint(int(impressions * 0.02), int(impressions * 0.08))
        comments = random.randint(int(reactions * 0.1), int(reactions * 0.4))
        shares = random.randint(int(reactions * 0.05), int(reactions * 0.2))
        clicks = random.randint(int(impressions * 0.01), int(impressions * 0.03))
        members_reached = int(impressions * random.uniform(0.6, 0.8))

        post = Post(
            post_date=post_date,
            title=POST_TITLES[i % len(POST_TITLES)][:100],
            post_type=random.choice(POST_TYPES),
            impressions=impressions,
            members_reached=members_reached,
            reactions=reactions,
            comments=comments,
            shares=shares,
            clicks=clicks,
        )
        post.recalculate_engagement_rate()
        posts.append(post)
    return posts


def generate_daily_metrics() -> list[DailyMetric]:
    metrics = []
    for i in range(DAYS):
        d = BASE_DATE + timedelta(days=i)
        impressions = random.randint(150, 800) + int(i * 1.5)  # Slight upward trend
        metrics.append(
            DailyMetric(
                post_id=None,
                metric_date=d,
                impressions=impressions,
                members_reached=int(impressions * random.uniform(0.6, 0.75)),
            )
        )
    return metrics


def generate_follower_snapshots() -> list[FollowerSnapshot]:
    snapshots = []
    total = random.randint(380, 450)
    for i in range(DAYS):
        d = BASE_DATE + timedelta(days=i)
        new = random.randint(1, 8)
        total += new
        snapshots.append(
            FollowerSnapshot(
                snapshot_date=d,
                total_followers=total,
                new_followers=new,
            )
        )
    return snapshots


def generate_demographics() -> list[DemographicSnapshot]:
    snap_date = date.today()
    records = []
    for category, values in DEMOGRAPHICS.items():
        for value, percentage in values:
            records.append(
                DemographicSnapshot(
                    snapshot_date=snap_date,
                    category=category,
                    value=value,
                    percentage=percentage,
                )
            )
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample data into the LinkedIn analytics database.")
    parser.add_argument("--reset", action="store_true", help="Drop all existing data before seeding.")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        if args.reset:
            print("Resetting database...")
            db.query(DemographicSnapshot).delete()
            db.query(FollowerSnapshot).delete()
            db.query(DailyMetric).delete()
            db.query(Post).delete()
            db.commit()
            print("All data cleared.")

        # Check for existing data
        existing_posts = db.query(Post).count()
        if existing_posts > 0 and not args.reset:
            print(f"Database already contains {existing_posts} posts. Use --reset to clear first.")
            return

        print(f"Generating {NUM_POSTS} posts...")
        posts = generate_posts()
        db.add_all(posts)
        db.commit()
        print(f"  Created {len(posts)} posts")

        print(f"Generating {DAYS} daily metric records...")
        metrics = generate_daily_metrics()
        db.add_all(metrics)
        db.commit()
        print(f"  Created {len(metrics)} daily metrics")

        print(f"Generating {DAYS} follower snapshots...")
        snapshots = generate_follower_snapshots()
        db.add_all(snapshots)
        db.commit()
        print(f"  Created {len(snapshots)} follower snapshots")

        print("Generating demographic records...")
        demographics = generate_demographics()
        db.add_all(demographics)
        db.commit()
        print(f"  Created {len(demographics)} demographic records")

        total = db.query(Post).count()
        followers = db.query(FollowerSnapshot).order_by(FollowerSnapshot.snapshot_date.desc()).first()
        print(f"\nSample data loaded successfully.")
        print(f"  Posts: {total}")
        print(f"  Current followers: {followers.total_followers if followers else 'n/a'}")
        print(f"\nStart the app and visit http://localhost:8050/dashboard")

    finally:
        db.close()


if __name__ == "__main__":
    main()
