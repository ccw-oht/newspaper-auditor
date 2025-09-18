from fastapi import FastAPI
from routers import papers, audits
from database import Base, engine

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Newspaper Audit API")

# Register routers
app.include_router(papers.router, prefix="/papers", tags=["papers"])
app.include_router(audits.router, prefix="/audits", tags=["audits"])

@app.get("/")
def root():
    return {"message": "Newspaper Audit API is running"}
