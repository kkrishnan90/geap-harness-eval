"""Live check: route real SDK calls through the Meter (tiny spend)."""
import asyncio
from google import genai
from google.genai import types
from anthropic import AsyncAnthropicVertex
from geap_eval.meter import Meter
from geap_eval import pricing
from geap_eval.config import PROJECT

recs = []
async def sink(kind, rec): recs.append((kind, rec))

async def main():
    m = Meter(sink); await m.start()
    base = m.register("tok1", "attempt-x")
    g = genai.Client(vertexai=True, project=PROJECT, location="global",
                     http_options=types.HttpOptions(base_url=base + "/"))
    await g.aio.models.generate_content(model="gemini-3.8-flash", contents="Say hi",
        config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="LOW")))
    async for _ in await g.aio.models.generate_content_stream(model="gemini-4-argon", contents="Count to 3"): pass
    a = AsyncAnthropicVertex(project_id=PROJECT, region="global", base_url=base + "/v1")
    await a.messages.create(model="claude-opus-5-5", max_tokens=64, messages=[{"role":"user","content":"Say hi"}])
    async with a.messages.stream(model="claude-opus-5-5", max_tokens=64, messages=[{"role":"user","content":"Count to 3"}]) as s:
        await s.get_final_message()
    bad = genai.Client(vertexai=True, project="other-project-1", location="global", http_options=types.HttpOptions(base_url=base + "/"))
    try: await bad.aio.models.generate_content(model="gemini-3.8-flash", contents="x")
    except Exception as e: print("foreign project blocked:", str(e)[:80])
    await m.stop()
    book = pricing.load_price_book()
    for kind, r in recs:
        c = pricing.cost_call(r, book)
        keys = ("provider","model","location","method","stream","http_status","stop_reason","tok_input","tok_cache_read","tok_output","tok_thinking","tok_total","traffic_type","thinking_requested")
        print(kind, {k: r.get(k) for k in keys}, "cost", c.usd, c.status, c.notes[:1])
asyncio.run(main())
