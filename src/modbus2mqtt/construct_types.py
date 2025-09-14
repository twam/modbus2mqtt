from construct import Adapter


class Factor(Adapter):
    def __init__(self, factor: float, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.factor = factor

    def _decode(self, obj, context, path):
        return obj * self.factor

    def _encode(self, obj, context, path):
        return obj / self.factor