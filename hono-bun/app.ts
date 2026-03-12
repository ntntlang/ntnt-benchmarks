import { Hono } from "hono";
import { Pool } from "pg";

const DATABASE_URL =
  process.env.DATABASE_URL ||
  "postgresql://ntnt:rQmS9BOUr_yEuc6jZV03bdekIPLxgnou@172.19.0.3:5432/benchmarks";

const pool = new Pool({
  connectionString: DATABASE_URL,
  max: 50,
  min: 10,
});

const app = new Hono();

app.get("/plaintext", (c) => {
  return c.text("Hello, World!");
});

app.get("/json", (c) => {
  return c.json({ message: "Hello, World!" });
});

app.get("/users/:id", (c) => {
  return c.json({ id: c.req.param("id") });
});

app.get("/db", async (c) => {
  const id = Math.floor(Math.random() * 10000) + 1;
  const result = await pool.query(
    "SELECT id, randomnumber FROM world WHERE id = $1",
    [id]
  );
  const row = result.rows[0];
  return c.json({ id: row.id, randomNumber: row.randomnumber });
});

app.get("/queries", async (c) => {
  let count = Math.max(
    1,
    Math.min(parseInt(c.req.query("count") || "1") || 1, 500)
  );
  const results = [];
  for (let i = 0; i < count; i++) {
    const id = Math.floor(Math.random() * 10000) + 1;
    const result = await pool.query(
      "SELECT id, randomnumber FROM world WHERE id = $1",
      [id]
    );
    results.push({
      id: result.rows[0].id,
      randomNumber: result.rows[0].randomnumber,
    });
  }
  return c.json(results);
});

app.get("/template", async (c) => {
  const items = [];
  for (let i = 0; i < 10; i++) {
    const id = Math.floor(Math.random() * 10000) + 1;
    const result = await pool.query(
      "SELECT id, randomnumber FROM world WHERE id = $1",
      [id]
    );
    items.push(result.rows[0]);
  }
  const rows = items
    .map((r) => `<tr><td>${r.id}</td><td>${r.randomnumber}</td></tr>`)
    .join("");
  return c.html(`<!DOCTYPE html>
<html>
<head><title>Benchmark</title></head>
<body>
<h1>World Database</h1>
<table>
<tr><th>ID</th><th>Random Number</th></tr>
${rows}
</table>
</body>
</html>`);
});

app.post("/json", async (c) => {
  const data = await c.req.json();
  return c.json(data);
});

export default {
  port: 3104,
  fetch: app.fetch,
};
