import os
import random
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://ntnt:rQmS9BOUr_yEuc6jZV03bdekIPLxgnou@172.19.0.3:5432/benchmarks",
)

pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=10, max_size=50)
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/plaintext")
async def plaintext():
    return PlainTextResponse("Hello, World!")


@app.get("/json")
async def json_test():
    return JSONResponse({"message": "Hello, World!"})


@app.get("/users/{user_id}")
async def user_by_id(user_id: str):
    return JSONResponse({"id": user_id})


@app.get("/db")
async def db_single():
    row_id = random.randint(1, 10000)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, randomnumber FROM world WHERE id = $1", row_id
        )
    return JSONResponse({"id": row["id"], "randomNumber": row["randomnumber"]})


@app.get("/queries")
async def db_multi(count: int = 1):
    count = max(1, min(count, 500))
    results = []
    async with pool.acquire() as conn:
        for _ in range(count):
            row_id = random.randint(1, 10000)
            row = await conn.fetchrow(
                "SELECT id, randomnumber FROM world WHERE id = $1", row_id
            )
            results.append({"id": row["id"], "randomNumber": row["randomnumber"]})
    return JSONResponse(results)


@app.get("/template")
async def template_test():
    items = []
    async with pool.acquire() as conn:
        for _ in range(10):
            row_id = random.randint(1, 10000)
            row = await conn.fetchrow(
                "SELECT id, randomnumber FROM world WHERE id = $1", row_id
            )
            items.append({"id": row["id"], "randomNumber": row["randomnumber"]})

    rows = "".join(
        f"<tr><td>{item['id']}</td><td>{item['randomNumber']}</td></tr>"
        for item in items
    )
    html_content = f"""<!DOCTYPE html>
<html>
<head><title>Benchmark</title></head>
<body>
<h1>World Database</h1>
<table>
<tr><th>ID</th><th>Random Number</th></tr>
{rows}
</table>
</body>
</html>"""
    return HTMLResponse(html_content)


@app.post("/json")
async def json_body(request: Request):
    data = await request.json()
    return JSONResponse(data)
