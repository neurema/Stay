import os
import sqlite3
import pytest
from app import db, services, models

# Use a test database
TEST_DB = "test_stay_crunch.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup
    os.environ["STAY_CRUNCH_DB"] = TEST_DB
    # Update db module's DB_PATH if it was already imported/initialized
    app_db_path = os.path.abspath(TEST_DB)
    # We might need to monkeypatch db.DB_PATH if it's a global constant that doesn't read env var on every call
    # In db.py: DB_PATH = os.getenv(...)
    # So if db was imported before we set env var, it has the old value.
    # We should patch it.
    db.DB_PATH = TEST_DB
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    db.init_db()
    
    yield
    
    # Teardown
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass

def test_topic_persistence():
    # 1. Create a topic
    payload = models.TopicCreate(
        subject_tag="Physics",
        difficulty=0.8, # Hard
        add_day=1,
        rt_ratio=3.0,
        accuracy=0.9,
        nd=100,
        ns=50,
        tmin_label="Major"
    )
    
    topic = services.create_topic(payload)
    topic_id = topic.id
    
    # 2. Verify it's in DB
    stored_data = db.get_topic(topic_id)
    assert stored_data is not None
    assert stored_data["subject_tag"] == "Physics"
    
    # 3. Simulate restart: clear in-memory state
    # services._topics is gone, so just clear scheduler
    services._scheduler.clear()
    
    # Verify we can still get topic (it fetches from DB)
    retrieved_topic = services.get_topic(topic_id)
    assert retrieved_topic is not None
        
    # 4. Initialize from DB (to repopulate scheduler)
    services.init_scheduler_from_db()
    
    # 5. Verify it's back
    retrieved_topic = services.get_topic(topic_id)
    assert retrieved_topic.id == topic_id
    assert retrieved_topic.subject_tag == "Physics"
    assert retrieved_topic.is_hard == True
    
    # Check schedule is registered (by checking if we can get it via scheduler or services internal check)
    # services._scheduler is private, but we can check if get_schedule_for_day works
    # The topic add day is 1. Hard topic schedule should have reviews.
    schedule = services.get_schedule_for_day(topic.schedule[0])
    assert topic_id in schedule["topics"]

def test_revision_persistence():
    # 1. Create topic
    payload = models.TopicCreate(
        subject_tag="Math",
        difficulty=0.5,
        add_day=1,
        rt_ratio=3.0,
        accuracy=0.9,
        nd=100,
        ns=50
    )
    topic = services.create_topic(payload)
    
    # 2. Execute revision
    rev_result = models.SessionResult(
        topic_id=topic.id,
        day=topic.schedule[0],
        success=True
    )
    updated_topic = services.execute_revision(rev_result)
    
    assert updated_topic.revision_count == 1
    
    # 3. Verify DB has updated state
    stored_data = db.get_topic(topic.id)
    assert stored_data["revision_count"] == 1
    assert len(stored_data["history"]) == 1
    
    # 4. Simulate restart
    services._scheduler.clear()
    services.init_scheduler_from_db()
    
    # 5. Verify state is restored
    restored = services.get_topic(topic.id)
    assert restored.revision_count == 1
    assert len(restored.history) == 1
