# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Hoàng Anh Tài
- **MSSV:** 2A202602612
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/TaiHoang2501/K4-L3A-Day13-Monitoring-LLMOps.git
- **Commit SHA cuối:** 13b606680ae4a3072eda90334959b632fe4ecba0
- **Challenge ID:** day13-k4-l3a-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-02612`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 80/100 | 100/100 | Pass cả 4 tiêu chí (schema, correlation ID, enrichment, PII scrubbing) |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Hợp lệ toàn bộ 6 panel theo đúng contract |
| `pytest` | 22 passed | 24 passed | 100% passed (bổ sung test CCCD và Thẻ thanh toán) |
| Số traces hợp lệ | 0 | 12 traces | Traces hiển thị đầy đủ root/child observations trên Langfuse |
| Số PII leak | 0 | 0 | Đã scrub sạch Email, SĐT VN, CCCD, Thẻ thanh toán |
| Latency P95 / TTFT P95 | 1417.2ms / 57.0ms | 1417.2ms / 57.0ms | Đạt SLO (< 3000ms), TTFT ổn định |
| Retrieval success rate | 100% | 100% | 100% query retrieval thành công ở baseline |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Sử dụng `CorrelationIdMiddleware` (`app/middleware.py`) gắn vào luồng request của FastAPI.
  - Đầu mỗi request, gọi `clear_contextvars()` để chống rò rỉ context giữa các async tasks.
  - Kiểm tra header `x-request-id`: nếu client truyền lên thì nhận nguyên vẹn, nếu không thì sinh mới theo định dạng `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`).
  - Gắn correlation ID vào structlog contextvars (`bind_contextvars`) và `request.state.correlation_id`.
  - Trả lại correlation ID qua response header `x-request-id` và thời gian xử lý qua `x-response-time-ms`.

- **Các metadata được ghi vào structured log:**
  - `user_id_hash`: SHA-256 rút gọn 12 ký tự của user_id (không lưu user_id thô).
  - `session_id`: Định danh phiên người dùng.
  - `feature`: Tên tính năng (`qa`, `summary`, v.v.).
  - `model`: Model LLM phục vụ (`claude-sonnet-4-5`).
  - `env`: Môi trường triển khai (`dev`).
  - `correlation_id`: Định danh tương quan gắn kết toàn bộ log của một request.
  - Các trường hiệu năng: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.

- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Đăng ký processor `scrub_event` trong chuỗi pipeline structlog đặt ngay trước `JsonlFileProcessor` và `JSONRenderer`.
  - `scrub_event` duyệt đệ quy làm sạch các trường văn bản trong `payload` và `event` qua hàm `_scrub_value` kết hợp bộ regex `PII_PATTERNS` trong `app/pii.py` (Email, SĐT VN, CCCD, Thẻ tín dụng).
  - Vì processor thực thi trước giai đoạn serialize JSON và ghi file, không có PII thô nào bị lọt xuống `data/logs.jsonl` hoặc stdout.

- **Cách kiểm chứng kết quả:**
  - Chạy `python scripts/validate_logs.py` đạt điểm tuyệt đối 100/100, 0 PII leak.
  - Kiểm tra trực tiếp file `data/logs.jsonl` thấy các thông tin nhạy cảm đều được thay bằng `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`.
  - Chạy `pytest` xác nhận các unit test PII (`test_pii.py`) đều passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Cấu hình `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` trỏ về project cá nhân trên Langfuse Cloud (`cloud.langfuse.com`).
  - Xác nhận kết nối qua `client.auth_check() == True` và kiểm tra các traces xuất hiện đúng trong project dashboard cá nhân.
- **Cấu trúc root/retrieval/generation observations:**
  - **Root observation:** `lab-agent-run` (type `AGENT`, capture_input=False, capture_output=False để bảo vệ PII).
  - **Child observation 1:** `retrieval` (type `RETRIEVER`, span thực thi hàm `retrieve(message)`).
  - **Child observation 2:** `generation` (type `GENERATION`, thực thi `FakeLLM.generate()`, ghi nhận `model`, `prompt`, `usage_details` và `cost_details`).
  - Waterfall thể hiện phân đoạn rõ ràng: bước retrieval và bước LLM generation tách biệt, giúp định vị chính xác bottleneck khi có độ trễ cao.
- **Cách nối trace với log:**
  - Sử dụng chung `correlation_id`. Correlation ID từ middleware được truyền vào trace metadata thông qua `propagate_attributes(metadata={"correlation_id": correlation_id})`.
  - Khi cần điều tra một log bất thường, chỉ cần lấy `correlation_id` từ `data/logs.jsonl` và tra cứu trong ô tìm kiếm metadata của Langfuse.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1, gắn labels `['baseline', 'production']`.
- **Version/label candidate:** Version 2 (bổ sung hướng dẫn trả lời ngắn gọn), gắn label `['candidate']`.
- **Trace ID của mỗi version:**
  - Version 1 (production): Trace ID `f45cd741bdbd18fc4b30d4e11cb4c04e` (và `948e003f2d4e4f48449edd39a7a1c10a`, Correlation ID: `req-tr-08-725b`).
  - Version 2 (candidate): Trace ID `e8b7b650ed88e1ad2060b103f1cb3cca` (Correlation ID: `req-tr-10-7da6`).
- **Cách promote và rollback `production`:**
  - **Promote:** Dùng SDK `client.update_prompt(name="day13-chat", version=2, new_labels=["candidate", "production"])` để chuyển nhãn production sang v2.
  - **Rollback:** Khi cần quay lại bản ổn định, gọi `client.update_prompt(name="day13-chat", version=1, new_labels=["baseline", "production"])` để chuyển nhãn production về v1 mà không cần sửa code hay redeploy app.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  1. `latency`: P50, P95, P99 và TTFT P95 (Đơn vị: ms, Threshold: P95 <= 3000ms).
  2. `traffic`: Tổng số request và tốc độ request/phút (Đơn vị: requests_per_minute, Threshold: rate >= 1 req/min).
  3. `errors`: Error rate %, phân bổ loại lỗi và tỷ lệ thành công của retrieval (Đơn vị: percent, Threshold: error_rate <= 2%).
  4. `cost`: Tổng chi phí tích lũy và chi phí theo thời gian (Đơn vị: usd, Threshold: total <= $2.50 USD).
  5. `tokens`: Tổng lượng token in và token out (Đơn vị: tokens, Threshold: sum <= 50,000 tokens).
  6. `quality`: Điểm chất lượng trung bình dựa trên heuristic proxy (Đơn vị: score_0_to_1, Threshold: mean >= 0.75).
- **SLO và lý do chọn:**
  - Primary SLO: `fast_successful_requests` với mục tiêu 99.5% trong cửa sổ 28 ngày.
  - SLI: Tỷ lệ các request có `event == "response_sent" and latency_ms <= 3000` trên tổng số `request_received`.
  - Lý do: Baseline P95 latency đo được là ~1417ms. Ngưỡng 3000ms đảm bảo đủ dung sai an toàn cho biến động mạng nhưng sẽ phát hiện vi phạm ngay lập tức khi xuất hiện sự cố nghiêm trọng (ví dụ incident `rag_slow` thêm 2500ms làm latency vượt ~3900ms).
- **Cách tính error budget:**
  - Error budget = $100\% - 99.5\% = 0.5\%$.
  - Trong chu kỳ 28 ngày, với mỗi 10,000 requests, hệ thống cho phép tối đa 50 requests bị lỗi HTTP 500 hoặc có độ trễ vượt quá 3000ms.
- **Ba alert và runbook tương ứng:**
  1. `HighErrorRate` (Critical): Kích hoạt khi `error_rate_pct > 2.0%` kéo dài trong 5 phút. Kênh Slack `#alerts-day13-critical`, owner: `oncall-sre`, runbook: `docs/alerts.md#alert-1`.
  2. `HighLatencyP95` (Warning): Kích hoạt khi `latency_p95_ms > 3000ms` kéo dài trong 5 phút. Kênh Slack `#alerts-day13-latency`, owner: `backend-team`, runbook: `docs/alerts.md#alert-2`.
  3. `LowRetrievalSuccessRate` (Warning): Kích hoạt khi `retrieval_success_rate_pct < 90%` trong 5 phút. Kênh Slack `#alerts-day13-rag`, owner: `rag-platform-team`, runbook: `docs/alerts.md#alert-3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (incident chính thức: `rag_slow`)
- **Khoảng thời gian điều tra:** 15:00:00 – 15:30:00 (chu kỳ diễn tập sự cố)
- **Triệu chứng từ metrics:**
  - Panel **Latency percentiles and TTFT**: P95 latency tăng đột biến từ baseline ~1417ms lên ~3950ms (vượt ngưỡng SLO 3000ms).
  - Panel **Errors**: Error rate đạt 0% (hệ thống vẫn trả về kết quả nhưng độ trễ nghiêm trọng vi phạm SLO `fast_successful_requests`).
  - Alert kích hoạt: `HighLatencyP95` (Warning, latency_p95 > 3000ms duy trì trong 5 phút).
- **Log line và correlation ID liên quan:**
  - Truy vấn lọc trong `data/logs.jsonl` tìm các event `response_sent` có `latency_ms > 2000` của challenge:
    ```json
    {
      "service": "api",
      "event": "response_sent",
      "correlation_id": "req-4d9c811c",
      "session_id": "k4-l3a-challenge-s01",
      "feature": "monitoring",
      "latency_ms": 4300,
      "ttft_ms": 53,
      "tool_name": "retrieval",
      "tool_success": true,
      "model": "claude-sonnet-4-5"
    }
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Trace ID trên Langfuse Cloud: `53056307fbdeb281117ad7e03a19e39c` (Session `k4-l3a-challenge-s01`, Correlation ID `req-4d9c811c`).
  - Quan sát waterfall hierarchy:
    - Root `lab-agent-run`: ~4300ms
    - **Span `retrieval` (RETRIEVER): 2505ms** $\rightarrow$ Đây là span chịu trách nhiệm cho hơn 60% tổng thời gian request.
    - Span `generation` (GENERATION): 150ms (hoạt động bình thường).
- **Root cause:**
  - Bước truy vấn vector store trong hàm `retrieve()` bị nghẽn (do incident `rag_slow`), gây trễ ~2500ms cho mỗi lượt tìm kiếm tài liệu ngữ cảnh, dẫn tới vi phạm SLO P95 latency của toàn hệ thống.
- **Fix action:**
  - Kích hoạt cache bộ nhớ (Redis/in-memory cache) cho các câu hỏi phổ biến để giảm tải truy vấn vector store.
  - Cấu hình timeout tối đa cho bước retrieval (ví dụ 1500ms), nếu quá thời gian thì fallback sang câu trả lời tổng quát thay vì để request bị treo lâu.
  - Scale out số lượng worker / read-replicas của cụm vector database.
- **Preventive measure:**
  - Triển khai Circuit Breaker cho retrieval tool: tự động ngắt kết nối tạm thời khi tỷ lệ trễ cao và chuyển sang chế độ degraded mode.
  - Thiết lập alert cảnh báo sớm `HighLatencyP95` trên kênh Slack `#alerts-day13-latency` để đội ngũ backend phản ứng trước khi cạn kiệt Error Budget của chu kỳ 28 ngày.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - **Đăng ký PII scrubber (`scrub_event`) ở cấp độ Structlog Processor pipeline ngay trước File Writer / JSON Renderer:** Thay vì scrub thủ công rải rác ở từng endpoint hoặc controller, quyết định này bảo đảm nguyên tắc *Defense in Depth*. Bất kỳ log event nào phát sinh từ ứng dụng (từ request thông thường, lỗi hệ thống unhandled exception, hay log từ middleware) đều bắt buộc đi qua processor làm sạch trước khi serialize và ghi xuống đĩa, ngăn chặn triệt để rủi ro rò rỉ PII do sơ suất của lập trình viên.

- **Một lỗi/blocker đã gặp:**
  - Lỗi OpenTelemetry Exporter trên macOS khi gửi span telemetry lên Langfuse Cloud: `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)`. Lỗi này làm các batch trace bị timeout và retry liên tục.
  - Lỗi môi trường ban đầu: Lệnh `python` mặc định của macOS trỏ về Python 2.7 không có module `venv`.

- **Cách tìm nguyên nhân và xử lý:**
  - Đối với lỗi Python 2.7: Kiểm tra các binary cài trên máy và khởi tạo virtualenv tường minh bằng Python 3.12 (`python3.12 -m venv .venv`).
  - Đối với lỗi OpenTelemetry SSL: Thư viện `urllib3` của OpenTelemetry không tự động đọc keychain root certificates của macOS. Đã xử lý bằng cách tích hợp `certifi` vào đầu `app/tracing.py`, tự động thiết lập `os.environ.setdefault("SSL_CERT_FILE", certifi.where())` và `REQUESTS_CA_BUNDLE`. Sau khi cấu hình, telemetry kết nối thông suốt và export dữ liệu lên Langfuse Cloud 100%.

- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics (Triệu chứng - What & When):** Biểu đồ trên Dashboard cung cấp góc nhìn tổng quan theo thời gian thực (ví dụ phát hiện Latency P95 vọt lên > 3000ms hoặc Error Rate tăng vọt tại một mốc thời gian).
  - **Logs (Phạm vi - Which):** Dựa vào khoảng thời gian sự cố, truy vấn `data/logs.jsonl` để lọc ra danh sách request bị ảnh hưởng và trích xuất `correlation_id` của request bất thường.
  - **Traces (Nguyên nhân gốc - Where & Why):** Dùng `correlation_id` tra cứu trên Langfuse để mở waterfall view của trace. Nhờ cấu trúc phân rã `lab-agent-run` → `retrieval` → `generation`, ta xác định chính xác span nào gây chậm/lỗi và thông điệp lỗi cụ thể, từ đó đưa ra root cause và biện pháp khắc phục.

- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Trong vận hành hệ thống AI/LLM, mô hình có tính chất phi tất định (non-deterministic). Quản lý prompt tập trung theo version và labels (`production`, `candidate`, `baseline`) cho phép truy vết chính xác prompt template nào đã sinh ra kết quả của từng request.
  - Khi prompt mới gây suy giảm chất lượng, tăng độ trễ hoặc bùng nổ token/cost, cơ chế label promotion cho phép SRE/Engineer rollback về version trước đó trong vòng vài giây trên giao diện quản lý mà không cần sửa code, rebuild image hay restart dịch vụ.
  - SLO và Error Budget cung cấp ranh giới định lượng rõ ràng giúp đội ngũ quyết định khi nào được phép thử nghiệm tính năng/prompt mới và khi nào phải tạm dừng để củng cố độ tin cậy hệ thống.

- **Điều quan trọng nhất đã học:**
  - Nắm vững kiến trúc Observability end-to-end cho LLMOps: cách đồng bộ `correlation_id` xuyên suốt từ HTTP Middleware, Structured Logs đến OpenTelemetry Traces trên Langfuse; kỹ thuật PII scrubbing tự động; và quy trình ứng cứu sự cố chuẩn SRE qua Runbook và Alert rules.

- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Hệ thống hiện tại nhận diện PII bằng Regex patterns tối ưu cho Email, SĐT VN, CCCD và Thẻ thanh toán. Trong môi trường production phức tạp với ngôn ngữ tự nhiên đa dạng, có thể mở rộng kết hợp các mô hình NER chuyên dụng (như Microsoft Presidio) để nhận diện địa chỉ và tên riêng linh hoạt hơn.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.

