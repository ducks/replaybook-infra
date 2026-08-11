# frozen_string_literal: true

require_relative "site_config"

running = true
Signal.trap("TERM") { running = false }
Signal.trap("INT") { running = false }

while running
  SiteConfig::DATABASES.each_key do |site|
    SiteConfig.connect(site) do |connection|
      jobs = connection.exec(<<~SQL)
        SELECT job_id
        FROM moderation_jobs
        WHERE completed_at IS NULL
        ORDER BY job_id
      SQL
      jobs.each do |row|
        job_id = row.fetch("job_id")
        connection.exec_params(<<~SQL, [job_id])
          INSERT INTO job_attempts (job_id, attempt_count)
          VALUES ($1, 1)
          ON CONFLICT (job_id)
          DO UPDATE SET attempt_count = job_attempts.attempt_count + 1
        SQL
        begin
          connection.exec_params(<<~SQL, [job_id])
            UPDATE moderation_jobs
            SET delivery_state = 'completed', completed_at = now()
            WHERE job_id = $1
          SQL
        rescue PG::UndefinedColumn => error
          warn("#{site}: #{error.message.lines.first.strip}")
        end
      end
    end
  rescue PG::Error => error
    warn("#{site}: #{error.message.lines.first.strip}")
  end

  sleep 0.25
end
