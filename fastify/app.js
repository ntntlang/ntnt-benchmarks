import Fastify from 'fastify';
import pg from 'pg';

const { Pool } = pg;
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgres://user:pass@localhost:5432/benchmarks'
});

const fastify = Fastify({ logger: false });

// plaintext
fastify.get('/plaintext', async (req, reply) => {
  reply.type('text/plain').send('Hello, World!');
});

// json
fastify.get('/json', async (req, reply) => {
  return { message: 'Hello, World!' };
});

// params
fastify.get('/users/:id', async (req, reply) => {
  return { id: req.params.id };
});

// db single
fastify.get('/db', async (req, reply) => {
  const id = Math.floor(Math.random() * 10000) + 1;
  const { rows } = await pool.query('SELECT id, randomnumber FROM world WHERE id = $1', [id]);
  return { id: rows[0].id, randomNumber: rows[0].randomnumber };
});

// queries
fastify.get('/queries', async (req, reply) => {
  let count = parseInt(req.query.count) || 1;
  if (count < 1) count = 1;
  if (count > 500) count = 500;
  const results = [];
  for (let i = 0; i < count; i++) {
    const id = Math.floor(Math.random() * 10000) + 1;
    const { rows } = await pool.query('SELECT id, randomnumber FROM world WHERE id = $1', [id]);
    results.push({ id: rows[0].id, randomNumber: rows[0].randomnumber });
  }
  return results;
});

// template
fastify.get('/template', async (req, reply) => {
  const items = [];
  for (let i = 0; i < 10; i++) {
    const id = Math.floor(Math.random() * 10000) + 1;
    const { rows } = await pool.query('SELECT id, randomnumber FROM world WHERE id = $1', [id]);
    items.push(rows[0]);
  }
  let html = `<!DOCTYPE html><html><head><title>Benchmark</title></head><body>
<h1>World Database</h1><table><tr><th>ID</th><th>Random Number</th></tr>`;
  for (const item of items) {
    html += `<tr><td>${item.id}</td><td>${item.randomnumber}</td></tr>`;
  }
  html += `</table></body></html>`;
  reply.type('text/html').send(html);
});

// json-body
fastify.post('/json', async (req, reply) => {
  return req.body;
});

fastify.listen({ port: parseInt(process.env.PORT) || 3106, host: '0.0.0.0' }, (err) => {
  if (err) { console.error(err); process.exit(1); }
  console.log('Fastify listening on', fastify.server.address().port);
});
