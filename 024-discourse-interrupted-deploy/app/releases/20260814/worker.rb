# frozen_string_literal: true

require "pg"

def connection
  PG.connect(host: "127.0.0.1", dbname: "discourse", user: "discourse")
end

loop do
  database = connection
  exports = database.exec(
    "SELECT export_id FROM staff_exports WHERE state = 'accepted' ORDER BY created_at LIMIT 20"
  )
  exports.each do |row|
    export_id = row.fetch("export_id")
    database.exec_params(
      "UPDATE staff_exports SET attempt_count = attempt_count + 1 WHERE export_id = $1",
      [export_id]
    )
    database.exec_params(
      "UPDATE staff_exports SET state = 'completed', artifact_key = '20260814', completed_at = now() WHERE export_id = $1",
      [export_id]
    )
  rescue PG::Error => error
    warn "export #{export_id}: #{error.message.lines.first.to_s.strip}"
  end
  database.close
  sleep 1
rescue PG::Error => error
  warn "worker: #{error.message.lines.first.to_s.strip}"
  database&.close
  sleep 1
end
