# frozen_string_literal: true

require "rack"
require_relative "site_config"

class MultisiteApp
  ID_PATTERN = /\A[a-zA-Z0-9_-]+\z/
  MIGRATION_VERSION = "202608110001"

  def call(env)
    request = Rack::Request.new(env)
    return text(200, "ok") if request.get? && request.path == "/health"

    match = request.path.match(%r{\A/sites/([^/]+)/(identity|migration)\z})
    return site_metadata(request, match[1], match[2]) if match

    match = request.path.match(%r{\A/sites/([^/]+)/jobs/([^/]+)(/attempts)?\z})
    return job(request, match[1], match[2], !match[3].nil?) if match

    text(404, "not found")
  rescue KeyError
    text(404, "unknown site")
  rescue PG::Error => error
    warn(error.message)
    text(503, "database error")
  end

  private

  def site_metadata(request, site, kind)
    return text(405, "method not allowed") unless request.get?

    SiteConfig.connect(site) do |connection|
      if kind == "identity"
        identity = connection.exec("SELECT identity FROM site_identity LIMIT 1").getvalue(0, 0)
        return text(200, identity)
      end

      column_present = connection.exec_params(<<~SQL, ["delivery_state"]).getvalue(0, 0) == "t"
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.columns
          WHERE table_schema = 'public'
            AND table_name = 'moderation_jobs'
            AND column_name = $1
        )
      SQL
      migration_recorded = connection.exec_params(
        "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = $1)",
        [MIGRATION_VERSION]
      ).getvalue(0, 0) == "t"
      return text(column_present && migration_recorded ? 200 : 404,
                  column_present && migration_recorded ? "applied" : "missing")
    end
  end

  def job(request, site, job_id, attempts)
    return text(400, "invalid") unless ID_PATTERN.match?(job_id)

    SiteConfig.connect(site) do |connection|
      if attempts
        return text(405, "method not allowed") unless request.get?

        result = connection.exec_params(
          "SELECT attempt_count FROM job_attempts WHERE job_id = $1",
          [job_id]
        )
        return text(result.ntuples == 1 ? 200 : 404,
                    result.ntuples == 1 ? result.getvalue(0, 0) : "missing")
      end

      if request.post?
        connection.exec_params(<<~SQL, [job_id])
          INSERT INTO moderation_jobs (job_id)
          VALUES ($1)
          ON CONFLICT (job_id) DO NOTHING
        SQL
        return text(202, "queued")
      end

      return text(405, "method not allowed") unless request.get?

      result = connection.exec_params(<<~SQL, [job_id])
        SELECT completed_at, delivery_state
        FROM moderation_jobs
        WHERE job_id = $1
      SQL
      completed = result.ntuples == 1 &&
                  !result.getvalue(0, 0).nil? &&
                  result.getvalue(0, 1) == "completed"
      text(completed ? 200 : 404, completed ? "completed" : "pending")
    rescue PG::UndefinedColumn
      text(404, "pending")
    end
  end

  def text(status, body)
    [status, {
      "content-type" => "text/plain",
      "content-length" => body.bytesize.to_s
    }, [body]]
  end
end
