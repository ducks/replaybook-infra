# frozen_string_literal: true

require "pg"
require "sidekiq"

redis_url = ENV.fetch("REDIS_URL")

Sidekiq.configure_client { |config| config.redis = { url: redis_url } }
Sidekiq.configure_server { |config| config.redis = { url: redis_url } }

class CheckoutConfirmationV2Job
  include Sidekiq::Job

  def perform(job_id, lane)
    worker_name = ENV.fetch("WORKER_NAME")
    raise "job for #{lane} reached #{worker_name}" unless lane == worker_name

    connection = PG.connect(host: "127.0.0.1", dbname: "replaybook", user: "replaybook")
    connection.exec_params(
      "INSERT INTO completed_jobs (job_id, worker_name, release_version) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
      [job_id, worker_name, "20260810"]
    )
  ensure
    connection&.close
  end
end
