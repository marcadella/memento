from abc import ABC, abstractmethod


class MemoryLike(ABC):
    """
    A memory is a some kind of storage which an agent can use to store and retrieve data.
    """
    def __init__(self):
        super().__init__()
        self._initialize()

    def _initialize(self):
        """
        Initialize the storage (optional)
        """
        pass

    @abstractmethod
    def get(self, query=None) -> list:
        """
        Given a query, retrieve some data.

        :param query: Some kind of query that the memory implementation is able to process.
        :return: List of matching data retrieved from storage (most commonly strings).
        """
        pass

    @abstractmethod
    def put(self, data, metadata=None):
        """
        Store some data in the storage along with some optional metadata.
        :param data: data to store (most commonly a string)
        :param metadata: (most commonly a dict)
        """
        pass


class MemoryWithEmbedding(MemoryLike):
    """
    A type of memory relying on the use of an embedding model.
    """

    def __init__(self, embedding_model):
        super().__init__()
        self.embedding_model = embedding_model

    @abstractmethod
    def embedding(self):
        pass #todo