# scripts/seed.py
import os
import json
import urllib.request
from sqlalchemy.orm import Session

# Add project root to sys.path to enable app imports
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.app.db import SessionLocal, Base, engine
from src.app import schemas, crud

SAMPLE_EVENTS_URL = "https://raw.githubusercontent.com/SetuHQ/hiring-assignments/main/solutions-engineer/sample_events.json"
SAMPLE_EVENTS_PATH = os.path.join(project_root, "sample_events.json")

def download_sample_events():
    """
    Downloads sample_events.json from Setu repository if it doesn't exist locally.
    """
    if not os.path.exists(SAMPLE_EVENTS_PATH):
        print(f"sample_events.json not found locally. Downloading from {SAMPLE_EVENTS_URL}...")
        try:
            req = urllib.request.Request(SAMPLE_EVENTS_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content = response.read()
            with open(SAMPLE_EVENTS_PATH, "wb") as f:
                f.write(content)
            print(f"Successfully downloaded and saved to {SAMPLE_EVENTS_PATH}")
        except Exception as e:
            print(f"Error downloading sample_events.json: {e}")
            raise e
    else:
        print(f"Found sample_events.json locally at {SAMPLE_EVENTS_PATH}")

def seed_database():
    """
    Seeds the database with sample events using optimized batch operations.
    """
    download_sample_events()

    print("Loading events...")
    with open(SAMPLE_EVENTS_PATH, "r", encoding="utf-8") as f:
        events_raw = json.load(f)

    print(f"Loaded {len(events_raw)} events from file. Parsing...")

    parsed_events = []
    for idx, e in enumerate(events_raw):
        try:
            parsed_events.append(schemas.EventIngest(**e))
        except Exception as err:
            print(f"Failed to parse event at index {idx}: {err}")

    print(f"Successfully parsed {len(parsed_events)} events. Starting database seed...")

    # Start db session
    db = SessionLocal()
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)

        # Batch insert
        new_count, dup_count = crud.bulk_ingest_events(db, parsed_events)
        print("==================================================")
        print("              Seeding Summary                     ")
        print("==================================================")
        print(f"New events inserted: {new_count}")
        print(f"Skipped duplicates:  {dup_count}")
        print("Seeding finished successfully!")
        print("==================================================")
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
