# Tài Liệu Thiết Kế: Multi-Agent Research System

## 1. Bài Toán

Hệ thống cần xây dựng là một trợ lý nghiên cứu có khả năng nhận câu hỏi từ người dùng,
tìm nguồn tham khảo liên quan, phân tích thông tin, sau đó viết câu trả lời cuối cùng
có trích dẫn nguồn.

Ví dụ query:

```text
Research GraphRAG state-of-the-art and write a concise summary
```

Đầu ra mong muốn:

- Có câu trả lời rõ ràng, phù hợp với người học kỹ thuật.
- Có danh sách nguồn đã dùng.
- Có phân tích điểm mạnh, điểm yếu hoặc khoảng trống của bằng chứng.
- Có trace để biết agent nào đã làm bước nào.
- Có benchmark so sánh baseline single-agent và workflow multi-agent.

## 2. Vì Sao Cần Multi-Agent?

Nếu chỉ dùng một agent, toàn bộ công việc như tìm nguồn, phân tích, viết câu trả lời
và kiểm tra lỗi đều nằm trong một bước duy nhất. Cách này đơn giản, nhưng khó debug và
khó biết phần nào gây ra lỗi khi câu trả lời sai hoặc thiếu nguồn.

Multi-agent giúp tách bài toán thành nhiều vai trò rõ ràng:

- Researcher chỉ tập trung tìm và tóm tắt nguồn.
- Analyst chỉ tập trung phân tích claim, gap và độ tin cậy.
- Writer chỉ tập trung viết câu trả lời cuối cùng.
- Supervisor điều phối thứ tự chạy và quyết định khi nào dừng.

Cách thiết kế này giúp workflow dễ quan sát hơn, dễ benchmark hơn và gần với cách xây
dựng hệ thống AI production hơn.

## 3. Vai Trò Các Agent

| Agent | Trách nhiệm | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Điều phối workflow, chọn agent tiếp theo, quyết định khi nào dừng | Shared state hiện tại | Route tiếp theo trong `route_history` | Route sai, chạy quá số vòng lặp, thiếu điều kiện dừng |
| Researcher | Tìm nguồn, loại trùng, tạo research notes có đánh số citation | User query, `max_sources` | `sources`, `research_notes` | Không tìm được nguồn, nguồn yếu, search provider timeout |
| Analyst | Phân tích claim chính, điểm yếu bằng chứng, đề xuất hướng tổng hợp | `sources`, `research_notes` | `analysis_notes` | Phân tích thiếu, không phát hiện nguồn yếu hoặc thiếu URL |
| Writer | Viết câu trả lời cuối cùng có trích dẫn nguồn | Query, research notes, analysis notes, sources | `final_answer` | Câu trả lời thiếu citation, nói quá bằng chứng, không rõ ràng |
| Critic | Kiểm tra nhẹ citation coverage và final answer | Final state | Critic findings trong `agent_results` | Không bắt được hallucination phức tạp |

## 4. Shared State

Shared state là nơi tất cả agent đọc và ghi thông tin. Trong repo, state chính là
`ResearchState`.

Các field quan trọng:

| Field | Ý nghĩa |
|---|---|
| `request` | Chứa query, audience và số nguồn tối đa cần lấy |
| `iteration` | Đếm số lần Supervisor route để tránh workflow chạy vô hạn |
| `route_history` | Lưu lịch sử route, ví dụ `researcher > analyst > writer > done` |
| `sources` | Danh sách nguồn Researcher tìm được |
| `research_notes` | Ghi chú nghiên cứu có đánh số nguồn `[1]`, `[2]`, ... |
| `analysis_notes` | Phân tích claim, gap, rủi ro và hướng tổng hợp |
| `final_answer` | Câu trả lời cuối cùng cho người dùng |
| `agent_results` | Log output của từng agent kèm metadata như token/cost |
| `trace` | Event trace local để debug từng bước |
| `errors` | Danh sách lỗi recoverable trong workflow |

Thiết kế này giúp mỗi agent không cần biết nội bộ của agent khác. Agent chỉ cần đọc
shared state, cập nhật phần mình phụ trách, rồi trả lại state.

## 5. Routing Policy

Luồng chạy mặc định:

```text
User Query
   |
   v
Supervisor
   |
   v
Researcher
   |
   v
Supervisor
   |
   v
Analyst
   |
   v
Supervisor
   |
   v
Writer
   |
   v
Supervisor
   |
   v
Done
```

Logic route:

1. Nếu chưa có `sources` hoặc `research_notes`, Supervisor route sang `researcher`.
2. Nếu đã có research notes nhưng chưa có `analysis_notes`, route sang `analyst`.
3. Nếu đã có analysis notes nhưng chưa có `final_answer`, route sang `writer`.
4. Nếu đã có final answer, route sang `done`.
5. Nếu vượt quá `MAX_ITERATIONS`, workflow dừng hoặc dùng kết quả tốt nhất hiện có.

Route history kỳ vọng:

```text
researcher > analyst > writer > done
```

## 6. Guardrails

| Guardrail | Cách triển khai |
|---|---|
| Max iterations | `MAX_ITERATIONS`, mặc định là `6`, tránh agent loop vô hạn |
| Timeout | Provider client dùng `TIMEOUT_SECONDS` khi bật live provider |
| Retry | LLM client dùng retry có giới hạn khi gọi provider thật |
| Fallback | Search không dùng mock fallback; nếu Tavily thiếu key hoặc lỗi thì fail rõ ràng. LLM vẫn có fallback deterministic để tránh mất toàn bộ workflow khi provider lỗi |
| Validation | Dùng Pydantic schema cho query, source, agent result và benchmark metrics |
| Trace | Mỗi bước ghi event vào `ResearchState.trace` |
| Error handling | Lỗi recoverable được ghi vào `state.errors` thay vì làm workflow sập ngay |

## 7. Baseline Single-Agent

Baseline dùng một luồng đơn giản:

```text
Query -> SearchClient -> LLMClient -> Final Answer
```

Baseline hữu ích vì:

- Là mốc so sánh với multi-agent.
- Chạy nhanh hơn, ít orchestration hơn.
- Cho thấy multi-agent có thật sự cải thiện chất lượng hay không.

Điểm yếu của baseline:

- Không có bước phân tích độc lập.
- Trace ít chi tiết hơn.
- Khó debug khi câu trả lời sai hoặc thiếu nguồn.

## 8. Benchmark Plan

Các query nên dùng để benchmark:

| Query | Metric chính | Kỳ vọng |
|---|---|---|
| Research GraphRAG state-of-the-art | Quality, citation coverage, latency | Multi-agent có câu trả lời grounded hơn |
| Compare single-agent and multi-agent workflows for customer support | Quality, route trace | Multi-agent giải thích rõ hơn vai trò từng bước |
| Summarize production guardrails for LLM agents | Source coverage, failure mode | Câu trả lời nhắc đến retry, timeout, fallback, validation |

Metric được đo:

- Latency: thời gian chạy end-to-end.
- Estimated cost: chi phí ước tính từ token metadata.
- Quality score: điểm heuristic 0-10.
- Citation coverage: số source được cite trong final answer.
- Error count: số lỗi ghi trong shared state.

## 9. Trace Và Quan Sát

Trace local hiện được lưu trong `ResearchState.trace`. Một run multi-agent nên có các event:

```text
supervisor.route
researcher.sources
analyst.notes
writer.final_answer
span.supervisor
span.researcher
span.analyst
span.writer
```

Nếu cần nộp LangSmith screenshot, có thể tích hợp LangSmith và chụp trace thể hiện rõ thứ tự:

```text
Supervisor -> Researcher -> Supervisor -> Analyst -> Supervisor -> Writer -> Done
```

## 10. Failure Mode Và Cách Xử Lý

Failure mode quan trọng:

- Search provider timeout hoặc không có API key.
- LLM provider lỗi mạng hoặc quota.
- Researcher tìm được nguồn yếu.
- Writer không cite đủ nguồn.
- Supervisor route sai hoặc không dừng.

Cách xử lý trong thiết kế hiện tại:

- Không dùng mock/local fallback cho search runtime; bắt buộc dùng Tavily qua `SearchClient`.
- Dùng retry có giới hạn cho LLM provider.
- Dùng `MAX_ITERATIONS` để tránh loop vô hạn.
- Dùng `state.errors` để lưu lỗi recoverable.
- Dùng `trace` và `route_history` để debug workflow.

## 11. Kết Luận Thiết Kế

Thiết kế multi-agent phù hợp với bài lab vì đáp ứng các yêu cầu chính:

- Có role rõ ràng cho từng agent.
- Có shared state làm nguồn dữ liệu chung.
- Có guardrail chống workflow chạy vô hạn.
- Có trace để giải thích agent nào làm gì.
- Có benchmark report để so sánh baseline và multi-agent.

Baseline vẫn cần giữ lại để làm mốc so sánh. Multi-agent không phải lúc nào cũng tốt hơn,
nhưng với bài toán nghiên cứu cần nguồn, phân tích và citation, workflow nhiều agent giúp
hệ thống dễ kiểm soát và dễ debug hơn.
