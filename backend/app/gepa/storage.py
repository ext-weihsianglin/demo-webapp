"""Local durable manifests and ordered events; no serialized executable state."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from app.prompt_registry import atomic_json
from app.gepa.datasets import root

_locks={}
_lock_guard=threading.Lock()


def safe_id(identity):
    if identity in ('.','..') or not re.fullmatch(r'[a-zA-Z0-9._-]+',identity):
        raise ValueError('Invalid artifact ID')
    return identity


class RunStore:
    def __init__(self, identity, directory=None):
        self.path=Path(directory or root()/'runs')/safe_id(identity)
        with _lock_guard:
            self.lock=_locks.setdefault(str(self.path.resolve()),threading.RLock())

    def write(self, name, value):
        with self.lock:
            atomic_json(self.path/(safe_id(name)+'.json'),value)

    def read(self, name):
        with self.lock:
            return json.loads((self.path/(safe_id(name)+'.json')).read_text())

    def event(self, phase, **data):
        with self.lock:
            events=self.events()
            value={'event_id':len(events)+1,'time':datetime.now(timezone.utc).isoformat(),'phase':phase,**data}
            self.path.mkdir(parents=True,exist_ok=True)
            with (self.path/'events.jsonl').open('a') as stream:
                stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
                stream.flush()
            return value

    def events(self, after=0):
        with self.lock:
            path=self.path/'events.jsonl'
            output=[]
            if path.exists():
                for line in path.read_text().splitlines():
                    try:
                        value=json.loads(line)
                        if value['event_id']>after:
                            output.append(value)
                    except ValueError:
                        # An interrupted final append cannot erase previous events.
                        continue
            return output

    def export(self):
        with self.lock:
            return {'summary':self.read('summary'),'manifest':self.read('manifest'),
                    'events':self.events(),'artifacts':{p.stem:json.loads(p.read_text())
                    for p in self.path.glob('*.json') if p.stem not in ('manifest','summary')}}
