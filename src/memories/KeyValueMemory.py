from generics.memory import MemoryLike
from processes.KeyValueProcess import KeyValueProcess


class KeyValueMemory(MemoryLike):
    """
    A key-value memory using a process to decide which information is important to store and what key to use to store data.
    """
    def __init__(self, name, client, model):
        super().__init__()
        self.kv_store = {}
        self.store_process = KeyValueProcess(f"{name}.kv_mem", client, model, self.store_key_value_pair)

    def store_key_value_pair(self, key, value):
        """
        Stores a key-value pair
        :param key:
        :param value:
        """
        self.kv_store[key] = value
        print(f"***** Memorizing({key}: {value})\n")

    def read_all(self):
        """
        Read all key-value pairs stored in memory.
        :return: Markdown format
        """
        memorized_items = [f"- {k}: {v}" for k, v in self.kv_store.items()]
        return "\n".join(memorized_items)

    def get(self, key=None) -> list:
        res = self.kv_store.get(key)
        return list(res) if res else []

    def put(self, data: str, metadata=None):
        self.store_process.apply(data)
