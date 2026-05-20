class Context:
    def __init__(self, path="."):
        self.path = path
        self.stack = []

    def append(self, item):
        self.stack.append(item)

    def pop(self):
        return self.stack.pop()

    def reset(self, path):
        self.path = path
        self.stack = []

    def current_path(self):
        return f"{self.path}/{'_'.join(self.stack)}"

ctx = Context()