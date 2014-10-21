

class FileSource(object):
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")

    def get_preread_metadata(self, node):
        return {"source": self.path,
                "start_index": self.f.tell()}

    def get_postread_metadata(self, node):
        end = self.f.tell()
        return {"end_index": end,
                "length": end - node._metadata["start_index"]}

    def read(self, n=1):
        data = self.f.read(n)
        if len(data) < n:
            raise EOFError()
        return data

    def tell(self):
        return self.f.tell()

