from openai import OpenAI

client = OpenAI()

def embed_resume(resume: str):
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=resume
    )
    resume_embedding = resp.data[0].embedding
    return resume_embedding

def embed_desc(description: str):
    client = OpenAI()
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=description
    )
    desc_embedding = resp.data[0].embedding
    return desc_embedding