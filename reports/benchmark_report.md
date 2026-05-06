# Báo Cáo Benchmark Multi-Agent Research System

Báo cáo này so sánh hai cách chạy: single-agent baseline và multi-agent workflow. Mục tiêu là đánh giá chất lượng câu trả lời, độ trễ, chi phí ước tính, khả năng trích dẫn nguồn, và khả năng quan sát trace của từng bước.

## Cấu Hình Chạy

- Baseline: một agent xử lý từ tìm nguồn đến viết câu trả lời.
- Multi-agent: Supervisor điều phối Researcher, Analyst và Writer.
- Chế độ đo hiện tại: `live provider`.
- Search runtime dùng Tavily thật qua `SearchClient`; không còn dùng mock/local corpus.
- Nếu `USE_LIVE_PROVIDERS=false` hoặc thiếu `TAVILY_API_KEY`, workflow sẽ fail rõ ràng thay vì lấy mock data.
- LangSmith: có LANGSMITH_API_KEY trong cấu hình.

## Cách Tính Metric

- **Latency**: thời gian wall-clock của mỗi lần chạy, đo bằng `perf_counter()`.
- **Cost**: chi phí từ usage/token của LLM provider nếu gọi OpenAI thành công. Nếu LLM fallback được dùng, cost là ước tính theo input/output token và bảng giá model.
- **Quality**: điểm heuristic 0-10 dựa trên final answer, số nguồn, research notes, analysis notes, citation coverage và lỗi trong state.
- **Notes**: tóm tắt luồng route, số nguồn, số lần Writer chạy và số lỗi nếu có.

## Rubric Chấm Điểm Chất Lượng

| Thành phần | Điểm tối đa | Ý nghĩa |
|---|---:|---|
| Có final answer | 3.0 | Hệ thống tạo được câu trả lời cuối cùng |
| Có nguồn tham khảo | 2.0 | Câu trả lời được grounded bằng retrieved sources |
| Có research notes | 1.5 | Researcher để lại thông tin handoff rõ ràng |
| Có analysis notes | 1.5 | Analyst phân tích claim, gap và hướng tổng hợp |
| Citation coverage | 2.0 | Final answer có trích dẫn các source index |
| Trừ lỗi | -2.0 | Trừ điểm nếu state ghi nhận lỗi workflow |

## Kết Quả Tổng Hợp

| Lần chạy | Độ trễ (s) | Độ trễ (ms) | Chi phí ước tính (USD) | Chất lượng | Ghi chú |
|---|---:|---:|---:|---:|---|
| baseline | 11.394473 | 11394.473 | 0.000512 | 7.0 | luồng=không có route; nguồn=5; writer_runs=1 |
| multi-agent | 14.396906 | 14396.906 | 0.000780 | 10.0 | luồng=researcher > analyst > writer > done; nguồn=5; writer_runs=1 |

## Phân Tích Kết Quả

- Lần chạy có điểm chất lượng cao nhất: **multi-agent** (10.0/10).
- Lần chạy nhanh nhất: **baseline** (11.394473s, 11394.473ms).
- Baseline phù hợp để có câu trả lời nhanh và kiến trúc đơn giản.
- Multi-agent có lợi thế khi cần tách rõ tìm kiếm, phân tích, viết câu trả lời và debug từng bước.
- Điểm chất lượng của multi-agent cao hơn khi workflow có research notes, analysis notes và citation coverage rõ ràng.

## Nhận Xét Từng Lần Chạy

- **baseline**: dùng một luồng đơn giản nên dễ chạy và dễ hiểu. Điểm chất lượng 7.0/10 phản ánh việc baseline có final answer và nguồn, nhưng thiếu bước phân tích độc lập.
- **multi-agent**: có route rõ qua Researcher, Analyst và Writer. Điểm chất lượng 10.0/10 cao hơn vì có research notes, analysis notes và citation coverage tốt hơn.

## Trace Va LangSmith

Lần chạy hiện tại ghi trace ở hai nơi: local `ResearchState.trace` và LangSmith project cấu hình trong `.env`. Trace local gồm các event `supervisor.route`, `researcher.sources`, `analyst.notes`, `writer.final_answer` và các span thời gian cho từng agent.

LangSmith tracing đã được bật qua `LANGSMITH_TRACING=true`. Root trace là `workflow.multi_agent`; các child span gồm `agent.supervisor`, `agent.researcher`, `agent.analyst`, `agent.writer`, và supervisor cuối cùng route sang `done`.

Có thể chèn ảnh chụp LangSmith waterfall hoặc trace link vào mục này khi nộp bài. Ví dụ:

```md
![LangSmith trace](./langsmith_trace.png)
Trace link: https://smith.langchain.com/...
```

Trong trace LangSmith nên thấy được thứ tự: Supervisor -> Researcher -> Supervisor -> Analyst -> Supervisor -> Writer -> Supervisor done.

## Checklist Nộp Bài

- [x] Có benchmark report so sánh baseline và multi-agent.
- [x] Có route history / trace local để giải thích agent nào làm gì.
- [x] Có failure mode và cách xử lý.
- [x] Có LangSmith trace provider thật cho workflow multi-agent.
- [ ] Chèn screenshot LangSmith vào repo nếu giảng viên yêu cầu nộp ảnh trực tiếp.

## Failure Mode Và Cách Xử Lý

Failure mode quan trọng nhất là provider LLM/search bị timeout hoặc không có mạng. Search runtime fail rõ ràng khi Tavily thiếu key hoặc lỗi thay vì dùng mock data. LLM client có retry có giới hạn và fallback deterministic, Supervisor có max-iteration guard, và trace event cho biết agent nào đã tạo ra thay đổi nào trong shared state.

## Kết Luận

Multi-agent đang phù hợp hơn cho bài lab này vì đáp ứng yêu cầu về role rõ ràng, shared state, guardrail, trace và benchmark. Baseline vẫn hữu ích làm mốc so sánh vì đơn giản hơn, ít orchestration overhead hơn, và giúp thấy rõ phần lợi ích thực sự của workflow nhiều agent.
