import sys
from pathlib import Path

# Add project root to sys.path if run directly
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.database import init_database, SessionLocal
from src.database.repository import Repository
from src.core.logging import get_logger

logger = get_logger("init_db")

DEFAULT_MERCHANTS = [
    {"id": "mer_electronics_hub", "name": "Apex Electronics India", "category": "electronics", "risk_category": "STANDARD"},
    {"id": "mer_fashion_trends", "name": "Vogue Vogue Apparel", "category": "fashion", "risk_category": "LOW"},
    {"id": "mer_quick_groceries", "name": "BlinkKart Supermarket", "category": "grocery", "risk_category": "LOW"},
    {"id": "mer_digital_gaming", "name": "PixelPlay Gaming Keys", "category": "digital_goods", "risk_category": "HIGH"},
    {"id": "mer_luxury_watches", "name": "Chronos Luxury Timepieces", "category": "jewelry_luxury", "risk_category": "HIGH"},
]


def seed_default_merchants() -> None:
    """Seeds baseline demo merchants."""
    db = SessionLocal()
    try:
        repo = Repository(db)
        for m in DEFAULT_MERCHANTS:
            repo.get_or_create_merchant(
                merchant_id=m["id"],
                name=m["name"],
                category=m["category"],
                risk_category=m["risk_category"],
            )
        logger.info("Default merchants seeded successfully (%d merchants).", len(DEFAULT_MERCHANTS))
    finally:
        db.close()


def main():
    """Main CLI entrypoint to initialize database."""
    logger.info("Starting database initialization...")
    init_database()
    seed_default_merchants()
    logger.info("Database initialization complete.")


if __name__ == "__main__":
    main()
