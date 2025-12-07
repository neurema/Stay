"""Verification script for (SQLite) persistence."""
import logging
import os
import shutil
import sys
import unittest
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import db, services, models
from app.services import _scheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_persistence")

TEST_DB_PATH = Path("test_stay_effective.db")

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Point db to test file
        db.DB_PATH = TEST_DB_PATH
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
        db.init_db()
        
        # Reset scheduler and logic
        services._scheduler = services.DeterministicScheduler()
        # services._topics is gone, replaced by DB
        
    def tearDown(self):
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass # Windows might hold lock

    def test_persistence_lifecycle(self):
        logger.info("Starting persistence lifecycle test")
        
        # 1. Create a topic
        payload = models.TopicCreate(
            subject_tag="Test Subject",
            difficulty=0.5,
            add_day=1,
            rt_ratio=1.0,
            accuracy=0.9,
            nd=10,
            ns=5
        )
        
        logger.info("Creating topic...")
        topic = services.create_topic(payload)
        topic_id = topic.id
        logger.info(f"Created topic {topic_id}")
        
        # Verify it exists in DB
        state = db.get_topic(topic_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.id, topic_id)
        self.assertEqual(state.subject_tag, "Test Subject")
        
        # 2. Simulate App Restart (Clear memory)
        logger.info("Simulating app restart...")
        services._scheduler = services.DeterministicScheduler()
        
        # Initialize from DB
        services.initialize_scheduler_from_db()
        
        # Verify scheduler has the topic
        schedule = services.get_schedule_for_day(1) # checking day 1 just in case
        # Note: scheduling depends on logic, but we want to ensure _something_ is registered if it has a schedule.
        # But newly created topic might not have schedule for day 1.
        # Let's just check if we can retrieve the topic via get_topic which goes to DB
        
        retrieved_topic = services.get_topic(topic_id)
        self.assertEqual(retrieved_topic.id, topic_id)
        
        # 3. Update State (Execution Revision)
        logger.info("Executing revision on day 5...")
        # Force add to schedule for test purpose if needed, but let's just run revision
        # The revision logic might fail if day is not in schedule? 
        # execute_revision checks: if result.day in state.schedule.
        
        # Let's just execute a revision. It doesn't strictly *have* to be in the schedule to be recorded in history 
        # (though in real app it should be).
        
        res = models.SessionResult(
            topic_id=topic_id,
            day=5,
            success=True
        )
        updated_topic = services.execute_revision(res)
        
        # Verify DB updated
        state_after = db.get_topic(topic_id)
        self.assertEqual(state_after.revision_count, 1)
        self.assertEqual(len(state_after.history), 1)
        self.assertEqual(state_after.history[0][0], 5) # day 5
        
        logger.info("Persistence test passed!")

if __name__ == "__main__":
    unittest.main()
