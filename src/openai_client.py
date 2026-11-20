
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def test_openai_connection():
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY belum tersedia")

    client = OpenAI(
        api_key=api_key,
        timeout=30.0,
        max_retries=1,
    )

    response = client.responses.create(
        model=model,
        instructions=(
            "You are a shipping analytics assistant. "
            "For this test, answer briefly. "
            "Do not invent shipment statistics."
        ),
        input="Explain what on-time delivery rate means in one sentence.",
        max_output_tokens=150,
        store=False,
    )

    print("OpenAI API berhasil terhubung!")
    print("Model:", model)
    print("Response:", response.output_text)


if __name__ == "__main__":
    test_openai_connection()
