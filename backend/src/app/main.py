from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes import query, system
from app.core.request_log import RequestLogMiddleware, WorkerCORSMiddleware

app = FastAPI(title="CHEMI - Chemistry Chatbot API", version="2.1.0")
register_error_handlers(app)
app.add_middleware(WorkerCORSMiddleware)
app.add_middleware(RequestLogMiddleware)
app.include_router(system.router)
app.include_router(query.router)
