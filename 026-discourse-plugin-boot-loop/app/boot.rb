require "pg"

module DiscourseCore
  PLUGIN_API_VERSION = Integer(ENV.fetch("DISCOURSE_PLUGIN_API_VERSION"))
end

module PluginRegistry
  class << self
    attr_reader :plugins

    def register(name)
      @plugins ||= []
      @plugins << name
    end
  end
end

load ENV.fetch("DISCOURSE_PLUGIN_INITIALIZER")

def database
  PG.connect(
    host: "127.0.0.1",
    dbname: "discourse",
    user: "discourse"
  )
end
