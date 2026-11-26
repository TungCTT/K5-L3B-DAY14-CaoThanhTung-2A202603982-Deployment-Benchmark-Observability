# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns tìm thấy trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong source code (`develop/app.py` dòng 17–18):**
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`
   - `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`
   - Nếu push lên GitHub (đặc biệt repo public), key và mật khẩu DB bị lộ ngay lập tức và lưu vĩnh viễn trong lịch sử Git.
2. **Hardcode cấu hình & bật cứng chế độ debug/reload (`develop/app.py` dòng 21–22, 53):**
   - `DEBUG = True`, `MAX_TOKENS = 500` được gán cứng trong code, không đọc từ biến môi trường; `uvicorn.run(..., reload=True)` bật hot-reload không phù hợp cho production (tốn tài nguyên, dễ crash/restart ngoài ý muốn).
3. **Dùng `print()` thay cho structured logging và in trực tiếp secret ra stdout (`develop/app.py` dòng 33–38, 48):**
   - Dùng `print(f"[DEBUG] ...")` rời rạc, khó parse/tìm kiếm trên hệ thống log tập trung (Loki, Datadog).
   - Nghiêm trọng hơn, dòng 34 (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`) làm rò rỉ thẳng API key vào log.
4. **Không có health check / readiness endpoint (`develop/app.py` dòng 42–43):**
   - Không có `GET /health` hay `GET /ready`. Khi deploy lên cloud hoặc chạy dưới load balancer, nền tảng không biết container còn sống hay đã sẵn sàng nhận traffic để restart hoặc route traffic.
5. **Bind cứng `host="localhost"` và `port=8000` (`develop/app.py` dòng 51–52):**
   - `host="localhost"` chỉ lắng nghe loopback bên trong máy/container, không nhận được kết nối từ bên ngoài container (`0.0.0.0`).
   - `port=8000` cố định không đọc biến `PORT` do các nền tảng cloud (Railway, Render, Cloud Run) cấp động.
6. **Không xử lý graceful shutdown (`develop/app.py`):**
   - Thiếu `lifespan` và xử lý `SIGTERM`. Khi platform dừng hoặc deploy phiên bản mới, process tắt đột ngột và cắt ngang các request đang xử lý.
7. **Nhận input lỏng lẻo qua query parameter & thiếu validation/CORS (`develop/app.py` dòng 30–31):**
   - `def ask_agent(question: str):` nhận `question` qua query string thay vì JSON body có schema validation rõ ràng, đồng thời thiếu cấu hình `CORSMiddleware` cho frontend.

---

### Exercise 1.2: Kết quả chạy bản `develop`

Cài đặt môi trường từ `.venv` (Python 3.12.10) và chạy `01-localhost-vs-production/develop/app.py` (lưu ý bản `develop` nhận `question` qua query parameter, gửi JSON body sẽ bị lỗi `422`):

**Lệnh test & kết quả thực tế:**

1. `curl.exe -sS -i "http://localhost:8000/"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:24:13 GMT
server: uvicorn
content-length: 54
content-type: application/json

{"message":"Hello! Agent is running on my machine :)"}
```

2. `curl.exe -sS -i -X POST "http://localhost:8000/ask?question=Hello"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:24:13 GMT
server: uvicorn
content-length: 95
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

**Quan sát log phía server (`stdout`):**
```text
Starting agent on localhost:8000...
INFO:     127.0.0.1:54605 - "GET / HTTP/1.1" 200 OK
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
INFO:     127.0.0.1:54611 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```
→ App chạy được trên localhost nhưng **không sẵn sàng cho production**: vừa lộ secret `OPENAI_API_KEY` ngay trong log, vừa bind `http://localhost:8000` kèm reloader.

---

### Exercise 1.3: So sánh `develop` vs `production` & đối chiếu dòng code đã sửa

**Kết quả chạy thực tế bản `01-localhost-vs-production/production/app.py`:**

1. `curl.exe -sS -i "http://localhost:8000/health"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:24:16 GMT
server: uvicorn
content-length: 129
content-type: application/json

{"status":"ok","uptime_seconds":0.5,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:24:16.620647+00:00"}
```

2. `curl.exe -sS -i "http://localhost:8000/ready"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:24:16 GMT
server: uvicorn
content-length: 14
content-type: application/json

{"ready":true}
```

3. `curl.exe -sS -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question": "Hello"}'`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:24:16 GMT
server: uvicorn
content-length: 144
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

**Quan sát log phía server:**
```text
WARNING:root:OPENAI_API_KEY not set — using mock LLM
INFO:     Started server process [22592]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```
*(Ghi chú quan sát thực tế: `production/app.py` đã bind `0.0.0.0:8000`, tắt `reload` khi `DEBUG=false`, và `config.py` cảnh báo khi thiếu `OPENAI_API_KEY`. Tuy nhiên vì `from config import settings` gọi `logging.warning(...)` ở dòng 45 trước khi `logging.basicConfig(...)` ở `app.py` dòng 28 chạy, root logger giữ mức mặc định `WARNING` nên các dòng `logger.info(...)` không in ra nếu không dùng handler/formatter riêng — bài học thực tế cho thấy ở Part 6 cần tự gắn `JsonFormatter` lên handler thay vì chỉ dựa vào `logging.basicConfig`.)*

**Bảng so sánh Develop vs Production:**

| Feature | Develop (`basic`) | Production (`advanced`) | Tại sao quan trọng? |
|---|---|---|---|
| **Config** | Hardcode trong code (`DEBUG`, `MAX_TOKENS`, port) | Tập trung trong `config.py` qua `os.getenv(...)` + `Settings.validate()` | Dễ thay đổi cấu hình giữa `dev`/`staging`/`production` mà không cần sửa code; fail-fast nếu thiếu cấu hình bắt buộc (`AGENT_API_KEY` khi `ENVIRONMENT=production`). |
| **Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL` trực tiếp và in ra `print()` | Đọc từ biến môi trường, cung cấp `.env.example` làm mẫu, không log secrets | Tránh rò rỉ thông tin nhạy cảm lên Git/log aggregator và tránh bị lạm dụng/mất tiền API. |
| **Host & Port** | `host="localhost"`, `port=8000`, `reload=True` | `host="0.0.0.0"`, `port` từ `PORT`, `reload=settings.debug` | `0.0.0.0` cho phép nhận traffic từ bên ngoài container; đọc `PORT` để tương thích với Railway/Render/Cloud Run; tắt `reload` để ổn định trong production. |
| **Health & Readiness** | Không có | Có `GET /health` (liveness) và `GET /ready` (readiness, trả 503 nếu chưa sẵn sàng) | Platform dựa vào `/health` để restart container khi treo; load balancer dựa vào `/ready` để chỉ gửi traffic khi app đã khởi tạo xong. |
| **Logging** | `print("[DEBUG] ...")` dạng text tự do | Cấu hình structured JSON log (`{"time":...,"level":...,"msg":...}`), chỉ log metadata (`question_length`, `response_length`) | Dễ thu thập, lọc và tạo cảnh báo trên Datadog/Loki/ELK mà không làm lộ dữ liệu nhạy cảm. |
| **Graceful Shutdown** | Không xử lý, tắt đột ngột | Có `lifespan` (quản lý startup/shutdown, set `is_ready = False`) và đăng ký `signal.SIGTERM` | Khi container nhận `SIGTERM`, hệ thống có thể ngừng nhận traffic mới và hoàn tất request đang chạy trước khi tắt, tránh lỗi 502 cho người dùng. |
| **API Input & CORS** | Query param `question: str`, không có CORS | JSON body kiểm tra rỗng (trả 422), có `CORSMiddleware` đọc `ALLOWED_ORIGINS` | Chuẩn hóa REST API và kiểm soát origin được phép gọi từ trình duyệt. |

**Đối chiếu cụ thể điểm lỗi trong `develop/app.py` đã được sửa ở `production/`:**
- **Hardcode secrets & config:** `develop/app.py` dòng 17–22 (`OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG`, `MAX_TOKENS`) → đã sửa trong `production/config.py` dòng 15–50 (`Settings` đọc từ `os.getenv`, có `validate()` kiểm tra `AGENT_API_KEY` khi `environment == "production"`).
- **Dùng `print()` & lộ secret:** `develop/app.py` dòng 33–38 (`print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`) → đã sửa trong `production/app.py` dòng 28–32 (cấu hình format JSON) và dòng 111–122 (chỉ log `question_length`, `client_ip`, `response_length`).
- **Thiếu health/readiness check:** `develop/app.py` dòng 42–43 (không có endpoint) → đã sửa trong `production/app.py` dòng 135–161 (`GET /health` và `GET /ready`).
- **Bind `localhost` / cứng `port=8000` / bật `reload=True`:** `develop/app.py` dòng 49–54 → đã sửa trong `production/app.py` dòng 194–199 (`host=settings.host`, `port=settings.port`, `reload=settings.debug`).
- **Thiếu graceful shutdown:** `develop/app.py` (không có) → đã sửa trong `production/app.py` dòng 39–68 (`lifespan` context manager) và dòng 180–189 (`signal.signal(signal.SIGTERM, handle_sigterm)`).

---

## Part 2: Docker

### Exercise 2.1: Phân tích `02-docker/develop/Dockerfile`

1. **Base image:** `python:3.11` (dòng 8 — bản phân phối Python đầy đủ trên Debian kèm nhiều công cụ hệ thống, dung lượng lớn; khác với bản `production/Dockerfile` dùng `python:3.11-slim`).
2. **Working directory:** `/app` (`WORKDIR /app`, dòng 11 — mọi lệnh `COPY`, `RUN`, `CMD` sau đó thực thi tương đối trong `/app`).
3. **Tại sao `COPY requirements.txt` (dòng 14) và `RUN pip install` (dòng 17) đứng trước `COPY app.py` (dòng 20)?**
   - Để tận dụng **Docker layer cache**: Docker build từng layer từ trên xuống dưới; khi một layer thay đổi, toàn bộ layer phía sau đều bị rebuild. Vì `requirements.txt` ít thay đổi hơn `app.py`, đặt bước cài dependencies lên trước giúp Docker tái sử dụng cache cho layer `pip install` mỗi khi bạn chỉ sửa source code.
   - *(Lưu ý: `--no-cache-dir` tắt cache tải package của `pip` để image không phình to, không tắt Docker layer cache.)*
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**
   - `CMD` (ví dụ `CMD ["python", "app.py"]` ở dòng 30) cung cấp câu lệnh/tham số mặc định và **dễ dàng bị ghi đè** khi người dùng truyền command mới ở cuối lệnh `docker run <image> <command>`.
   - `ENTRYPOINT` cố định tiến trình chính sẽ chạy trong container; mọi tham số truyền thêm lúc `docker run` được nối vào làm đối số cho `ENTRYPOINT` (muốn đổi hẳn phải dùng cờ `--entrypoint`).

---

### Exercise 2.2: Build và chạy container `my-agent:develop`

Build từ thư mục gốc repo (vì Dockerfile `COPY` theo đường dẫn tính từ gốc repo):
```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --rm --name cp2-dev-agent -p 8000:8000 my-agent:develop
```

*(Lưu ý: `02-docker/develop/app.py` nhận `question` qua query parameter giống Part 1.)*

**Kết quả test thực tế:**

1. `curl.exe -sS -i "http://localhost:8000/health"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:29:13 GMT
server: uvicorn
content-length: 53
content-type: application/json

{"status":"ok","uptime_seconds":0.1,"container":true}
```

2. `curl.exe -sS -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker?"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:29:13 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

---

### Exercise 2.3: Multi-stage build (`02-docker/production/Dockerfile`) & So sánh kích thước

**Phân tích các stage trong `02-docker/production/Dockerfile`:**
- **Stage 1 (`builder`, `FROM python:3.11-slim AS builder`):** Cài trình biên dịch/thư viện build (`gcc`, `libpq-dev`) bằng `apt-get` và cài các Python package vào `/root/.local` qua `pip install --no-cache-dir --user -r requirements.txt`. Stage này **không** được đưa vào image cuối.
- **Stage 2 (`runtime`, `FROM python:3.11-slim AS runtime`):** Tạo user non-root `appuser`, chỉ `COPY --from=builder /root/.local /home/appuser/.local`, copy `main.py` + `utils/mock_llm.py`, thiết lập `PATH=/home/appuser/.local/bin:$PATH` và `PYTHONPATH=/app`, thêm `HEALTHCHECK` gọi `/health`, chuyển sang `USER appuser` và chạy `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2`.
- **Tại sao image nhỏ hơn và bảo mật hơn?**
  1. Image cuối dùng `python:3.11-slim` thay cho `python:3.11` đầy đủ.
  2. Toàn bộ công cụ build (`gcc`, `libpq-dev`, apt cache) nằm lại ở stage `builder`, không đi theo vào image `runtime`.
  3. Container chạy bằng user non-root `appuser`, giảm rủi ro nếu ứng dụng bị khai thác lỗ hổng.

**Kích thước image đo thực tế (`docker images my-agent` & `docker image inspect`):**

```text
IMAGE               ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:advanced   548814c1a76f        240MB         57.4MB
my-agent:develop    29ed17c38c67       1.67GB          426MB
```

- `my-agent:develop`: **1,667,771,754 bytes** (~**1,667.77 MB** / **1.67 GB** hiển thị trên `docker images`)
- `my-agent:advanced`: **239,815,281 bytes** (~**239.82 MB** / **240 MB** hiển thị trên `docker images`)
- **Mức giảm:** `(1,667,771,754 - 239,815,281) / 1,667,771,754 ≈` **85.62%** (nhỏ hơn ~6.95 lần, đạt chuẩn `< 500 MB`).

---

### Exercise 2.4: Docker Compose Stack (`02-docker/production/docker-compose.yml`)

**Sơ đồ kiến trúc:**
```text
┌────────┐      HTTP (:80)      ┌──────────────────────────────┐
│ Client │ ───────────────────► │  nginx (nginx:alpine)        │
└────────┘                      │  • Reverse proxy & LB        │
                                │  • Rate limit: 10r/s (b=20)  │
                                │  • Security headers          │
                                └──────────────┬───────────────┘
                                               │ (network: internal)
                                               ▼
                                ┌──────────────────────────────┐
                                │  agent (my-agent:advanced)   │
                                │  • FastAPI :8000 (internal)  │
                                │  • depends_on healthy        │
                                └──────┬────────────────┬──────┘
                                       │                │
                         REDIS_URL     │                │ QDRANT_URL
                         (redis:6379)  ▼                ▼ (qdrant:6333)
                         ┌──────────────────┐    ┌──────────────────┐
                         │ redis:7-alpine   │    │ qdrant:v1.9.0    │
                         │ • healthcheck    │    │ • healthcheck    │
                         │ • vol:redis_data │    │ • vol:qdrant_data│
                         └──────────────────┘    └──────────────────┘
```

**Các service được khởi động & cơ chế giao tiếp:**
1. **`redis` (`redis:7-alpine`):** Cache/session store ở `redis:6379`, dùng named volume `redis_data` và `healthcheck` (`redis-cli ping`).
2. **`qdrant` (`qdrant/qdrant:v1.9.0`):** Vector database ở `http://qdrant:6333`, dùng named volume `qdrant_data` và `healthcheck` qua TCP port 6333.
3. **`agent` (build từ `02-docker/production/Dockerfile`, `target: runtime`):** Chỉ khởi động sau khi cả `redis` và `qdrant` đều đạt trạng thái `healthy` (`depends_on` + `condition: service_healthy`), không mở port ra host mà chỉ phục vụ trong network `internal`.
4. **`nginx` (`nginx:alpine`):** Reverse proxy nhận traffic ở cổng `80`/`443` trên host, áp dụng security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`, `server_tokens off`) và rate limiting `10r/s` (`burst=20`), rồi forward sang `http://agent_backend` (`agent:8000`) qua DNS nội bộ của Docker network `internal`.

**Output chạy thực tế (`docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml`):**

1. `docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml ps`
```text
NAME                       IMAGE                   COMMAND                  SERVICE   CREATED          STATUS                            PORTS
k5-day14-docker-agent-1    k5-day14-docker-agent   "uvicorn main:app --…"   agent     14 seconds ago   Up 2 seconds (health: starting)   8000/tcp
k5-day14-docker-nginx-1    nginx:alpine            "/docker-entrypoint.…"   nginx     14 seconds ago   Up 1 second                       0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp
k5-day14-docker-qdrant-1   qdrant/qdrant:v1.9.0    "./entrypoint.sh"        qdrant    24 seconds ago   Up 12 seconds (healthy)           6333-6334/tcp
k5-day14-docker-redis-1    redis:7-alpine          "docker-entrypoint.s…"   redis     24 seconds ago   Up 13 seconds (healthy)           6379/tcp
```

2. `curl.exe -sS -i "http://localhost/health"`
```http
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 07:31:20 GMT
Content-Type: application/json
Content-Length: 95
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":0.4,"version":"2.0.0","timestamp":"2026-11-26T07:31:20.087872"}
```

3. `curl.exe -sS -i -X POST "http://localhost/ask" -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'`
```http
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 07:31:20 GMT
Content-Type: application/json
Content-Length: 95
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```
*(Quan sát thêm: các response qua Nginx đều có `Server: nginx` cùng bộ security headers cấu hình trong `nginx.conf`, chứng tỏ request đi qua reverse proxy trước khi tới `agent`.)*

---

## Part 3: Cloud Deployment

### Deploy Agent Part 6 (`06-lab-complete/`)

- **Platform:** Render (Web Service Docker từ `06-lab-complete/` + Cloud Redis)
- **Public URL:** `https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com`
- **Chi tiết & biến môi trường:** xem [DEPLOYMENT.md](DEPLOYMENT.md)
- **Screenshots:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

**Kết quả kiểm tra thực tế endpoint public:**
1. `GET /health` → **`200 OK`**: `{"status":"ok","environment":"production"}`
2. `GET /ready` → **`200 OK`**: `{"status":"ready"}` (đã kết nối thành công tới Cloud Redis)
3. `POST /ask` không có `X-API-Key` → **`401 Unauthorized`**: `{"detail":"Invalid or missing API key"}`
4. `POST /ask` có header `X-API-Key: $AGENT_API_KEY` → **`200 OK`** (kiểm tra với biến `$AGENT_API_KEY` trên terminal và chụp ở `screenshots/test.png`, không lưu key thật vào repo)

---

### Exercise 3.2: So sánh `railway.toml` và `render.yaml`

| Tiêu chí | `railway.toml` | `render.yaml` (Blueprint) |
|---|---|---|
| **Định dạng & phạm vi** | **TOML** — cấu hình gọn cho **1 service** riêng lẻ (`[build]`, `[deploy]`). | **YAML** — Infrastructure as Code (**IaC**) khai báo được **nhiều service** và add-on (web + Redis + disk) trong cùng 1 file. |
| **Build & Runtime** | Dùng `builder = "DOCKERFILE"` (hoặc `"NIXPACKS"` tự nhận diện Python) và `dockerfilePath`; chạy lệnh trong Dockerfile `CMD` hoặc `startCommand`. | Khai báo tường minh `type: web`, `runtime: docker` (hoặc `python`), `region`, `plan` (`free`/`starter`...), `autoDeploy`, `buildCommand`/`startCommand`. |
| **Biến môi trường & Secrets** | Không khai báo secret trong file; đặt qua Railway Dashboard hoặc CLI (`railway variables set ...`). | Hỗ trợ mục `envVars:` trực tiếp trong YAML; secret dùng `generateValue: true` (tự sinh random) hoặc `sync: false` (nhập tay trên dashboard, không lộ vào Git). |
| **Health check & Restart** | `healthcheckPath = "/health"`, `healthcheckTimeout`, `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries`. | `healthCheckPath: /health` trên service web; nền tảng tự quản lý health check & auto-deploy theo branch. |
| **Dịch vụ phụ thuộc (Redis)** | Tạo Redis riêng trên Railway Dashboard/CLI rồi gán biến `REDIS_URL` cho service agent. | Có thể khai báo trực tiếp block `- type: redis` (`plan`, `maxmemoryPolicy`) ngay trong `render.yaml`. |

**Vì sao hai file khác nhau?**  
Railway hướng tới trải nghiệm **CLI-first / deploy nhanh theo từng service** (ưu tiên thao tác nhanh qua `railway up` + `railway variables`), nên `railway.toml` chỉ giữ các tham số build/deploy tối giản. Ngược lại, Render thiết kế `render.yaml` theo hướng **GitOps / Blueprint (IaC)** để mô tả toàn bộ hạ tầng (web service, Redis, env var, plan, region) thành một bản thiết kế đồng bộ từ Git.

---

### Exercise 3.3: Pipeline CI/CD GCP Cloud Run (`cloudbuild.yaml` & `service.yaml`)

- **Trigger & Test (`cloudbuild.yaml` bước `test`):** Khi push lên nhánh `main`, Cloud Build chạy container `python:3.11-slim`, cài dependencies và chạy `pytest tests/ -v` để chặn build nếu test fail.
- **Build & Push Docker image (bước `build` → `push`):** Dùng `gcr.io/cloud-builders/docker` build image với `--cache-from` (`:latest`), gắn 2 tag `:$COMMIT_SHA` và `:latest`, rồi push lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
- **Deploy lên Cloud Run (bước `deploy`):** Chạy `gcloud run deploy` triển khai image `:$COMMIT_SHA` tại region `asia-southeast1` với `--min-instances=1` (tránh cold start), `--max-instances=10`, `512Mi` RAM / `1` CPU, timeout `60s` và inject secret an toàn từ **Secret Manager** (`--set-secrets`).
- **Định nghĩa hạ tầng IaC (`service.yaml`):** File Knative (`serving.knative.dev/v1`) mô tả cấu hình chuẩn của service Cloud Run gồm autoscaling (`minScale: "1"`, `maxScale: "10"`, `containerConcurrency: 80`), tham chiếu secret qua `secretKeyRef`, cùng `livenessProbe` (`/health`) và `startupProbe` (`/ready`).

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)

**Phân tích code:**
1. **API key được kiểm tra ở đâu?**
   - Tại hàm dependency `verify_api_key` (`develop/app.py` dòng 39–54), sử dụng `APIKeyHeader(name="X-API-Key", auto_error=False)` (dòng 36) và so sánh với biến `API_KEY = os.getenv("AGENT_API_KEY", ...)` (dòng 35). Dependency này được gắn vào `POST /ask` thông qua `_key: str = Depends(verify_api_key)` ở dòng 70 (còn `/` và `/health` được giữ public).
2. **Điều gì xảy ra nếu thiếu hoặc sai key?**
   - Thiếu header `X-API-Key`: trả `401 Unauthorized` (`{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}`).
   - Sai key (`api_key != API_KEY`): trả `403 Forbidden` (`{"detail":"Invalid API key."}`). *(Lưu ý: ở Part 6 chuẩn hóa cả thiếu và sai key đều trả `401` để tránh lộ thông tin và thống nhất hợp đồng.)*
3. **Làm sao rotate API key an toàn không downtime?**
   - Cho phép server chấp nhận đồng thời nhiều key hợp lệ trong giai đoạn chuyển tiếp (ví dụ đọc danh sách key từ biến môi trường `AGENT_API_KEYS=old-key,new-key` hoặc Secret Manager) → cập nhật key mới cho toàn bộ client → sau khi không còn traffic dùng key cũ thì xóa key cũ khỏi cấu hình và reload/restart service.

**Kết quả test thực tế (`AGENT_API_KEY=secret-key-123`):**

1. **Không có key → `401 Unauthorized`:**
```http
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 07:33:55 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

2. **Sai key (`X-API-Key: wrong-key`) → `403 Forbidden`:**
```http
HTTP/1.1 403 Forbidden
date: Thu, 26 Nov 2026 07:33:56 GMT
server: uvicorn
content-length: 29
content-type: application/json

{"detail":"Invalid API key."}
```

3. **Đúng key (`X-API-Key: secret-key-123`) → `200 OK`:**
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:33:56 GMT
server: uvicorn
content-length: 122
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

---

### Exercise 4.2: JWT Authentication (`04-api-gateway/production/auth.py` & `app.py`)

**Luồng hoạt động của JWT stateless:**
1. Client gửi `POST /auth/token` kèm `username` / `password` (`student` / `demo123`).
2. `authenticate_user` (`auth.py` dòng 70–75) xác thực thông tin đăng nhập; sai thì trả `401`.
3. `create_token` (`auth.py` dòng 35–43) ký payload gồm `sub` (username), `role`, `iat` và `exp` (+60 phút) bằng thuật toán `HS256` với `JWT_SECRET`.
4. Khi gọi endpoint bảo vệ (`POST /ask`, `GET /me/usage`, `GET /admin/stats`), client đính kèm `Authorization: Bearer <token>`.
5. `verify_token` (`auth.py` dòng 46–67) dùng `HTTPBearer(auto_error=False)` kiểm tra chữ ký và thời hạn mà **không cần truy vấn database**: thiếu hoặc hết hạn trả `401`, token giả/sai chữ ký trả `403`.

**Kết quả test thực tế:**

1. **Gọi `/ask` không có token → `401 Unauthorized`:**
```http
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 07:33:59 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

2. **Lấy token từ `POST /auth/token` (`student` / `demo123`, đã che token):**
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:34:20 GMT
server: uvicorn
content-length: 307
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"access_token":"eyJhbGciOiJIUzI1...<masked>","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."}
```

3. **Dùng Bearer token gọi `POST /ask` (Request #1) → `200 OK`:**
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:34:20 GMT
server: uvicorn
content-length: 187
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Test 1","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

---

### Exercise 4.3: Rate Limiting (`04-api-gateway/production/rate_limiter.py`)

**Trả lời câu hỏi:**
1. **Algorithm nào được dùng?**
   - **Sliding Window** (dạng Sliding Window Log): mỗi `user_id` có một `deque` chứa timestamp các request gần nhất. Khi có request mới, hàm `check()` (`rate_limiter.py` dòng 29–71) xóa hết các timestamp cũ hơn `now - window_seconds` (60 giây), rồi so sánh `len(window) >= max_requests`.
2. **Limit là bao nhiêu requests/minute?**
   - User thường (`role="user"`, tài khoản `student`): **10 requests / 60 giây** (`rate_limiter_user`, dòng 86).
   - Admin (`role="admin"`, tài khoản `teacher`): **100 requests / 60 giây** (`rate_limiter_admin`, dòng 87).
3. **Làm sao bypass/nâng limit cho admin?**
   - Hiện tại `app.py` dòng 141 chọn limiter theo role (`limiter = rate_limiter_admin if role == "admin" else rate_limiter_user`), nâng trần lên 100 req/phút. Nếu muốn bypass hoàn toàn cho admin, có thể thêm nhánh `if role != "admin": limiter.check(username)`, tuy nhiên thực tế vẫn nên giữ một trần cao (100+ req/phút) để tránh vòng lặp lỗi từ phía admin làm sập hệ thống.

**Kết quả test vòng lặp 12 requests liên tiếp với token `student`:**
- Requests `1..10`: `HTTP/1.1 200 OK` (`requests_remaining` giảm từ `9` về `0`)
- Requests `11..12`: `HTTP/1.1 429 Too Many Requests`

**Output `curl -i` đầy đủ tại Request #11 (hit limit → `429`):**
```http
HTTP/1.1 429 Too Many Requests
date: Thu, 26 Nov 2026 07:34:23 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795678524
retry-after: 57
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":57}}
```

---

### Exercise 4.4: Cost Guard (`04-api-gateway/production/cost_guard.py`) & Thiết kế với Redis

**Quan sát `cost_guard.py` bản mẫu và output `/me/usage` sau 10 requests:**
- `cost_guard.py` tính chi phí theo giá token (`PRICE_PER_1K_INPUT_TOKENS = 0.00015`, `PRICE_PER_1K_OUTPUT_TOKENS = 0.0006`), chặn per-user vượt `$1/ngày` bằng **HTTP `402 Payment Required`** (cảnh báo log khi đạt 80%) và chặn global vượt `$10/ngày` bằng **HTTP `503`**.
- Output thực tế từ `GET /me/usage` sau 10 requests thành công:
```http
HTTP/1.1 200 OK
content-type: application/json

{"user_id":"student","date":"2026-11-26","requests":10,"input_tokens":40,"output_tokens":308,"cost_usd":0.000191,"budget_usd":1.0,"budget_remaining_usd":0.999809,"budget_used_pct":0.0}
```

**Thiết kế `check_budget(user_id, estimated_cost)` dùng Redis (budget `$10/tháng`, stateless):**
- Bản mẫu dùng dict `_records` trong RAM nên sẽ mất số liệu khi restart và không đồng bộ giữa nhiều instance. Khi chuyển sang Redis:
  1. Tạo key theo user và tháng hiện tại: `key = f"budget:{user_id}:{datetime.now(timezone.utc).strftime('%Y-%m')}"`.
  2. Đọc chi phí đã tiêu trong tháng bằng `current = float(r.get(key) or 0.0)`. Nếu `current + estimated_cost > 10.0` thì trả về `False` (hoặc raise HTTP `402 Payment Required`).
  3. Nếu còn budget, cộng dồn nguyên tử bằng `r.incrbyfloat(key, estimated_cost)` và đặt `r.expire(key, 32 * 24 * 3600)` (32 ngày) để key tự dọn sau khi sang tháng mới; tháng mới sinh key mới nên budget tự reset về `$0`.

**Vì sao cần cả Rate Limit lẫn Cost Guard?**
- **Rate Limit** bảo vệ **tốc độ/tần suất** request (req/phút), chống spam, brute-force hay DDoS làm quá tải CPU/worker.
- **Cost Guard** bảo vệ **túi tiền (token/USD)**. Một user gọi dưới 10 req/phút nhưng gửi prompt dài 2.000 từ hoặc dùng model đắt vẫn có thể đốt hết ngân sách rất nhanh — điều mà rate limit không chặn được. Hai lớp này bổ trợ nhau để bảo vệ cả hiệu năng lẫn chi phí.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks — Liveness (`/health`) vs Readiness (`/ready`)

**Sự khác nhau giữa Liveness probe và Readiness probe (`05-scaling-reliability/develop/app.py`):**

| Tiêu chí | `GET /health` (Liveness probe) | `GET /ready` (Readiness probe) |
|---|---|---|
| **Câu hỏi kiểm tra** | Process/container còn sống hay đang treo chết? | App đã sẵn sàng nhận traffic thực tế chưa? |
| **Cách xử lý khi fail** | Platform (Docker, Railway, Render, Kubernetes) sẽ **restart container**. | Load balancer **ngừng route traffic mới** vào instance đó (nhưng không restart container oan). |
| **Điều kiện kiểm tra** | Chỉ kiểm tra trạng thái sống cơ bản của process (uptime, memory...); **không** phụ thuộc Redis/DB bên ngoài để tránh restart dây chuyền. | Kiểm tra `_is_ready` (startup xong chưa, có đang shutdown không) và kết nối phụ thuộc (Redis `ping()`); nếu chưa sẵn sàng → trả **`503 Service Unavailable`**. |

**Kết quả test thực tế bản `05-scaling-reliability/develop/app.py`:**

1. `curl.exe -sS -i "http://localhost:8000/health"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:36:57 GMT
server: uvicorn
content-length: 195
content-type: application/json

{"status":"ok","uptime_seconds":0.9,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:36:58.205009+00:00","checks":{"memory":{"status":"ok","note":"psutil not installed"}}}
```

2. `curl.exe -sS -i "http://localhost:8000/ready"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:36:57 GMT
server: uvicorn
content-length: 37
content-type: application/json

{"ready":true,"in_flight_requests":1}
```

3. `curl.exe -sS -i -X POST "http://localhost:8000/ask?question=hello"`
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:36:58 GMT
server: uvicorn
content-length: 95
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

---

### Exercise 5.2: Graceful Shutdown

**Cơ chế trong `05-scaling-reliability/develop/app.py`:**
1. **Theo dõi request đang chạy:** Middleware `track_requests` (dòng 72–81) tăng `_in_flight_requests += 1` khi nhận request và giảm `_in_flight_requests -= 1` trong khối `finally`.
2. **Đón nhận `SIGTERM`:** Khi platform/orchestrator gửi `SIGTERM` (thay vì `SIGKILL` cắt ngang ngay lập tức), hàm `handle_sigterm` (dòng 175–187) ghi log, còn `uvicorn` (chạy với `timeout_graceful_shutdown=30`, dòng 198) tự động kích hoạt nhánh shutdown của `lifespan` (dòng 54–66).
3. **Ngừng nhận mới — hoàn tất request cũ:**
   - Đặt `_is_ready = False` để `/ready` (và `/ask`) trả `503`, báo cho load balancer ngừng gửi thêm traffic mới.
   - Vòng lặp `while _in_flight_requests > 0 and elapsed < 30:` chờ toàn bộ request đang dở chạy xong (tối đa 30 giây), rồi mới đóng kết nối và thoát với exit code `0`.

---

### Exercise 5.3: Stateless Design (RAM vs Redis)

**Vì sao lưu state trong RAM bị hỏng khi scale ngang?**
- Khi chạy 3 instance phía sau Nginx load balancer, mỗi container có vùng nhớ RAM riêng biệt. Nếu lưu `conversation_history = {}` trong RAM:
  - Request 1 vào `Instance 1` → session lưu trong RAM của `Instance 1`.
  - Request 2 của cùng user được Nginx chuyển sang `Instance 2` → `Instance 2` không thấy session đó → mất toàn bộ ngữ cảnh hội thoại (hoặc lỗi 404).
  - Ngoài ra, khi container restart hoặc rolling deploy, toàn bộ dữ liệu trong RAM bị mất sạch.

**Cách `05-scaling-reliability/production/app.py` giải quyết:**
- Chuyển toàn bộ session ra **Redis** dùng chung (`REDIS_URL=redis://redis:6379/0`):
  - `save_session()` (dòng 59–65) lưu JSON vào Redis bằng `_redis.setex(f"session:{session_id}", 3600, serialized)` với TTL 1 giờ.
  - `load_session()` (dòng 68–73) đọc lại từ Redis theo `session_id`.
  - `append_to_history()` (dòng 76–90) cập nhật lịch sử (giữ tối đa 20 messages = 10 turns) và ghi ngược lại Redis.
- Nhờ đó, **mọi instance đều ngang hàng (stateless)** và có thể phục vụ bất kỳ turn nào của bất kỳ `session_id` nào.

---

### Exercise 5.4 & 5.5: Load Balancing với Nginx (`--scale agent=3`) & Kiểm chứng `test_stateless.py`

**Kiến trúc triển khai (`05-scaling-reliability/production/docker-compose.yml`):**
```text
Client ──► Nginx (:8080, round-robin + header X-Served-By)
             ├──► Agent Instance 1 (:8000) ─┐
             ├──► Agent Instance 2 (:8000) ─┼──► Redis (:6379, session:{id})
             └──► Agent Instance 3 (:8000) ─┘
```

**Output thực tế khi chạy `docker compose -p k5-day14-scaling -f 05-scaling-reliability/production/docker-compose.yml up -d --build --scale agent=3`:**

1. `docker compose -p k5-day14-scaling -f 05-scaling-reliability/production/docker-compose.yml ps`:
```text
NAME                       IMAGE                    COMMAND                  SERVICE   CREATED          STATUS                    PORTS
k5-day14-scaling-agent-1   k5-day14-scaling-agent   "python -m uvicorn a…"   agent     25 seconds ago   Up 12 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-2   k5-day14-scaling-agent   "python -m uvicorn a…"   agent     25 seconds ago   Up 12 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-3   k5-day14-scaling-agent   "python -m uvicorn a…"   agent     25 seconds ago   Up 12 seconds (healthy)   8000/tcp
k5-day14-scaling-nginx-1   nginx:alpine             "/docker-entrypoint.…"   nginx     24 seconds ago   Up 11 seconds             0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
k5-day14-scaling-redis-1   redis:7-alpine           "docker-entrypoint.s…"   redis     26 seconds ago   Up 23 seconds (healthy)   6379/tcp
```

2. `curl.exe -sS -i "http://localhost:8080/health"`:
```http
HTTP/1.1 200 OK
Server: nginx/1.31.10
Date: Thu, 26 Nov 2026 07:39:00 GMT
Content-Type: application/json
Content-Length: 109
Connection: keep-alive
X-Served-By: 172.20.0.5:8000

{"status":"ok","instance_id":"instance-eee744","uptime_seconds":9.9,"storage":"redis","redis_connected":true}
```

3. **Kết quả chạy `python test_stateless.py`:**
```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 3688fd0e-1dec-43a0-825a-36a174343d08

Request 1: [instance-9308d8]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-eee744]
  Q: Why do we need containers?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 3: [instance-83cb42]
  Q: What is Kubernetes?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

Request 4: [instance-9308d8]
  Q: How does load balancing work?
  A: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ O...

Request 5: [instance-eee744]
  Q: What is Redis used for?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-9308d8', 'instance-eee744', 'instance-83cb42'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Kubernetes?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...
  [user]: How does load balancing work?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...
  [user]: What is Redis used for?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...

✅ Session history preserved across all instances via Redis!
```

4. **Giải thích & thí nghiệm dừng 1 instance (`docker stop k5-day14-scaling-agent-1`):**
   - Trong `test_stateless.py`, 5 request thuộc cùng `Session ID: 3688fd0e-1dec-43a0-825a-36a174343d08` được Nginx chia round-robin đều qua **cả 3 instance** (`instance-9308d8`, `instance-eee744`, `instance-83cb42`), nhưng `GET /chat/{session_id}/history` vẫn đọc đủ **10 messages** (5 cặp hỏi–đáp) từ Redis.
   - Khi dừng container `k5-day14-scaling-agent-1` rồi gửi tiếp `POST /chat` với cùng `session_id`:
```http
HTTP/1.1 200 OK
Server: nginx/1.31.10
X-Served-By: 172.20.0.3:8000

{"session_id":"3688fd0e-1dec-43a0-825a-36a174343d08","question":"After stopping agent-1, do you still have my session?","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","turn":7,"served_by":"instance-9308d8","storage":"redis"}
```
   - Request vẫn thành công (`200 OK`) trên instance còn sống (`instance-9308d8`) và tiếp tục nối vào session cũ trong Redis (`turn: 7`). *(Quan sát thêm: lệnh `GET /history` kế tiếp với `--max-time 5` bị timeout 5s do `nginx.conf` không đặt `proxy_connect_timeout` ngắn nên khi vòng round-robin rơi trúng IP của `agent-1` vừa dừng, Nginx chờ TCP connect timeout mặc định 60s trước khi `proxy_next_upstream` chuyển sang instance tiếp theo — trong production cần thêm `proxy_connect_timeout 2s;` hoặc cơ chế service discovery động.)*

---

## Part 6: Final Project — Production Readiness Check

Đã hoàn thiện toàn bộ `TODO` trong `06-lab-complete/` (`app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`) và chạy kiểm tra đầy đủ trong WSL2 (`Ubuntu`, `os.name == "posix"`, Docker `29.8.2`):

- Lệnh đã chạy: `cd 06-lab-complete && python3 check_production_ready.py`
- Kích thước Docker image đo thực tế: **297 MB** (`< 500 MB`)
- Graceful shutdown: `SIGTERM` → exit code `0`; `docker stop` → exit code `0`, `0.9s` (`< 10s`)

**Output phần "📋 Checklist Deliverable":**

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI Log

| Thời điểm | Phần | Nội dung đã hỏi / dùng AI | Kết quả nhận được & cách tự kiểm tra lại |
|---|---|---|---|
| 2026-11-26 | Setup & CP1 | Kiểm tra môi trường Docker/WSL2/Python trên Windows; đọc và đối chiếu `01-localhost-vs-production/develop/app.py` với `production/app.py`, `production/config.py`. | Tự chạy kiểm tra `wsl --list -v`, `docker run --rm hello-world`, tạo `.venv` Python 3.12, chạy thực tế cả hai app `develop` và `production` trên cổng 8000, gọi `curl.exe` tới `/`, `/health`, `/ready`, `/ask` và đối chiếu từng dòng code trước khi ghi câu trả lời vào `MISSION_ANSWERS.md`. |
| 2026-11-26 | CP2 | Phân tích `02-docker/develop/Dockerfile`, `02-docker/production/Dockerfile`, `docker-compose.yml`, `nginx.conf` và chạy thử stack. | Tự build `my-agent:develop` và `my-agent:advanced` từ gốc repo, chạy container test `/health` và `/ask`, đo dung lượng thực tế bằng `docker images` và `docker image inspect` (1.67 GB vs 240 MB, giảm 85.62%), chạy Docker Compose stack với `-p k5-day14-docker`, test qua Nginx trên cổng 80 và `down -v` dọn sạch sau khi hoàn tất. |
| 2026-11-26 | CP3 | Đọc và phân tích cơ chế API Key (`04-api-gateway/develop/app.py`), JWT (`auth.py`), Rate Limit (`rate_limiter.py`) và Cost Guard (`cost_guard.py`). | Tự cài `pyjwt`, chạy bản `develop` test các mã 401/403/200; chạy bản `production` lấy JWT của `student`/`demo123`, lặp 12 request ghi nhận 1–10 trả 200 và 11–12 trả 429, kiểm tra `/me/usage` và che token trước khi lưu vào `MISSION_ANSWERS.md`. |
| 2026-11-26 | CP4 | Phân tích `05-scaling-reliability/develop/app.py`, `production/app.py`, `docker-compose.yml`, `nginx.conf` về health/readiness, graceful shutdown và stateless Redis. | Tự chạy bản `develop` kiểm tra `/health`, `/ready`, `/ask`; chạy stack 3 instance với `-p k5-day14-scaling`, chạy `test_stateless.py` xác nhận 5 request chia qua cả 3 instance với 10 messages trong Redis, thử `docker stop` 1 instance và dọn stack bằng `down -v`. |
| 2026-11-26 | CP5 (Part 6) | Thiết kế và cài đặt các module trong `06-lab-complete/` (`config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`). | Cài WSL2 (`Ubuntu` trên `D:\wsl\Ubuntu`), bật tích hợp Docker Desktop, cài `06-lab-complete/requirements.txt` và tự chạy `python3 check_production_ready.py` đạt **`PASS 12/12` (43/43 checks passed)**, image 297 MB, `docker stop` 0.9s với exit code 0; dán output thật vào `MISSION_ANSWERS.md`. |
| 2026-11-26 | CP6 (Part 3) | Đọc và phân tích `railway.toml`, `render.yaml`, `cloudbuild.yaml`, `service.yaml`; hoàn thiện `DEPLOYMENT.md` và kiểm tra URL Render public. | Đối chiếu trực tiếp từng trường trong file gốc (`03-cloud-deployment/` và `06-lab-complete/`) cho Exercise 3.2 & 3.3; deploy agent Part 6 lên Render (`https://k5-l3b-day14-caothanhtung-2a202603982.onrender.com`), tự test `/health` (200), `/ready` (200), `/ask` không key (401) và chạy `check_production_ready.py --static-only --public-url ...`. |
| 2026-11-26 | CP7 (Part 7 Bước 1) | Thêm Histogram `agent_question_length_chars` vào `develop/app.py`, bổ sung 2 entry `KNOWLEDGE_BASE` trong `mock_llm.py` và viết workflow CI `.github/workflows/eval.yml`. | Tự chạy `load_test.py` ở 4 mức concurrency (`1, 10, 50, 100`) và 3 mức `MOCK_SLOW_RATE` (`0, 0.03, 0.1`), chạy `eval/run_eval.py` v1 (4.3%) vs v2 (91.3%) vs v2 sau sửa KB (**23/23 — 100.0%**, 0 regression, exit code 0), xuất đủ 10 file JSON vào `reports/` và điền Mục 1–3 trong `BENCHMARK_REPORT.md` khớp số liệu JSON. |
| 2026-11-26 | CP8 (Part 7 Bước 2) | Chạy full stack Docker Compose (`-p k5-day14-observability`), sửa lỗi thiếu `ENV PYTHONUSERBASE=/home/agent/.local` trong `production/Dockerfile`, phân tích Grafana, Jaeger trace và Prometheus alerts. | Chạy `promtool test rules` (`SUCCESS`), Locust headless 2 phút cho `scale=1` và `scale=3` (`benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`), truy vấn Prometheus API & Jaeger `/api/v3/traces` + log JSON khớp `trace_id`, kích hoạt đồng thời 3 alert firing (`AgentInstanceDown` +45s, `AgentHighErrorRate` +107s, `AgentHighLatencyP95` +147s), chụp đủ 4 ảnh Part 7, hoàn thiện Mục 4–6 của `BENCHMARK_REPORT.md` và chạy `docker compose down -v` dọn sạch. |
