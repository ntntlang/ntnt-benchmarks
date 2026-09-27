# Sidekiq worker: started as `sidekiq -r ./worker.rb -c <slots> -q bench`.
# Prints one JSON line per completed job in the shared benchmark shape.
require "sidekiq"

# Log completion from server middleware after the job and the rest of the
# middleware chain return, so it is measured at the same point as BullMQ's
# `completed` event and ntnt's post-persist `job.completed`, not inside
# `perform`. Only Sidekiq's final ack (a single LREM of the in-progress
# entry) runs after this.
class BenchCompletionLog
  include Sidekiq::ServerMiddleware

  def call(_job_instance, job, _queue)
    yield
    ns = Process.clock_gettime(Process::CLOCK_REALTIME, :nanosecond)
    $stderr.write(%({"event":"job.completed","job_id":"#{job["jid"]}","timestamp":"#{ns}"}\n))
  end
end

Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch("REDIS_URL") }
  config.logger.level = Logger::WARN
  config.server_middleware { |chain| chain.add BenchCompletionLog }
end

class BenchJob
  include Sidekiq::Job
  sidekiq_options queue: "bench", retry: false

  def perform(work_ms)
    sleep(work_ms / 1000.0) if work_ms > 0
  end
end
