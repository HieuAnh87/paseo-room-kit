# Context window và compaction cho Paseo Lead

Ngày nghiên cứu: `2026-08-09`

## Câu hỏi

Lead có cần model context `1M` hay nên giữ working context khoảng `300K`, sau đó compact trên mọi model để vận hành an toàn hơn?

## Kết luận

`1M` không phải lượng context nên sử dụng thường xuyên. Nó chỉ là **trần dự phòng**. Với Lead dài hạn, phương án hợp lý hơn là:

1. giữ active working set có chủ đích, không đợi gần đầy cửa sổ;
2. compact hoặc reset tại ngưỡng mềm đã được benchmark;
3. ghi objective, quyết định, rủi ro, bằng chứng và next action ra artifact bền vững;
4. nạp lại bằng chứng chính xác từ file/git/runtime khi cần, không xem summary là source of truth.

Vì vậy, giả thuyết `Sonnet 5 [1M] + compact khoảng 250–300K` là một cấu hình pilot hợp lý. Nhưng `300K` chưa phải ngưỡng đã được chứng minh chung cho mọi model; cần đo trên trace Paseo thực tế. Chọn biến thể `1M` không đồng nghĩa với việc cho phiên làm việc tăng tới `1M`.

Nếu chỉ dùng biến thể Sonnet 5 `200K`, mục tiêu compact ở `300K` là không khả thi. Khi đó ngưỡng mềm phải thấp hơn đáng kể, và khoảng đệm cho tool output hoặc một turn lớn sẽ hẹp hơn.

## Bằng chứng

### 1. Context lớn không loại bỏ context pollution

Anthropic mô tả context là tài nguyên hữu hạn cần được chọn lọc. Họ cảnh báo rằng dù cửa sổ lớn đến đâu, context pollution và vấn đề độ liên quan vẫn tồn tại; các kỹ thuật cho tác vụ dài hạn gồm compaction, structured note-taking và multi-agent architecture.

Nguồn: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

Các nghiên cứu về long-context cũng cho thấy thông tin ở giữa context có thể được sử dụng kém hơn thông tin ở đầu hoặc cuối. Do đó, thêm raw context không tự động tạo ra khả năng nhớ đáng tin cậy.

Nguồn: [Lost in the Middle](https://arxiv.org/abs/2307.03172), [Found in the Middle](https://research.google/pubs/found-in-the-middle-calibrating-positional-attention-bias-improves-long-context-utilization/)

### 2. Compaction hữu ích nhưng có thể làm mất chi tiết

Anthropic mô tả Claude Code compact bằng cách tóm tắt lịch sử, giữ các quyết định kiến trúc, bug chưa giải quyết và chi tiết triển khai, đồng thời loại bỏ tool output dư thừa. Họ cũng nói compaction quá mạnh có thể làm mất ngữ cảnh tinh tế nhưng quan trọng.

Nguồn: [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

Trong thử nghiệm agent dài hạn, Anthropic ghi nhận compaction không phải lúc nào cũng truyền đạt hoàn hảo chỉ dẫn cho phiên tiếp theo. Giải pháp hiệu quả cần thêm progress file, git history, tiến độ theo lát nhỏ và handoff có cấu trúc.

Nguồn: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

Một thử nghiệm khác phân biệt rõ compaction với context reset: compaction giữ continuity nhưng không tạo clean slate; reset kèm structured handoff có thể sửa mất coherence ở model/harness nhất định. Điều này cho thấy chính sách phải được benchmark theo model, không nên giả định một cơ chế compact giống nhau sẽ an toàn trên mọi provider.

Nguồn: [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

### 3. Native compaction không đồng nhất giữa provider

OpenAI hiện dùng một compaction item đặc biệt, opaque và encrypted trong Responses API; Codex tự compact khi vượt `auto_compact_limit`. Đây không phải cùng cơ chế với summary dạng văn bản của Claude Code, nên không thể coi “compact ở mọi model” là một primitive có semantics giống nhau.

Nguồn: [Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)

OpenAI cũng huấn luyện GPT-5.1-Codex-Max cho nhiều cửa sổ context qua compaction, củng cố nhận định rằng khả năng chịu nhiều lần compact là thuộc tính của model và runtime, không chỉ là một ngưỡng token bên ngoài.

Nguồn: [Building more with GPT-5.1-Codex-Max](https://openai.com/index/gpt-5-1-codex-max/)

### 4. Sonnet 5 có 1M nhưng benchmark dài hạn vẫn dùng compaction

Anthropic công bố Sonnet 5 có context tới `1M`. Benchmark agentic search được chạy với ngân sách tổng `10M` token, compaction và programmatic tool calling. Điều này cho thấy cửa sổ `1M` và compaction là hai lớp bổ trợ, không phải hai lựa chọn loại trừ nhau.

Nguồn: [Introducing Claude Sonnet 5](https://www.anthropic.com/news/claude-sonnet-5), [Claude Sonnet 5 System Card](https://www-cdn.anthropic.com/73ad94ca3c0502e75e46637cc62c8bd9532a7f2c/Claude%20Sonnet%205%20System%20Card.pdf)

## Chính sách pilot đề xuất

Không áp dụng ngay như policy production; trước hết chạy một nhóm workstream có thể so sánh:

- dùng `Sonnet 5 [1M]` như capacity ceiling;
- đặt `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000`; Claude Code sẽ auto-compact khi usage tiến gần cửa sổ này thay vì đợi sát `1M`;
- tại mỗi checkpoint, lưu tối thiểu: objective hiện hành, quyết định Human đã chấp nhận, ownership, open dissent/risk, bằng chứng đã có, việc tiếp theo;
- sau compaction, kiểm tra Lead có khôi phục đúng các trường trên và có tiếp tục từ bằng chứng thay vì suy đoán hay không;
- so sánh với một nhánh `200K` compact sớm hơn và với Lead Codex hiện tại;
- đo drift, chi phí/độ trễ, số lần phải đọc lại, lỗi quên constraint và chất lượng handback.

Ngưỡng production nên được chọn từ kết quả pilot. Nếu `200K` không làm tăng drift hay handoff friction, không có lý do governance để trả chi phí cho `1M`. Nếu `300K` working set hữu ích, biến thể `1M` tạo khoảng đệm an toàn cho turn lớn và compact có kiểm soát.

Nguồn cấu hình: [Claude Code environment variables](https://code.claude.com/docs/en/env-vars#variables)

## Quyết định hiện tại

Chưa có bằng chứng để bắt buộc Lead dùng `1M`. Khuyến nghị chính xác là:

> Dùng `1M` như headroom tùy chọn cho pilot dài hạn; vận hành với working set nhỏ hơn và compaction/checkpoint chủ động. Không để context tự tăng tới giới hạn, và không dựa vào summary như nguồn trạng thái duy nhất.
