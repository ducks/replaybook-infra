# frozen_string_literal: true

require "pg"
require "socket"
require_relative "jobs"

def response(socket, status, body)
  reasons = { 200 => "OK", 202 => "Accepted", 404 => "Not Found" }
  socket.write(
    "HTTP/1.1 #{status} #{reasons.fetch(status)}\r\n" \
    "Content-Type: text/plain\r\n" \
    "Content-Length: #{body.bytesize}\r\n" \
    "Connection: close\r\n\r\n#{body}"
  )
end

def job_state(job_id)
  connection = PG.connect(host: "127.0.0.1", dbname: "replaybook", user: "replaybook")
  result = connection.exec_params(
    "SELECT worker_name, release_version FROM completed_jobs WHERE job_id = $1",
    [job_id]
  )
  return "pending" if result.ntuples.zero?

  "completed:#{result[0]['worker_name']}:#{result[0]['release_version']}"
ensure
  connection&.close
end

server = TCPServer.new("127.0.0.1", 3000)

loop do
  socket = server.accept
  method, path = socket.gets.to_s.split(" ", 3)
  while (line = socket.gets)
    break if line == "\r\n"
  end

  if method == "GET" && path == "/health"
    response(socket, 200, "ok")
  elsif method == "POST" && path&.start_with?("/jobs/")
    job_id, lane = path.delete_prefix("/jobs/").split("/", 2)
    if %w[standard express].include?(lane)
      CheckoutConfirmationV2Job.set(queue: lane).perform_async(job_id, lane)
      response(socket, 202, "queued")
    else
      response(socket, 404, "not found")
    end
  elsif method == "GET" && path&.start_with?("/jobs/")
    state = job_state(path.delete_prefix("/jobs/"))
    response(socket, state == "pending" ? 404 : 200, state)
  else
    response(socket, 404, "not found")
  end
rescue StandardError => error
  warn "#{error.class}: #{error.message}"
  response(socket, 404, "error") if socket
ensure
  socket&.close
end
