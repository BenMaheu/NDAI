import openai
from app.config import Config


def call_llm(prompt: str, model="gpt-4o-mini", temperature=0.3) -> str:
    """Wrapper simple pour OpenAI complet."""
    client = openai.Client(api_key=Config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a legal assistant specialized in NDA analysis."},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature
    )
    return response.choices[0].message.content.strip()
