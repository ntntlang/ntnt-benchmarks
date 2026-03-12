import express, { Request, Response } from "express";
import pg from "pg";

const DATABASE_URL =
  process.env.DATABASE_URL ||
  "postgresql://ntnt:rQmS9BOUr_yEuc6jZV03bdekIPLxgnou@172.19.0.3:5432/benchmarks";

const pool = new pg.Pool({
  connectionString: DATABASE_URL,
  max: 50,
  min: 10,
});

const app = express();
app.use(express.json());

app.get("/plaintext", (_req: Request, res: Response) => {
  res.set("Content-Type", "text/plain");
  res.send("Hello, World!");
});

app.get("/json", (_req: Request, res: Response) => {
  res.json({ message: "Hello, World!" });
});

app.get("/users/:id", (req: Request, res: Response) => {
  res.json({ id: req.params.id });
});

app.get("/db", async (_req: Request, res: Response) => {
  const id = Math.floor(Math.random() * 10000) + 1;
  const result = await pool.query(
    "SELECT id, randomnumber FROM world WHERE id = $1",
    [id]
  );
  const row = result.rows[0];
  res.json({ id: row.id, randomNumber: row.randomnumber });
});

app.get("/queries", async (req: Request, res: Response) => {
  let count = Math.max(1, Math.min(parseInt(req.query.count as string) || 1, 500));
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
  res.json(results);
});

app.get("/template", async (_req: Request, res: Response) => {
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
  res.send(`<!DOCTYPE html>
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

app.post("/json", (req: Request, res: Response) => {
  res.json(req.body);
});

const PORT = parseInt(process.env.PORT || "3102");
app.listen(PORT, () => {
  console.log(`Express listening on :${PORT}`);
});
