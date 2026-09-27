# Sidekiq worker: started as `sidekiq -r ./worker.rb -c <slots> -q bench`.
# Prints one JSON line per completed job in the shared benchmark shape.
require "sidekiq"

Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch("REDIS_URL") }
  config.logger.level = Logger::WARN
end

class BenchJob
  include Sidekiq::Job
  sidekiq_options queue: "bench", retry: false

  def perform(work_ms)
    sleep(work_ms / 1000.0) if work_ms > 0
    ns = Process.clock_gettime(Process::CLOCK_REALTIME, :nanosecond)
    $stderr.write(%({"event":"job.completed","job_id":"#{jid}","timestamp":"#{ns}"}\n))
  end
end
