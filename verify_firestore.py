import json
from google.cloud import firestore

# --- Connect to Firestore ---
db = firestore.Client(database="travel-insurance-faq")

# --- Get the latest document ---
latest_doc_ref = db.collection('context_cache').document('latest')
latest_doc = latest_doc_ref.get()

if not latest_doc.exists:
    print("'latest' document not found in 'context_caches' collection.")
else:
    print("Successfully retrieved 'latest' document. Content:")
    latest_data = latest_doc.to_dict()

    def datetime_handler(x):
        if hasattr(x, 'isoformat'):
            return x.isoformat()
        raise TypeError("Unknown type")

    print(json.dumps(latest_data, indent=4, default=datetime_handler))

    # --- Verify a historical document exists ---
    # We can construct an expected timestamp or query the collection
    print("\nChecking for a corresponding historical document...")
    history_collection_ref = db.collection('context_caches_history').limit(1).order_by("create_time", direction=firestore.Query.DESCENDING)
    history_docs = list(history_collection_ref.stream())

    if not history_docs:
        print("No documents found in 'context_caches_history'.")
    else:
        print(f"Successfully found {len(history_docs)} historical document(s). The most recent one is:")
        history_data = history_docs[0].to_dict()
        print(json.dumps(history_data, indent=4, default=datetime_handler))
