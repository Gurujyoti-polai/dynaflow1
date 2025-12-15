# run this first
python3 -m uvicorn api.main:app --reload

# then run this
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Get the weather for New York, add it to my Notion database, and create a GitHub issue in Gurujyoti-polai/dynaflow1 with the weather report"
  }'


