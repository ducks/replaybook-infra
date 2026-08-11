# frozen_string_literal: true

require "pg"

module SiteConfig
  DATABASES = {
    "default" => ENV.fetch("DEFAULT_DATABASE", "discourse_default"),
    "secondary" => ENV.fetch("SECONDARY_DATABASE", "discourse_secondary")
  }.freeze

  module_function

  def database(site)
    DATABASES.fetch(site)
  end

  def connect(site)
    connection = PG.connect(
      host: "127.0.0.1",
      user: "replaybook",
      dbname: database(site)
    )
    return connection unless block_given?

    begin
      yield connection
    ensure
      connection.close
    end
  end
end
