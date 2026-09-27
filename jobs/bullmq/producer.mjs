// Enqueue BENCH_JOBS jobs (each sleeping BENCH_WORK_MS) with addBulk.
import { Queue } from "bullmq";
import IORedis from "ioredis";

const connection = new IORedis(process.env.REDIS_URL, { maxRetriesPerRequest: null });
const jobs = Number(process.env.BENCH_JOBS ?? 1000);
const workMs = Number(process.env.BENCH_WORK_MS ?? 20);
const queue = new Queue("bench", { connection });

for (let start = 0; start < jobs; start += 1000) {
  const batch = [];
  for (let i = start; i < Math.min(start + 1000, jobs); i++) {
    batch.push({ name: "bench", data: { work_ms: workMs }, opts: { removeOnComplete: true, removeOnFail: true } });
  }
  await queue.addBulk(batch);
}
await queue.close();
await connection.quit();
console.log(`enqueued ${jobs}`);
