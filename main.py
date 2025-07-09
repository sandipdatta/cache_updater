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

    if not name.startswith("travel_faq") or not name.endswith(".pdf"):
        print(f"Ignoring file {name} as it is not the FAQ PDF.")
        return

    gcs_uri = f"gs://{bucket}/{name}"

    genai_client = genai.Client(project=PROJECT_ID, location=LOCATION)
    firestore_client = firestore.Client(database=DB_NAME)

    # 1. Get the ID of the current cache to be replaced.
    latest_doc_ref = firestore_client.collection("context_cache").document("latest")
    doc = latest_doc_ref.get()
    old_cache_id = None
    if doc.exists:
        old_cache_id = doc.to_dict().get("cache_id")

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

    expire_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=365 * 10
    )

    # 2. Create the new cache first.
    try:
        content_cache = genai_client.caches.create(
            model=MODEL_NAME,
            config=CreateCachedContentConfig(
                contents=contents,
                system_instruction=system_instruction,
                display_name="travel-insurance-faq-cache",
                expireTime=expire_time,
            ),
        )
        print(f"Successfully created new content cache: {content_cache.name}")
    except Exception as e:
        print(f"Failed to create new content cache. Aborting update. Error: {e}")
        return  # Exit the function, leaving the old cache active.

    # 3. Update Firestore with the new cache information.
    # --- Prepare the full data object ---
    now = datetime.datetime.now(datetime.timezone.utc)
    usage_metadata = content_cache.usage_metadata
    full_data = {
        "cache_id": content_cache.name,
        "model": content_cache.model,
        "display_name": content_cache.display_name,
        "create_time": content_cache.create_time,
        "update_time": content_cache.update_time,
        "expire_time": content_cache.expire_time,
        "gcs_uri": gcs_uri,
        "system_instruction": system_instruction,
        "usage_metadata": {
            "total_token_count": usage_metadata.total_token_count,
            "text_count": usage_metadata.text_count,
            "image_count": usage_metadata.image_count,
        },
        "last_updated": now,
    }

    # --- Create the historical record ---
    timestamp_id = now.strftime("context_cache_%Y%m%d%H%M%S")
    history_doc_ref = firestore_client.collection("context_caches_history").document(
        timestamp_id
    )
    history_doc_ref.set(full_data)
    print(f"Created historical record: {history_doc_ref.path}")

    # --- Update the 'latest' document with a full copy of the data ---
    latest_doc_ref.set(full_data)
    print(f"Updated 'latest' document with new cache ID: {content_cache.name}")

    # 4. Delete the old cache now that the new one is active.
    if old_cache_id:
        try:
            genai_client.caches.delete(name=old_cache_id)
            print(f"Successfully deleted old cache: {old_cache_id}")
        except Exception as e:
            # Log the error, but don't treat it as a critical failure.
            # The main goal of activating the new cache is already complete.
            print(
                f"Warning: Failed to delete old cache {old_cache_id}. It could need manual cleanup. Error: {e}"
            )
