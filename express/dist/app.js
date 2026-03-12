"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const pg_1 = __importDefault(require("pg"));
const DATABASE_URL = process.env.DATABASE_URL ||
    "postgresql://ntnt:rQmS9BOUr_yEuc6jZV03bdekIPLxgnou@172.19.0.3:5432/benchmarks";
const pool = new pg_1.default.Pool({
    connectionString: DATABASE_URL,
    max: 50,
    min: 10,
});
const app = (0, express_1.default)();
app.use(express_1.default.json());
app.get("/plaintext", (_req, res) => {
    res.set("Content-Type", "text/plain");
    res.send("Hello, World!");
});
app.get("/json", (_req, res) => {
    res.json({ message: "Hello, World!" });
});
app.get("/users/:id", (req, res) => {
    res.json({ id: req.params.id });
});
app.get("/db", async (_req, res) => {
    const id = Math.floor(Math.random() * 10000) + 1;
    const result = await pool.query("SELECT id, randomnumber FROM world WHERE id = $1", [id]);
    const row = result.rows[0];
    res.json({ id: row.id, randomNumber: row.randomnumber });
});
app.get("/queries", async (req, res) => {
    let count = Math.max(1, Math.min(parseInt(req.query.count) || 1, 500));
    const results = [];
    for (let i = 0; i < count; i++) {
        const id = Math.floor(Math.random() * 10000) + 1;
        const result = await pool.query("SELECT id, randomnumber FROM world WHERE id = $1", [id]);
        results.push({
            id: result.rows[0].id,
            randomNumber: result.rows[0].randomnumber,
        });
    }
    res.json(results);
});
app.get("/template", async (_req, res) => {
    const items = [];
    for (let i = 0; i < 10; i++) {
        const id = Math.floor(Math.random() * 10000) + 1;
        const result = await pool.query("SELECT id, randomnumber FROM world WHERE id = $1", [id]);
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
app.post("/json", (req, res) => {
    res.json(req.body);
});
const PORT = parseInt(process.env.PORT || "3102");
app.listen(PORT, () => {
    console.log(`Express listening on :${PORT}`);
});
