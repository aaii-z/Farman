import os
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
from google import genai
from config.settings import settings

client = genai.Client(api_key=settings.llm_api_key)
try:
    response = client.models.generate_content(
        model=settings.llm_model,
        contents='hello'
    )
    print("Success:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
