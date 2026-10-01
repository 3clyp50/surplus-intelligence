from helpers.extension import Extension
from usr.plugins.surplus_intelligence.helpers.routing import prepare_call


class SurplusRouting(Extension):
    def execute(self, data, **kwargs):
        prepare_call(data)
