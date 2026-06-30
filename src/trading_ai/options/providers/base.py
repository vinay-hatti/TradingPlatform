from abc import ABC, abstractmethod


class OptionsProvider(ABC):

    @abstractmethod
    def get_chain(self, symbol):
        pass
