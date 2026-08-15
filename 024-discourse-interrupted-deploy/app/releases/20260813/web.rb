# frozen_string_literal: true

require "pg"

class DiscourseExportApp
  def call(environment)
    method = environment.fetch("REQUEST_METHOD")
    path = environment.fetch("PATH_INFO")

    return reply(200, "ok") if method == "GET" && path == "/health"
    return reply(200, "20260813") if method == "GET" && path == "/release"

    if path.start_with?("/exports/")
      suffix = path.delete_prefix("/exports/")
      export_id, detail = suffix.split("/", 2)
      return accept_export(export_id) if method == "POST" && detail.nil?
      return export_attempts(export_id) if method == "GET" && detail == "attempts"
      return export_status(export_id) if method == "GET" && detail.nil?
    end

    reply(404, "not found")
  rescue PG::Error => error
    warn "#{error.class}: #{error.message}"
    reply(503, "database error")
  end

  private

  def connection
    PG.connect(host: "127.0.0.1", dbname: "discourse", user: "discourse")
  end

  def accept_export(export_id)
    with_connection do |database|
      database.exec_params(
        "INSERT INTO staff_exports (export_id, state) VALUES ($1, 'accepted') ON CONFLICT DO NOTHING",
        [export_id]
      )
    end
    reply(202, "accepted")
  end

  def export_status(export_id)
    result = with_connection do |database|
      database.exec_params(
        "SELECT state, artifact_key FROM staff_exports WHERE export_id = $1",
        [export_id]
      )
    end
    return reply(404, "missing") if result.ntuples.zero?
    return reply(409, "pending") unless result[0]["state"] == "completed"

    reply(200, "completed:#{result[0]['artifact_key']}")
  end

  def export_attempts(export_id)
    result = with_connection do |database|
      database.exec_params(
        "SELECT attempt_count FROM staff_exports WHERE export_id = $1",
        [export_id]
      )
    end
    return reply(404, "missing") if result.ntuples.zero?

    reply(200, result[0]["attempt_count"])
  end

  def with_connection
    database = connection
    yield database
  ensure
    database&.close
  end

  def reply(status, body)
    [status, { "content-type" => "text/plain", "content-length" => body.bytesize.to_s }, [body]]
  end
end
