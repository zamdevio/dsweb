# Proxy tool-call contract

- Input: OpenAI `tools` + optional `tool_choice`
- Mechanism: prompt injection + `<tool_call>…</tool_call>` parse (`lib/client/tools.py`)
- Output: `message.tool_calls` / streaming tool_call deltas / `finish_reason=tool_calls`
- `tool_choice=none` → omit schemas
- Streaming buffers assistant text when tools are present

Not bit-identical to official DeepSeek Platform tools.
