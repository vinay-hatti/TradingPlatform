from abc import ABC, abstractmethod


class Repository(ABC):

    @abstractmethod
    def save(self, entity):
        pass

    @abstractmethod
    def get(self, id):
        pass
