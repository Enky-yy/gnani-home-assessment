import os
import sys
# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from sqlalchemy import text
from app.config import settings
from app.database import engine, init_db, AsyncSessionLocal
from app.models.audio_note import AudioNote

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_postgres")


async def verify_postgres():
    print("=" * 60)
    print(" AUDIO NOTES PLATFORM — DATABASE CONNECTIVITY VERIFIER")
    print("=" * 60)
    print(f"Target Database URL: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

    try:
        # Step 1: Connect and query version
        print("\n[1/3] Testing low-level engine connection...")
        async with engine.connect() as conn:
            if "sqlite" in settings.DATABASE_URL:
                result = await conn.execute(text("SELECT sqlite_version();"))
                version = result.scalar()
                print(f" SQLite Connected successfully! Version: {version}")
            else:
                result = await conn.execute(text("SELECT version();"))
                version = result.scalar()
                print(f" PostgreSQL Connected successfully!\n      {version}")

        # Step 2: Initialize tables
        print("\n[2/3] Checking and creating application tables...")
        await init_db()
        print(" Tables verified and created on database.")

        # Step 3: Test session query on AudioNote
        print("\n[3/3] Querying audio_notes table...")
        async with AsyncSessionLocal() as session:
            count_result = await session.execute(text("SELECT count(*) FROM audio_notes;"))
            count = count_result.scalar()
            print(f" Successfully queried audio_notes table! Existing records: {count}")

        print("\n" + "=" * 60)
        print(" DATABASE VERIFICATION PASSED: Ready for application use!")
        print("=" * 60)
        return True

    except Exception as e:
        print("\n" + "!" * 60)
        print(f" DATABASE CONNECTION FAILED: {type(e).__name__}: {e}")
        print("!" * 60)
        if "Connection refused" in str(e):
            print("\n TIP: PostgreSQL server is not running or port 5432 is not accessible.")
            print(" If running Docker, execute:")
            print("     docker compose up -d db")
        elif "password authentication failed" in str(e):
            print("\n TIP: PostgreSQL credentials in DATABASE_URL do not match the database.")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify_postgres())
