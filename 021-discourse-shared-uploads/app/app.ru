# frozen_string_literal: true

require "fileutils"

class DiscourseUploadsApp
  ID_PATTERN = /\A[a-zA-Z0-9_-]+\z/

  def call(env)
    method = env.fetch("REQUEST_METHOD")
    path = env.fetch("PATH_INFO")

    return text(200, "ok") if method == "GET" && path == "/health"

    if path.start_with?("/uploads/")
      upload_id = path.delete_prefix("/uploads/")
      return text(400, "invalid") unless ID_PATTERN.match?(upload_id)

      upload_path = File.join(upload_root, upload_id)
      if method == "POST"
        FileUtils.mkdir_p(upload_root)
        File.write(upload_path, "upload\n")
        return text(201, "stored")
      end
      if method == "GET"
        present = File.file?(upload_path)
        return text(present ? 200 : 404, present ? "present" : "missing")
      end
    end

    text(404, "not found")
  end

  private

  def upload_root
    ENV.fetch("UPLOAD_ROOT")
  end

  def text(status, body)
    [status, { "content-type" => "text/plain", "content-length" => body.bytesize.to_s }, [body]]
  end
end

run DiscourseUploadsApp.new
