# Enqueue BENCH_JOBS jobs (each sleeping BENCH_WORK_MS) with push_bulk.
require "sidekiq"
require_relative "worker"

Sidekiq.configure_client do |config|
  config.redis = { url: ENV.fetch("REDIS_URL") }
end

jobs = Integer(ENV.fetch("BENCH_JOBS", "1000"))
work_ms = Integer(ENV.fetch("BENCH_WORK_MS", "20"))
jobs.times.each_slice(1000) do |slice|
  Sidekiq::Client.push_bulk("class" => BenchJob, "args" => slice.map { [work_ms] })
end
puts "enqueued #{jobs}"
