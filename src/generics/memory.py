from generics.process import ProcessLike


class MemoryLike(ProcessLike):
    """
    A memory is a file (virtual or not) which an agent process can interact with using functions.
    """
    def __init__(self, name, client, model):
        super().__init__(name, client, model)

