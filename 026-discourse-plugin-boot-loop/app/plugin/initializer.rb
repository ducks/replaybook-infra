supported_plugin_api_versions = [1]

unless supported_plugin_api_versions.include?(DiscourseCore::PLUGIN_API_VERSION)
  raise "discourse-presence does not support plugin API #{DiscourseCore::PLUGIN_API_VERSION}"
end

PluginRegistry.register("discourse-presence")
