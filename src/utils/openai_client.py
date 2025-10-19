import httpx
from openai import OpenAI
from dotenv import load_dotenv

# ✅ Load environment variables from .env
load_dotenv()

# ✅ Read API key from .env
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env file")

# Initialize client with API key and disable SSL verification (for local dev)
client = OpenAI(
    api_key=api_key,
    http_client=httpx.Client(verify=False)
)

product_file = client.files.create(
    file=open('products.txt', 'rb'),
    purpose='assistants'
)

vector_store = client.vector_stores.create(
    name="bank_products_knowledge",
)

vector_store_file = client.vector_stores.files.create_and_poll(
    file_id=product_file.id,
    vector_store_id=vector_store.id,
)

with open('assistant_prompt.txt', 'r', encoding='utf-8') as f:
    prompt_text = '\n'.join(f.readlines())

assistant = client.beta.assistants.create(
    name="ZamanbankGPTWrapper",
    model="gpt-4o",
    instructions=prompt_text,
    tools=[{'type': 'file_search'}, {'type': 'code_interpreter'}],
    tool_resources={
        'file_search': {
            'vector_store_ids': [vector_store.id]
        }
    }
)
