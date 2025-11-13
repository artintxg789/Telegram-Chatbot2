import os, json, math, sqlite3
from openai import OpenAI

DB = "kb.sqlite"
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _norm(a):  return math.sqrt(sum(x*x for x in a)) + 1e-9
def _cos(a,b): return _dot(a,b) / (_norm(a) * _norm(b))

def _embed(q: str):
    e = client.embeddings.create(model="text-embedding-3-small", input=q)
    return e.data[0].embedding

def search(query: str, k: int = 5):
    qv = _embed(query)
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT path, text, embedding FROM docs").fetchall()
    con.close()
    scored = []
    for path, text, emb_json in rows:
        v = json.loads(emb_json)
        scored.append((_cos(qv, v), path, text))
    scored.sort(reverse=True)
    return [t for _,_,t in scored[:k]]
