from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import SessionLocal
from ..models import Paper

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=list[schemas.PaperOut])
def list_papers(db: Session = Depends(get_db)):
    stmt = select(Paper).options(selectinload(Paper.audits))
    result = db.execute(stmt)
    return result.scalars().all()
