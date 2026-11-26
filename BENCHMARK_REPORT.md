# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Cao Thanh Tùng — 2A202603982
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11 + WSL2 Ubuntu (Python 3.11.18) + Docker Desktop 29.8.2

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Agent v2 bình thường có retrieval (~20ms) + LLM (~120–180ms) nên p95 ổn định quanh ~220–280ms; ngưỡng 500ms đủ dung sai cho dao động nhẹ (jitter) nhưng phát hiện sớm khi hệ thống bão hòa hoặc tỷ lệ slow request tăng. |
| Error rate `/ask` | < 2 % | Mock LLM có lỗi upstream ngẫu nhiên mặc định ~1% (`MOCK_ERROR_RATE=0.01`); đặt ngưỡng 2% cho phép lỗi upstream nhỏ không gây báo động giả, nhưng bắt được lỗi tăng bất thường. |
| Accuracy trên golden dataset | ≥ 85 % | Đảm bảo chất lượng trả lời đạt chuẩn RAG trên tập 23 câu hỏi golden dataset trước khi cho merge/deploy (và yêu cầu 0 câu bị regression so với baseline). |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.13 | 190.5 | 220.9 | 1708.7 | 1.67% | ✅ PASS |
| 10 | 42.1 | 186.9 | 219.1 | 1694.7 | 1.00% | ✅ PASS |
| 50 | 106.44 | 201.4 | 276.2 | 1675.6 | 2.33% | ❌ FAIL |
| 100 | 55.69 | 485.9 | 3797.9 | 4434.1 | 1.00% | ❌ FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không tăng tuyến tính ở mức tải cao:
- Từ `concurrency=1` lên `10`, RPS tăng gần tuyến tính (~10.2×: từ `4.13` lên `42.1 req/s`) trong khi `p95` giữ nguyên quanh `220 ms`, vì agent dùng async I/O (`asyncio.sleep`) nên 1 worker xử lý song song tốt khi chờ I/O.
- Lên `concurrency=50`, RPS đạt đỉnh `106.44 req/s` (`p95` tăng lên `276.2 ms`, nhưng `error_rate = 2.33% > 2.0%` nên FAIL SLO).
- Tới `concurrency=100`, RPS **tụt mạnh xuống `55.69 req/s`** còn `p50` tăng lên `485.9 ms` và `p95` vọt lên `3797.9 ms` (FAIL SLO): một tiến trình uvicorn đơn trên event loop / socket queue bị bão hòa khi phục vụ 100 kết nối đồng thời, các request phải xếp hàng chờ xử lý nên vừa tăng mạnh latency vừa giảm thông lượng.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 190.1 | 221.7 | 229.3 |
| 0.03 (mặc định) | 261.7 | 235.8 | 1701.5 |
| 0.1 | 336.4 | 1697.6 | 1712.6 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **`p99` (và `p95` khi tỷ lệ chậm lên 10%)** nhạy nhất với các request chậm bất thường: khi `MOCK_SLOW_RATE` tăng từ `0` lên `0.03`, `avg` chỉ tăng thêm `+71.6 ms` (`190.1 → 261.7 ms`, trông vẫn bình thường), nhưng **`p99` nhảy vọt hơn 7.4 lần (`229.3 → 1701.5 ms`)**. Khi `MOCK_SLOW_RATE = 0.1`, `avg` vẫn dưới ngưỡng 500 ms (`336.4 ms`), trong khi **`p95` vọt lên `1697.6 ms`** (vi phạm SLO).
- Vì thế SLO **không được đặt theo `average`**: giá trị trung bình bị các request nhanh (90–97% tổng số) kéo xuống và che giấu trải nghiệm tệ ở đuôi phân phối (*tail latency*), nơi nhiều người dùng thực tế phải chờ gần 2 giây.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.5 | 109.1 | 113.7 |
| Tổng cost (USD) | $0.000409 | $0.000762 | $0.00079 |
| Cost / câu đúng (USD) | $0.00040935 | $0.00003627 | $0.00003436 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt"], "API key là chuỗi bí mật cố định, không tự hết hạn. JWT là token có chữ ký số, chứa thông tin user và thời điểm hết hạn; server xác minh chữ ký mà không cần tra database.")` vào cuối `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`). |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa", "kubernetes", "autoscal"], "Kubernetes HPA (Horizontal Pod Autoscaler) scale số pod dựa trên CPU, memory hoặc custom metrics như RPS hay độ dài hàng đợi.")` vào cuối `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`). |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- Agent `v2` có thêm bước retrieval nên `Avg tokens / câu` tăng gần gấp đôi (`57.5 → 109.1` rồi `113.7`), kéo `Tổng cost` của 23 câu từ `$0.000409` lên `$0.00079` và `Latency p95` tăng thêm ~30 ms (`187.9 → 220.6 ms` ở lần đo đầu).
- Đổi lại, `Accuracy` nhảy vọt từ **`4.3% (1/23)` lên `100.0% (23/23)`**, giúp **`Cost / câu đúng` giảm hơn 11.9 lần** (từ `$0.00040935` xuống `$0.00003436`). Đây là đánh đổi hoàn toàn xứng đáng cho RAG trong production.
- **Quality gate trong CI ([.github/workflows/eval.yml](.github/workflows/eval.yml)):** `run_eval.py` trả về `exit code 1` nếu `accuracy < --min-accuracy` hoặc phát hiện bất kỳ câu nào bị regression so với `--baseline`. Trong GitHub Actions trên sự kiện `pull_request`, bước `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85` khiến job fail ngay lập tức khi exit code ≠ 0, chặn không cho merge PR làm tụt chất lượng.
- **Ghi chú Exercise 7.1 (Metrics & Cardinality):** Trên `/metrics` ghi nhận đủ 3 loại: Counter (`http_requests_total`), Gauge (`agent_in_flight_requests`, `agent_info`), Histogram (`http_request_duration_seconds_bucket` và metric tự thêm `agent_question_length_chars`). Dùng `route.path` thay cho `request.url.path` là bắt buộc để tránh **cardinality explosion** khi bot quét hàng nghìn URL lạ (`/wp-admin`, `/.env`, ...) làm bùng nổ số time series và tràn RAM Prometheus.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [screenshots/grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**: [screenshots/prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

**Trả lời câu hỏi quan sát (Exercise 7.4):**
1. **p95 và avg:** Khi chạy tải 30 users, Prometheus ghi nhận `p95 ≈ 289.7 ms` (`290.56 ms` trên panel Grafana) và `avg ≈ 212.2 ms`. Khoảng cách ~78 ms cho thấy phần lớn request xử lý nhanh quanh ~190–210 ms, nhưng ~3% request chậm bất thường (~1.7s) kéo các phân vị cao (`p95`/`p99`) lên cao hơn trung bình.
2. **Requests/s theo instance:** Nginx chia tải tương đối đều giữa 2 instance đang chạy (`172.20.0.6:8000` ≈ `3.16 req/s` và `172.20.0.9:8000` ≈ `3.62 req/s` tại thời điểm đo).
3. **Vì sao input tokens/s lớn hơn output tokens/s?** Thực đo trên Prometheus: `input ≈ 513.9 tok/s` vs `output ≈ 267.8 tok/s` (gần gấp đôi), vì với agent `v2` (RAG), đầu vào gửi cho LLM gồm cả `SYSTEM_PROMPT`, ngữ cảnh tài liệu truy xuất từ `KNOWLEDGE_BASE` và câu hỏi của user, dài hơn đáng kể so với câu trả lời đầu ra.
4. **`curl http://localhost:8080/metrics` trả về gì? Vì sao?** Trả về **`404 Not Found`** từ Nginx (`nginx/1.28.3`), vì `nginx.conf` chủ động chặn (`location = /metrics { return 404; }`) để không lộ thông tin nội bộ hệ thống (route, lưu lượng, trạng thái instance) ra bên ngoài; chỉ Prometheus trong mạng Docker nội bộ (`obs_net`) mới scrape trực tiếp `agent:8000/metrics`.

### 4.2 Thí nghiệm "phá hệ thống"

*(Đã chạy unit test rule bằng `promtool test rules /p/alert_rules_test.yml` → `SUCCESS`.)*

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`for: 1m`) | **107s** | Error rate (Golden Signals), Requests/s theo status code (`503`), LLM calls (`error`) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`for: 2m`) | **147s** | Latency p95 (Golden Signals), Latency `/ask` — p50 / p95 / p99 |
| C | `LLM_MODEL=mock-llm-large` | *(Chưa chạy tách riêng trong thí nghiệm; theo rule là `LLMCostBurnRateHigh` khi > `$2/giờ` trong `2m` + `AgentHighLatencyP95`)* | *(Trong đợt tải nền 30 users, `LLMCostBurnRateHigh` cũng từng bật thoáng qua lúc `+17s`)* | Cost burn rate (USD/giờ), LLM cost (1h), LLM latency p95 theo model |
| D | `docker pause` 1 instance | `AgentInstanceDown` (`for: 30s`) | **45s** (từ lúc pause `agent-1`) | Instances up (`2 → 1`), Requests/s theo instance |
| E | `AGENT_VERSION=v1` | Không có alert nào firing | — | Retrieval hit ratio (mất/giảm), Tokens/s (giảm), Phiên bản đang chạy (`v1`) |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

- **CI/CD Quality Gate trước khi deploy:** Bắt buộc chạy `eval/run_eval.py` trên golden dataset kèm `--baseline` và `--min-accuracy` để chặn các thay đổi code/prompt/config làm tụt độ chính xác (như `v2 → v1`) trước khi merge hoặc rollout.
- **Online Evaluation & Canary Check:** Chạy đánh giá tự động (LLM-as-judge hoặc semantic similarity) trên một tỷ lệ nhỏ traffic thật (sampled requests) và so sánh chất lượng ở canary trước khi đẩy 100% traffic.
- **Metric & Alert theo dõi nghiệp vụ RAG:** Đặt alert cho `retrieval_hit_ratio` giảm đột ngột hoặc `agent_info{version!="expected"}` (phát hiện deploy nhầm phiên bản/cấu hình), kết hợp thu thập feedback người dùng (thumbs up/down).

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được trong Jaeger ([screenshots/jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)):

- `trace_id`: `37f19908ac40997ce5c49e2c95ee5e50`
- Tổng thời gian: `1718.69 ms` (`1.7s` hiển thị trên Jaeger UI)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`1697.89 ms`, **`98.8%`** tổng thời gian; trong khi `agent.retrieve_context` chỉ mất `18.88 ms`, `1.1%`)
- Dòng log tương ứng (grep từ `docker compose -p k5-day14-observability logs agent` theo `trace_id`):

```json
{"ts": "2026-11-26T09:12:05.311437+00:00", "level": "INFO", "service": "observable-agent", "instance": "98e4598fc16c", "event": "llm_call", "trace_id": "37f19908ac40997ce5c49e2c95ee5e50", "span_id": "0fa7bafccd1447d8", "request_id": "da4a5c9c5eaf", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1697.8}
```

*(Trace lỗi đã kiểm tra trong [screenshots/jaeger-error-trace.png](screenshots/jaeger-error-trace.png): `trace_id = 357009defe274f413c6ab4cefcdf2cbc`, tổng `110.23 ms`, `status = 503`, span `chat mock-llm-small` ghi event `exception` với `Upstream LLM error: 503 Service Unavailable (mock)`, khớp dòng log `llm_error` cùng `trace_id`.)*

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu lấy trực tiếp từ [benchmark-results/scale_1_stats.csv](benchmark-results/scale_1_stats.csv) và [benchmark-results/scale_3_stats.csv](benchmark-results/scale_3_stats.csv) (dòng `Aggregated` — và ghi chú kèm riêng `POST /ask`):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 (`Aggregated` / `/ask`) | 66.47 (60.65) | 190 (190) | 240 (250) | 1700 (1700) | 62 / 7931 (62 / 7237) |
| 3 (`Aggregated` / `/ask`) | 66.20 (59.89) | 190 (190) | 220 (230) | 1700 (1700) | 74 / 7897 (74 / 7145) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- Scale từ **1** lên **3** instance chỉ giảm rất nhẹ `p95` (`240 → 220 ms` tổng hợp, `250 → 230 ms` cho `/ask`), trong khi `p50` (`190 ms`), `p99` (`1700 ms`) và thông lượng (`~66 req/s`) gần như giữ nguyên.
- **Lý do & nút thắt:** Ở kịch bản 100 user có `wait_time = 0.5–2s` giữa các request, tổng lượng traffic sinh ra chỉ quanh `~66 req/s` — chưa làm bão hòa CPU hay event loop bất đồng bộ (`async/await`) của 1 container FastAPI. Do đó nút thắt latency nằm ở **thời gian chờ upstream LLM** (`MOCK_LATENCY_MS` và `MOCK_SLOW_RATE = 0.03` gây `p99 = 1700 ms` trên từng request), không phải ở số lượng instance agent. Scale ngang chỉ cải thiện latency rõ rệt khi 1 instance đã bị bão hòa CPU/event loop (như mốc `concurrency = 100` ở bài `load_test.py` không có `wait_time`), hoặc để tăng tính sẵn sàng (HA) khi 1 instance gặp sự cố.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. **Percentile quan trọng hơn trung bình:** `average` che giấu *tail latency*, trong khi `p95`/`p99` phản ánh đúng trải nghiệm chậm bất thường của người dùng và là cơ sở chuẩn để đặt SLO.
  2. **Ba trụ cột Metrics – Traces – Logs bổ trợ lẫn nhau:** Prometheus/Grafana phát hiện *có sự cố*, Jaeger khoanh vùng *span gây chậm/lỗi* (`chat mock-llm-small` chiếm 98.8% thời gian), và JSON log gắn `trace_id` giúp truy ra chi tiết request tức thì.
  3. **Observability hạ tầng không thay thế được Eval chất lượng:** Hệ thống vẫn "xanh" hoàn toàn khi chất lượng trả lời tụt (như `v2 → v1`), bắt buộc phải có `golden_dataset` và quality gate tự động trong CI/CD.
- Nếu đưa agent này lên production thật, các metric / alert nên bổ sung:
  - **Metric & Alert từ tầng Nginx/Edge:** Theo dõi riêng mã `502`/`504` gateway timeout (vì request timeout ở Nginx không đi vào metric của agent).
  - **Metric chất lượng RAG & drift:** Theo dõi `retrieval_hit_ratio`, điểm đánh giá online (LLM-as-judge) theo phiên bản và alert khi tỷ lệ miss tăng bất thường.
  - **Alertmanager & Token anomaly:** Kết nối Alertmanager gửi cảnh báo về Slack/PagerDuty theo mức độ (`critical` vs `warning`), kèm alert phát hiện tăng đột biến `tokens_per_request` hoặc chi phí theo từng tenant/API key.
