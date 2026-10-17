import warnings

import asgi
from workers import WorkerEntrypoint

# langgraph-checkpoint 2.0 triggers this LangChain warning on import. Wrangler prints it as an error.
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from app.main import app  # noqa: E402


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await asgi.fetch(app, request.js_object, self.env)
