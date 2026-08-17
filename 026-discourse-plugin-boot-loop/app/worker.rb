require_relative "boot"

File.write("/run/discourse-sidekiq/worker.pid", Process.pid.to_s)

loop do
  connection = database
  connection.transaction do |db|
    enabled = db.exec("SELECT processing_enabled FROM runtime_state WHERE singleton = true").first.fetch("processing_enabled")
    next unless enabled == "t"

    job = db.exec(<<~SQL).first
      SELECT job_id
      FROM background_jobs
      WHERE state = 'pending'
      ORDER BY created_at
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    SQL
    if job
      db.exec_params(
        "UPDATE background_jobs SET state = 'completed', attempt_count = attempt_count + 1 WHERE job_id = $1",
        [job.fetch("job_id")]
      )
    end
  end
  connection.close
  sleep 0.1
rescue PG::Error => error
  warn error.full_message
  connection&.close
  sleep 1
end
