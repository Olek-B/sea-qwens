import os
import uvicorn

if __name__ == "__main__":
    reload = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run("services.librarian.app:app", host="0.0.0.0", port=8001, reload=reload)
