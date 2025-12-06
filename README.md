# run this first
python3 -m uvicorn api.main:app --reload

# then run this
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Get current Mumbai temperature from OpenWeatherMap, then POST to Notion API to create a database entry with Name property containing Mumbai Weather + timestamp, and Temperature property containing the actual temperature number",
    "save": true
  }'

