from trading_ai.options.providers.base import OptionsProvider


class LiveOptionsProvider(OptionsProvider):

    def get_chain(self, symbol):
        raise NotImplementedError
