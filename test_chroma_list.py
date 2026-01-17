import chromadb
import os

path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'chroma_data'))
print('Using path:', path)
client = chromadb.PersistentClient(path=path)
cols = client.list_collections()
print('Collections types:', [type(x) for x in cols])
# Try multiple ways to extract names
names = []
for x in cols:
    name = getattr(x, 'name', None)
    if callable(name):
        try:
            name = name()
        except Exception:
            pass
    if name is None and isinstance(x, dict):
        name = x.get('name')
    names.append(name)
print('Collection names:', names)
print('Raw:', cols)
