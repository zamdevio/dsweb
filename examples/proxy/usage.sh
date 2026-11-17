#!/usr/bin/env bash
# examples/proxy: call the local proxy from common clients.
# 1. start:  ./dsweb serve
# 2. run:    bash examples/proxy/usage.sh
set -euo pipefail
BASE="${DS_LOCAL_BASE:-http://127.0.0.1:8787/v1}"
KEY="${DS_API_KEY:-sk-dsweb-change-me}"

echo "── curl (streaming) ──"
curl -sS -N "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","stream":true,
       "messages":[{"role":"user","content":"say hi in 3 words"}]}'
echo; echo

echo "── curl (thinking) ──"
curl -sS "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"deepseek-reasoner","thinking":true,
       "messages":[{"role":"user","content":"what is 17*23? show reasoning"}]}'

echo
echo "── curl (tools) ──"
curl -sS "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{
    "model":"deepseek-chat",
    "messages":[{"role":"user","content":"What is the weather in SF? Use the tool."}],
    "tools":[{
      "type":"function",
      "function":{
        "name":"get_weather",
        "description":"Get weather by city",
        "parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}
      }
    }],
    "tool_choice":"required"
  }'
echo

cat <<EOF

── python (openai sdk) ──
  from openai import OpenAI
  c = OpenAI(base_url="$BASE", api_key="$KEY")
  r = c.chat.completions.create(model="deepseek-chat",
        messages=[{"role":"user","content":"hi"}])
  print(r.choices[0].message.content)

── js (fetch) ──
  const r = await fetch("$BASE/chat/completions", {
    method: "POST",
    headers: { "Authorization": "Bearer $KEY", "Content-Type": "application/json" },
    body: JSON.stringify({ model: "deepseek-chat",
      messages: [{ role: "user", content: "hi" }] }),
  });
  console.log((await r.json()).choices[0].message.content);
EOF
