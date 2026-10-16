from fastapi import FastAPI

from app.api.routes import query, system

app = FastAPI(title="CHEMI - Chemistry Chatbot API", version="2.0.0")
app.include_router(system.router)
app.include_router(query.router)
