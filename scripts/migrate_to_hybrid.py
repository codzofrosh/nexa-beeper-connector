# scripts/migrate_to_hybrid.py
"""
Migration script to add hybrid classifier support
without breaking existing functionality
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

def migrate_database():
    """
    Add new columns to existing tables
    """
    conn = sqlite3.connect('data/nexa.db')
    cursor = conn.cursor()
    
    # Add classification metadata column (if it doesn't exist)
    try:
        cursor.execute("""
            ALTER TABLE actions 
            ADD COLUMN classification_meta JSON
        """)
        logger.info("Added classification_meta column")
    except sqlite3.OperationalError:
        logger.info("Column already exists, skipping")
    
    # Add classifier_type column
    try:
        cursor.execute("""
            ALTER TABLE actions 
            ADD COLUMN classifier_type TEXT DEFAULT 'rule'
        """)
        logger.info("Added classifier_type column")
    except sqlite3.OperationalError:
        logger.info("Column already exists, skipping")
    
    conn.commit()
    conn.close()
    logger.info("Migration complete!")

if __name__ == "__main__":
    migrate_database()