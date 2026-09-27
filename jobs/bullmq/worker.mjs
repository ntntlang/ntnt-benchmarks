// BullMQ worker: one process, BENCH_CONCURRENCY concurrent jobs.
// Prints one JSON line per completed job in the shared benchmark shape.
import { Worker } from "bullmq";
import IORedis from "ioredis";

// BullMQ 6 needs a constructed client under native ESM.
const connection = new IORedis(process.env.REDIS_URL, { maxRetriesPerRequest: null });
const concurrency = Number(process.env.BENCH_CONCURRENCY ?? 1);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const worker = new Worker(
  "bench",
  async (job) => {
    if (job.data.work_ms > 0) await sleep(job.data.work_ms);
  },
  { connection, concurrency, removeOnComplete: { count: 0 }, removeOnFail: { count: 0 } },
);

worker.on("completed", (job) => {
  const ns = process.hrtime.bigint() - startHr + startNs;
  process.stderr.write(`{"event":"job.completed","job_id":"${job.id}","timestamp":"${ns}"}\n`);
});

// Wall-clock nanoseconds from a monotonic clock anchored once at startup.
const startNs = BigInt(Date.now()) * 1000000n;
const startHr = process.hrtime.bigint();

for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, async () => {
    await worker.close();
    await connection.quit();
    process.exit(0);
  });
}
