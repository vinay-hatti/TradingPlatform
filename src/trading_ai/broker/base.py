from abc import ABC, abstractmethod


class Broker(ABC):

    @abstractmethod
    def submit_order(self, order):
        pass

    @abstractmethod
    def positions(self):
        pass

    @abstractmethod
    def account(self):
        pass
