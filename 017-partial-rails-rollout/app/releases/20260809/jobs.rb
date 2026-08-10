# frozen_string_literal: true

require "pg"
require "sidekiq"

redis_url = ENV.fetch("REDIS_URL")

Sidekiq.configure_client { |config| config.redis = { url: redis_url } }
Sidekiq.configure_server { |config| config.redis = { url: redis_url } }

class CheckoutConfirmationJob
  include Sidekiq::Job

  def perform(job_id)
    connection = PG.connect(host: "127.0.0.1", dbname: "replaybook", user: "replaybook")
    connection.exec_params(
      "INSERT INTO completed_jobs (job_id, worker_name, release_version) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
      [job_id, ENV.fetch("WORKER_NAME"), "20260809"]
    )
  ensure
    connection&.close
  end
end
