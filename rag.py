import os
from openai import OpenAI
from retriever import search

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

RAG_SYSTEM = (
  "You are the official gaming support bot. "
  "Answer ONLY using the provided context. "
  "If the answer is not in context, say you don’t have that information and offer to escalate. "
  "Never invent probabilities or promises. Include eligibility, wagering, regions, and dates when relevant."
)

def answer_with_kb(user_lang: str, user_text: str) -> str:
    context = "\n\n".join(search(user_text, k=6))
    messages = [
        {"role": "system", "content": RAG_SYSTEM},
        {"role": "system", "content": f"User language code: {user_lang}. Reply strictly in this language."},
        {"role": "system", "content": f"Context:\n{context}"},
        {"role": "user", "content": user_text},
    ]
    resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.1)
    return resp.choices[0].message.content.strip()
