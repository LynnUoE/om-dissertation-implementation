import json
import requests
from query_processor import QueryProcessor

# Initialize the processor
processor = QueryProcessor('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')

# Process a query
query = "machine learning experts in healthcare with focus on medical imaging"
analysis = processor.process_query(query)

# Print the results
print(json.dumps(analysis, indent=2))