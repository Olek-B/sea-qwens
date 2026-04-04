from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "seaqwenspassword"

    # ChromaDB
    CHROMA_DB_HOST: str = "localhost"
    CHROMA_DB_PORT: int = 8000

    # App
    DEBUG: bool = True


settings = Settings()
