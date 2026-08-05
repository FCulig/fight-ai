import json
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_fight_state(fight_id: int, state) -> None:
    state_val = state.value if hasattr(state, "value") else state
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE fights SET state = :state WHERE id = :id"),
            {"state": state_val, "id": fight_id},
        )
        db.execute(
            text("SELECT pg_notify('fight_state', :payload)"),
            {"payload": json.dumps({"id": fight_id, "state": state_val})},
        )
        db.commit()
    finally:
        db.close()
