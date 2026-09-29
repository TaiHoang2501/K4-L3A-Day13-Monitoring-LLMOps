# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- **Tên:** HighErrorRate
- **Severity:** Critical
- **Duration:** 5 phút
- **Kênh thông báo:** Slack (`#alerts-day13-critical`)
- **SLI/SLO liên quan:** Guardrail Error Rate (`error_rate_pct_max: 2%`) và Primary SLO (`fast_successful_requests: 99.5%`)
- **Điều kiện và thời gian duy trì:** Tỷ lệ lỗi API request_failed / request_received vượt quá 2.0% liên tục trong 5 phút.
- **Ảnh hưởng tới người dùng:** Người dùng bị lỗi 500 khi gửi yêu cầu chat/QA, không nhận được câu trả lời từ AI assistant.
- **Ba bước kiểm tra đầu tiên:**
  1. Kiểm tra dashboard panel **Error rate and retrieval success** để xác định lỗi xuất hiện từ thời điểm nào và tỷ lệ lỗi hiện tại.
  2. Lọc `data/logs.jsonl` tìm các event `request_failed`, trích xuất `error_type`, `correlation_id` và `payload.detail`.
  3. Mở Langfuse trace tương ứng với `correlation_id` để xác định span gây ra lỗi (ví dụ Vector store timeout trong bước retrieval hay LLM API error).
- **Mitigation tạm thời:**
  - Nếu lỗi do vector store (retrieval tool_fail), bật chế độ fallback không dùng retrieval hoặc khởi động lại vector store connection pool.
  - Tắt incident nếu đang trong diễn tập bằng `/incidents/<name>/disable`.
- **Owner:** oncall-sre

## Alert 2

- **Tên:** HighLatencyP95
- **Severity:** Warning
- **Duration:** 5 phút
- **Kênh thông báo:** Slack (`#alerts-day13-latency`)
- **SLI/SLO liên quan:** Primary SLO `fast_successful_requests` (`latency_ms <= 3000ms`, target 99.5%)
- **Điều kiện và thời gian duy trì:** Latency P95 của các yêu cầu chat vượt quá 3000ms liên tục trong 5 phút.
- **Ảnh hưởng tới người dùng:** Thời gian chờ câu trả lời lâu, giao diện bị đơ/lag, suy giảm trải nghiệm người dùng.
- **Ba bước kiểm tra đầu tiên:**
  1. Xem panel **Latency percentiles and TTFT** trên Dashboard để so sánh TTFT P95 và tổng Latency P95 (xác định chậm ở bước stream token đầu tiên hay xử lý sinh từ).
  2. Lấy mẫu một số `correlation_id` có `latency_ms > 3000` trong `data/logs.jsonl` (event `response_sent`).
  3. Mở waterfall trace trên Langfuse để so sánh thời gian thực thi giữa span `retrieval` và span `generation`.
- **Mitigation tạm thời:**
  - Nếu bước `retrieval` bị chậm (ví dụ incident `rag_slow`), kích hoạt cache kết quả retrieval hoặc giảm số document truy vấn.
  - Nếu bước `generation` bị chậm, giảm max_tokens hoặc chuyển sang fallback model có latency thấp hơn.
- **Owner:** backend-team

## Alert 3

- **Tên:** LowRetrievalSuccessRate
- **Severity:** Warning
- **Duration:** 5 phút
- **Kênh thông báo:** Slack (`#alerts-day13-rag`)
- **SLI/SLO liên quan:** Guardrail `retrieval_success_rate_pct_min: 90%`
- **Điều kiện và thời gian duy trì:** Tỷ lệ thành công của retrieval tool giảm xuống dưới 90% trong 5 phút.
- **Ảnh hưởng tới người dùng:** Agent không lấy được tài liệu ngữ cảnh chính xác, câu trả lời suy giảm chất lượng hoặc rơi vào generic fallback answer.
- **Ba bước kiểm tra đầu tiên:**
  1. Kiểm tra panel **Errors** trên Dashboard, theo dõi biểu đồ `tool_success_rate_pct`.
  2. Kiểm tra log lọc theo `tool_name == "retrieval"` và `tool_success == false` để xác định mã lỗi từ vector store.
  3. Kiểm tra kết nối mạng và tài nguyên của cụm RAG/vector store.
- **Mitigation tạm thời:**
  - Chuyển sang prompt fallback với local knowledge base nếu vector store không phản hồi.
  - Scale out replicas của vector search service hoặc restart service nếu connection bị nghẽn.
- **Owner:** rag-platform-team

