# Local Langfuse

Self-hosted Langfuse for local Jacc tracing. This compose file starts Postgres, ClickHouse, Redis, MinIO, Langfuse web, and Langfuse worker.

```bash
cd docker/langfuse
cp .env.langfuse.example .env.langfuse
# Replace every change-me value with a random secret.
docker compose --env-file .env.langfuse pull
docker compose --env-file .env.langfuse up -d
```

Open `http://localhost:3000`. Create a project, then put its keys in the project `.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

Jacc reads these variables and traces LLM calls through LangChain. Without them, tracing stays disabled.

Check/stop:

```bash
docker compose --env-file .env.langfuse ps
docker compose --env-file .env.langfuse logs -f langfuse-web
docker compose --env-file .env.langfuse down
```

Data remains in Docker volumes until removed explicitly:

```bash
docker compose --env-file .env.langfuse down -v
```
