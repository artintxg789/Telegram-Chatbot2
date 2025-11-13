import os, glob, json, sqlite3
from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required to build the KB.")

client = OpenAI(api_key=OPENAI_API_KEY)
DB = "kb.sqlite"

def read_docs():
    items = []
    # Very simple splitter: each list-item in *.md becomes one chunk
    for path in glob.glob("kb/*.md"):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = [c.strip("- ").strip() for c in text.split("\n- ") if c.strip()]
        for chunk in chunks:
            items.append({"path": path, "text": chunk})
    return items

def ensure_db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY,
            path TEXT,
            text TEXT,
            embedding TEXT
        )
    """)
    con.execute("DELETE FROM docs")
    con.commit()
    con.close()

def embed_text(txt: str):
    out = client.embeddings.create(model="text-embedding-3-small", input=txt)
    return out.data[0].embedding

def build():
    ensure_db()
    docs = read_docs()
    con = sqlite3.connect(DB)
    for d in docs:
        emb = embed_text(d["text"])
        con.execute("INSERT INTO docs (path, text, embedding) VALUES (?, ?, ?)",
                    (d["path"], d["text"], json.dumps(emb)))
    con.commit()
    con.close()
    print(f"Indexed {len(docs)} chunks into {DB}")

if __name__ == "__main__":
    build()
