from weakref import WeakValueDictionary
from types import MethodType
from typing import Sequence, Callable


class Dispatcher:
    __slots__ = '_event_mapping',

    def __init__(self, events: Sequence[str] = None):
        if events is not None:
            self._event_mapping = {event: WeakValueDictionary() for event in events}

    def add_event(self, *args: str):
        for arg in args:
            self._event_mapping[arg] = WeakValueDictionary()

    def bind(self, event: str, *args: Callable):
        try:
            event_handlers = self._event_mapping[event]
        except KeyError:
            raise ValueError(f'No such event with name {event}.')

        def bind(callback: Callable):
            if not callable(callback):
                raise TypeError('Provided object is not callable.')
            k, v = self._compute_kv(callback)
            event_handlers[k] = v
            return callback

        if args:  # Regular usage
            for arg in args:
                bind(arg)
        else:  # Decorator usage
            return bind

    def unbind(self, event: str, *args: Callable) -> None:
        event_handlers = self._event_mapping[event]
        keys = list(event_handlers.keys())
        for arg in args:
            k = self._compute_kv(arg)[0]
            if k in keys:
                del event_handlers[k]

    def notify(self, event: str, *args, **kwargs) -> None:
        for k, v in self._event_mapping[event].items():
            func_name = k[0]
            (v if func_name is None else getattr(v, func_name))(*args, **kwargs)

    @staticmethod
    def _compute_kv(obj):
        if isinstance(obj, MethodType):
            return (obj.__func__.__name__, id(obj.__self__)), obj.__self__
        else:
            return (None, id(obj)), obj


if __name__ == '__main__':
    class LOL(Dispatcher):
        def __init__(self):
            super().__init__(['lol', 'xd'])

        def run(self):
            self.notify('lol', 'rolf')
            self.notify('xd', 'haha')


    lol = LOL()

    @lol.bind('xd')
    @lol.bind('lol')
    def lol_listener(msg):
        print('function', msg)


    class LolListener:
        def lel(self, msg):
            print('method', msg)

        def __call__(self, msg):
            print('__call__', msg)


    listener = LolListener()

    # listener.lel = lol.bind('lol')(listener.lel)
    # listener = lol.bind('xd')(listener)
    lol.bind('lol', listener.lel)
    lol.bind('xd', listener)

    lol.run()
    print()

    lol.unbind(lol_listener, listener.lel)

    lol.run()
