
import json
from google.cloud import firestore

# --- Connect to Firestore ---
db = firestore.Client(database="travel-insurance-faq")

# --- Get the document ---
doc_ref = db.collection('config').document('chatbot_settings')
doc = doc_ref.get()

# --- Print the result ---
if doc.exists:
    print("Successfully retrieved document. Content:")
    data = doc.to_dict()
    # Convert timestamp to string for JSON serialization
    if 'last_updated' in data and hasattr(data['last_updated'], 'isoformat'):
        data['last_updated'] = data['last_updated'].isoformat()
    print(json.dumps(data, indent=4))
else:
    print("Document not found.")
