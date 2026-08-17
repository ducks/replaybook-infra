require "json"
require "rack"
require_relative "boot"

class DiscourseApplication
  def call(env)
    request = Rack::Request.new(env)

    case [request.request_method, request.path_info]
    when ["GET", "/health"]
      text(200, "ok")
    when ["GET", "/core/release"]
      text(200, ENV.fetch("DISCOURSE_RELEASE"))
    when ["GET", "/core/plugin-api"]
      text(200, DiscourseCore::PLUGIN_API_VERSION.to_s)
    when ["GET", "/plugin/status"]
      plugin_status
    else
      route_resource(request)
    end
  rescue PG::Error => error
    warn error.full_message
    text(500, "database-error")
  end

  private

  def route_resource(request)
    if request.post? && (match = request.path_info.match(%r{\A/topics/([^/]+)\z}))
      return accept_topic(match[1])
    end

    if request.get? && (match = request.path_info.match(%r{\A/topics/([^/]+)\z}))
      return state_for("topics", match[1], "published")
    end

    if request.get? && (match = request.path_info.match(%r{\A/uploads/([^/]+)\z}))
      return state_for("uploads", match[1], "preserved")
    end

    if request.get? && (match = request.path_info.match(%r{\A/plugin-data/([^/]+)\z}))
      return state_for("plugin_topic_data", match[1], "preserved")
    end

    if request.get? && (match = request.path_info.match(%r{\A/jobs/([^/]+)\z}))
      return job_state(match[1])
    end

    text(404, "not-found")
  end

  def accept_topic(identifier)
    connection = database
    trigger = false

    connection.transaction do |db|
      db.exec_params(
        "INSERT INTO topics (topic_id, state) VALUES ($1, 'published') ON CONFLICT DO NOTHING",
        [identifier]
      )
      db.exec_params(
        "INSERT INTO uploads (upload_id, topic_id, state) VALUES ($1, $1, 'preserved') ON CONFLICT DO NOTHING",
        [identifier]
      )
      db.exec_params(
        "INSERT INTO plugin_topic_data (topic_id, state) VALUES ($1, 'preserved') ON CONFLICT DO NOTHING",
        [identifier]
      )
      db.exec_params(
        "INSERT INTO background_jobs (job_id, state, attempt_count) VALUES ($1, 'pending', 0) ON CONFLICT DO NOTHING",
        [identifier]
      )

      state = db.exec("SELECT incident_triggered FROM runtime_state WHERE singleton = true FOR UPDATE").first
      count = db.exec("SELECT count(*) AS count FROM topics").first.fetch("count").to_i
      if state.fetch("incident_triggered") == "f" && count >= 3
        db.exec("UPDATE runtime_state SET incident_triggered = true, processing_enabled = true WHERE singleton = true")
        trigger = true
      end
    end

    activate_incompatible_release if trigger
    text(202, "accepted")
  ensure
    connection&.close
  end

  def activate_incompatible_release
    runtime = ENV.fetch("DISCOURSE_RUNTIME_FILE")
    contents = File.read(runtime).sub(
      /^DISCOURSE_PLUGIN_API_VERSION=.*$/,
      "DISCOURSE_PLUGIN_API_VERSION=2"
    )
    File.write(runtime, contents)

    Thread.new do
      sleep 0.5
      worker_pid_file = "/run/discourse-sidekiq/worker.pid"
      Process.kill("TERM", Integer(File.read(worker_pid_file))) if File.exist?(worker_pid_file)
      Process.kill("TERM", Process.pid)
    rescue Errno::ESRCH
      Process.kill("TERM", Process.pid)
    end
  end

  def plugin_status
    connection = database
    enabled = connection.exec("SELECT value FROM plugin_settings WHERE name = 'discourse-presence-enabled'").first&.fetch("value")
    registered = PluginRegistry.plugins&.include?("discourse-presence")
    if enabled == "true" && registered
      text(200, "enabled:discourse-presence:api#{DiscourseCore::PLUGIN_API_VERSION}")
    else
      text(503, "plugin-disabled")
    end
  ensure
    connection&.close
  end

  def state_for(table, identifier, expected)
    connection = database
    row = connection.exec_params("SELECT state FROM #{table} WHERE #{table == 'uploads' ? 'upload_id' : 'topic_id'} = $1", [identifier]).first
    row && row.fetch("state") == expected ? text(200, expected) : text(404, "missing")
  ensure
    connection&.close
  end

  def job_state(identifier)
    connection = database
    row = connection.exec_params(
      "SELECT state, attempt_count FROM background_jobs WHERE job_id = $1",
      [identifier]
    ).first
    return text(404, "missing") unless row

    case row.fetch("state")
    when "pending"
      text(409, "pending")
    when "completed"
      text(200, "completed:#{row.fetch('attempt_count')}")
    else
      text(500, "invalid-state")
    end
  ensure
    connection&.close
  end

  def text(status, body)
    [status, { "content-type" => "text/plain", "content-length" => body.bytesize.to_s }, [body]]
  end
end
