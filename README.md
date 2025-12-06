# run this first
python3 -m uvicorn api.main:app --reload

# then run this
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Get Mumbai weather temperature",
    "save": true
  }'
