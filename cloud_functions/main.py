import functions_framework
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore
from google.genai.types import Content, CreateCachedContentConfig, Part
import os
import datetime
# Load environment variables from .env file
load_dotenv()


PROJECT_ID = os.environ.get("GCP_PROJECT")
LOCATION = os.environ.get("FUNCTION_REGION")
MODEL_NAME = os.environ.get("MODEL_NAME")
DB_NAME = os.environ.get("DB_NAME")

@functions_framework.cloud_event
def update_context_cache(cloud_event):
    """Triggered by a change to a GCS bucket, this function updates the Vertex AI Context Cache."""
    data = cloud_event.data

    bucket = data["bucket"]
    name = data["name"]

    if name != "travel_faq.pdf":
        print(f"Ignoring file {name} as it is not the FAQ PDF.")
        return

    gcs_uri = f"gs://{bucket}/{name}"

    genai_client = genai.Client(project=PROJECT_ID, location=LOCATION)
    firestore_client = firestore.Client(database=DB_NAME)

    # Construct the absolute path to the system instruction file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instruction_path = os.path.join(script_dir, "system_instruction.txt")

    with open(instruction_path, "r") as f:
        system_instruction = f.read()

    contents = [
        Content(
            role="user",
            parts=[
                Part.from_uri(
                    file_uri=gcs_uri,
                    mime_type="application/pdf",
                ),
            ],
        )
    ]

    content_cache = genai_client.caches.create(
        model=MODEL_NAME,
        config=CreateCachedContentConfig(
            contents=contents,
            system_instruction=system_instruction,
            display_name="travel-insurance-faq-cache",
        ),
    )

    print(f"Content cache created: {content_cache.name}")

    doc_ref = firestore_client.collection('config').document('chatbot_settings')
    data = {
        'active_cache_id': content_cache.name,
        'last_updated': datetime.datetime.now(datetime.timezone.utc)
    }
    doc_ref.set(data)

    print(f"Updated Firestore with new cache ID: {content_cache.name}")
