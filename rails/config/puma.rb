workers ENV.fetch('WEB_CONCURRENCY', 4).to_i
threads_count = ENV.fetch('RAILS_MAX_THREADS', 5).to_i
threads threads_count, threads_count
bind "tcp://127.0.0.1:#{ENV.fetch('PORT', 3107)}"
environment 'production'
preload_app!
