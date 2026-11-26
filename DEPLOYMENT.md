# Deployment Information

## Public URL
https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com

## Platform
Render (Web Service Docker từ thư mục `06-lab-complete/` + Cloud Redis)

## Test Commands

### Health Check
```bash
curl https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com/health
# Expected: {"status":"ok","environment":"production"}
```

### Readiness Check
```bash
curl https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com/ready
# Expected: {"status":"ready"}
```

### API Test (Authentication Required)
```bash
# Không có API key -> 401
curl -i -X POST https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Có API key -> 200
curl -i -X POST https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

### 4 lệnh tự kiểm CP6
```bash
BASE="https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

## Environment Variables Set on Platform
- `PORT` (Render cấp tự động, Dockerfile lắng nghe qua `${PORT:-8000}`)
- `ENVIRONMENT` (`production`)
- `REDIS_URL` (trỏ tới Cloud Redis)
- `AGENT_API_KEY` (khai báo trên Render Dashboard, không ghi trong code)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
