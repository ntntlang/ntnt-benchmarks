require 'rails'
require 'action_controller/railtie'
require 'active_record/railtie'

class BenchApp < Rails::Application
  config.load_defaults 7.1
  config.api_only = true
  config.eager_load = true
  config.cache_classes = true
  config.consider_all_requests_local = false
  config.log_level = :warn
  config.secret_key_base = 'benchmark-not-for-production-use-only'
end
