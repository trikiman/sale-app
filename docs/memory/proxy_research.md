# API Proxy Alternatives to Bonsai for Claude Code (Claude Sonnet 4.6)

**Research Date:** 2026-03-05
**Objective:** Find free/cheap API proxies that support Claude Sonnet 4.6 and expose a standard `/v1/messages` REST API compatible with Claude Code.

---

## How Claude Code Connects to Proxies

Claude Code uses two environment variables to redirect API calls:

```bash
export ANTHROPIC_BASE_URL="http://localhost:PORT/v1"
export ANTHROPIC_API_KEY="your-key-or-proxy-token"
```

**Requirements for any proxy:**
- Must expose Anthropic Messages API format at `/v1/messages`
- Must forward headers: `anthropic-beta`, `anthropic-version`
- Avoid query parameters in `ANTHROPIC_BASE_URL` (known SDK bug)
- Use `ANTHROPIC_AUTH_TOKEN` for proxy-level auth if needed

Source: [Anthropic LLM Gateway Docs](https://docs.anthropic.com/en/docs/claude-code/llm-gateway)

---

## Baseline: Direct Anthropic API Pricing

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Haiku 4.5 | $0.25 | $1.25 |
| **Sonnet 4.6** | **$3.00** | **$15.00** |
| Opus 4.6 | $15.00 | $75.00 |
| Sonnet 4.6 (Batch) | $1.50 | $7.50 |
| Sonnet 4.6 (Cache reads) | $0.30 | -- |

Source: [OpenRouter Pricing](https://openrouter.ai/anthropic/claude-sonnet-4.6/pricing) | [PricePerToken](https://pricepertoken.com/pricing-page/model/anthropic-claude-sonnet-4.6)

---

## Top Proxy Alternatives

### 1. OpenRouter (Managed, Pay-per-token)

| Attribute | Details |
|-----------|---------|
| **URL** | https://openrouter.ai |
| **Cost** | Pass-through pricing + small markup; Sonnet 4.6 ~$3/$15 per 1M tokens |
| **Claude Code Compatible** | Yes, via Anthropic-format endpoint |
| **Claude Sonnet 4.6** | Yes (`anthropic/claude-sonnet-4.6`) |
| **Free tier** | Some free models available; Claude models are paid |
| **Setup** | `ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1` |

**Pros:** 250+ models, reliable, good fallback routing, community rankings
**Cons:** No free Claude access, small markup over base pricing
**Verdict:** Best managed multi-provider option. No savings on Claude specifically.

Source: [OpenRouter Claude Sonnet 4.6](https://openrouter.ai/anthropic/claude-sonnet-4.6)

---

### 2. LiteLLM (Self-hosted, Free & Open Source)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/BerriAI/litellm |
| **Cost** | Free (self-hosted); Enterprise plan available |
| **Claude Code Compatible** | Yes, native `/v1/messages` support |
| **Claude Sonnet 4.6** | Yes, via Anthropic direct, Bedrock, or Vertex AI |
| **Setup** | `pip install litellm` then `litellm --config config.yaml` |

**Key Features:**
- Routes to 100+ LLM providers through unified API
- Built-in cost tracking, caching, fallback, load balancing
- Web search interception for Claude Code (v1.81.0+)
- 25% CPU reduction in latest version
- Can route through AWS Bedrock or Google Vertex (potentially cheaper with credits)

**Setup Example:**
```yaml
model_list:
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: sk-ant-xxx
```
```bash
litellm --config config.yaml
export ANTHROPIC_BASE_URL=http://localhost:4000
```

**Pros:** Most feature-rich, free, excellent Claude Code integration
**Cons:** Requires self-hosting, still need upstream API keys
**Verdict:** Best self-hosted option. Saves money through caching and smart routing.

Source: [LiteLLM Docs](https://docs.litellm.ai/release_notes/v1-81-0) | [LiteLLM Claude Code WebSearch](https://docs.litellm.ai/docs/tutorials/claude_code_websearch)

---

### 3. Antigravity Claude Proxy (Free)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/badrisnarayanan/antigravity-claude-proxy |
| **Cost** | FREE (uses Google Antigravity backend) |
| **Claude Code Compatible** | Yes, translates to Anthropic Messages API |
| **Claude Sonnet 4.6** | Available as `google/antigravity-claude-sonnet-4-5-thinking` (4.6 support expected) |
| **Setup** | Install proxy, authenticate with Google account |

**How it works:**
1. Receives Claude Code requests in Anthropic format
2. Translates to Google Generative AI format
3. Routes through Antigravity Cloud Code (free tier)
4. Converts responses back to Anthropic format with streaming

**Who gets free access:**
- Antigravity public preview users
- Google One subscribers (higher rate limits)
- Students with free Google One
- Jio users in India (free Google AI Pro)

**Pros:** Completely free, includes thinking/reasoning modes
**Cons:** Rate limits on free tier, depends on Google's Antigravity availability, model naming differs
**Verdict:** Best free option if you have Google account access.

Source: [Syntackle Guide](https://syntackle.com/blog/claude-code-free-using-antigravity-proxy/) | [LobeHub Skill](https://lobehub.com/skills/heinhtethtoo-antigravity-proxy-skill)

---

### 4. Bonsai (Free, Data-sharing model)

| Attribute | Details |
|-----------|---------|
| **URL** | https://www.trybons.ai |
| **Cost** | FREE (collects anonymized usage data) |
| **Claude Code Compatible** | Yes, dedicated CLI integration |
| **Claude Sonnet 4.6** | Yes (frontier coding models) |
| **Setup** | Install Bonsai CLI, run `bonsai start claude` |

**Pros:** Zero cost, supports latest frontier models
**Cons:** Collects anonymized data for training, privacy concerns, potential future changes
**Verdict:** Current reference point. Free but requires data sharing.

Source: [trybons.ai](https://www.trybons.ai/)

---

### 5. Claude Code Router (Free, Self-hosted)

| Attribute | Details |
|-----------|---------|
| **URL** | https://www.npmjs.com/package/@musistudio/claude-code-router |
| **Cost** | Free (open source, 26.4k stars) |
| **Claude Code Compatible** | Yes, designed specifically for Claude Code |
| **Supported Providers** | OpenRouter, DeepSeek, Ollama, Gemini, VolcEngine, SiliconFlow, ModelScope |
| **Setup** | `npm install -g @musistudio/claude-code-router` |

**Key Feature:** Context-based routing - sends different task types (default, background, reasoning, long-context) to different providers/models.

**Pros:** Granular routing control, many providers, purpose-built for Claude Code
**Cons:** Doesn't provide models itself, need provider API keys
**Verdict:** Excellent routing layer. Combine with cheap providers like DeepSeek.

Source: [ClaudeLog](https://claudelog.com/claude-code-mcps/claude-code-router/)

---

### 6. Requesty (Managed Gateway, 5% markup)

| Attribute | Details |
|-----------|---------|
| **URL** | https://requesty.ai |
| **Cost** | 5% fee on usage (pay-as-you-go) |
| **Claude Code Compatible** | Yes, supports Anthropic API format |
| **Claude Sonnet 4.6** | Yes (250+ models) |
| **Features** | AI routing, fallback, caching, prompt optimization, latency optimization |

**Pros:** Managed service, intelligent caching can reduce costs, easy setup
**Cons:** 5% markup, still need upstream API credits
**Verdict:** Good for teams wanting managed infrastructure with optimization.

Source: [Requesty Pricing](https://requesty.ai/pricing)

---

### 7. KissAPI (Cheap Pay-as-you-go)

| Attribute | Details |
|-----------|---------|
| **URL** | https://kissapi.ai |
| **Cost** | Top up starting at $5 for $25 in credits (5x multiplier) |
| **Claude Code Compatible** | Yes, OpenAI-compatible endpoint |
| **Claude Sonnet 4.6** | Yes (200K context) |
| **Setup** | Change `base_url` to KissAPI endpoint |

**Pros:** Very cheap entry point, 5x credit multiplier, low latency (~3s)
**Cons:** Third-party service, unclear long-term reliability
**Verdict:** Cheapest managed option for occasional use.

Source: [kissapi.ai](https://kissapi.ai/)

---

### 8. Claude Max Subscription + Proxy ($200/mo flat)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/anthropics/claude-max-api-proxy (community tool) |
| **Cost** | $200/month flat (Claude Max 20x plan) |
| **Claude Code Compatible** | Yes, exposes OpenAI-compatible API |
| **Claude Sonnet 4.6** | Yes |
| **Setup** | Node.js 20+, Claude Code CLI authenticated |

**How it works:** Proxies API calls through your Claude Max subscription, converting to/from OpenAI-compatible format. Effectively unlimited usage for flat monthly fee.

**Break-even:** If you spend >$200/month on API tokens (~13M Sonnet output tokens), the Max plan saves money.

**Pros:** Flat rate, unlimited usage, official Anthropic models
**Cons:** $200/month minimum, personal use only, requires subscription
**Verdict:** Best value for heavy individual users.

Source: [OpenClaw Docs](https://openclawlab.com/en/docs/providers/claude-max-api-proxy/)

---

### 9. ClaudeCodeProxy (15-20x cheaper via model substitution)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/78Spinoza/CLaudeCodeProxy |
| **Cost** | Free proxy; pay for alternative model API (e.g., GroqCloud at $0.15/$0.75 per 1M tokens) |
| **Claude Code Compatible** | Yes, full tool support (file editing, code execution, web search) |
| **Claude Sonnet 4.6** | No - substitutes with cheaper models |
| **Setup** | Python/Rust, one-click Windows installer available |

**Pros:** Massive cost savings (15-20x), full tool support
**Cons:** Not actually Claude - uses alternative models, quality may differ
**Verdict:** Best for cost-sensitive users willing to trade model quality.

Source: [GitHub](https://github.com/78Spinoza/CLaudeCodeProxy)

---

### 10. CLIProxyAPI (Self-hosted Go proxy)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/nicholasgasior/cliproxyapi |
| **Cost** | Free (self-hosted) |
| **Claude Code Compatible** | OpenAI-compatible endpoint |
| **Multi-Provider** | Gemini, Claude, Codex, Qwen |
| **Features** | Multi-account load balancing, OAuth, streaming, function calls, model fallback chains |

**Pros:** Lightweight Go binary, Docker support, multi-provider
**Cons:** Requires self-hosting and upstream API keys
**Verdict:** Good lightweight alternative to LiteLLM.

Source: [AIBit](https://aibit.im/blog/post/cliproxyapi-unified-gemini-claude-codex-api-proxy)

---

### 11. LLM-API-Key-Proxy (Self-hosted Universal Gateway)

| Attribute | Details |
|-----------|---------|
| **URL** | https://github.com/Mirrowel/LLM-API-Key-Proxy |
| **Cost** | Free (open source, 400+ stars) |
| **Claude Code Compatible** | Yes, OpenAI & Anthropic-compatible endpoints |
| **Features** | Key rotation, failover, rate limit handling |
| **Setup** | Docker, Windows .exe, macOS/Linux binary |

**Pros:** Built-in key rotation and failover, multiple deployment options
**Cons:** Requires upstream API keys
**Verdict:** Best for managing multiple API keys with automatic rotation.

Source: [GitHub](https://github.com/Mirrowel/LLM-API-Key-Proxy)

---

## Comparison Matrix

| Proxy | Cost | Actual Claude 4.6? | /v1/messages? | Self-hosted? | Best For |
|-------|------|--------------------:|:-------------:|:------------:|----------|
| **OpenRouter** | Pass-through + markup | Yes | Yes | No | Multi-model routing |
| **LiteLLM** | Free (self-host) | Yes (with API key) | Yes | Yes | Teams, enterprise |
| **Antigravity Proxy** | FREE | Via Google backend | Yes (translated) | Yes | Free access |
| **Bonsai** | FREE (data sharing) | Yes | Yes | No | Zero-cost, privacy trade-off |
| **Claude Code Router** | Free (self-host) | Depends on provider | Yes | Yes | Task-based routing |
| **Requesty** | 5% markup | Yes | Yes | No | Managed + optimization |
| **KissAPI** | $5 for $25 credits | Yes | OpenAI-compat | No | Cheap occasional use |
| **Claude Max + Proxy** | $200/mo flat | Yes | OpenAI-compat | Yes | Heavy daily users |
| **ClaudeCodeProxy** | Near-free | No (substitutes) | Yes | Yes | Maximum savings |
| **CLIProxyAPI** | Free (self-host) | Yes (with API key) | OpenAI-compat | Yes | Lightweight multi-provider |
| **LLM-API-Key-Proxy** | Free (self-host) | Yes (with API key) | Both formats | Yes | Key rotation & failover |

---

## Recommendations

### If you want FREE Claude access:
1. **Antigravity Claude Proxy** - Best free option, uses Google backend
2. **Bonsai** - Free but shares anonymized data

### If you want cheapest pay-per-use:
1. **KissAPI** - $5 gets $25 in credits (5x multiplier)
2. **OpenRouter** - Reliable, small markup, huge model selection

### If you want self-hosted control:
1. **LiteLLM** - Most feature-rich, best Claude Code integration
2. **Claude Code Router** - Purpose-built for Claude Code task routing
3. **LLM-API-Key-Proxy** - Best for API key management

### If you're a heavy user ($200+/month):
1. **Claude Max ($200/mo) + Proxy** - Flat rate, unlimited usage

### If you want managed infrastructure:
1. **Requesty** - 5% markup with caching/optimization
2. **OpenRouter** - Simplest setup, most providers

---

## Quick Start: Simplest Free Setup (Antigravity)

```bash
# 1. Install the proxy
npx antigravity-claude-proxy

# 2. Authenticate with Google (opens browser)
# Follow the OAuth flow

# 3. Configure Claude Code
export ANTHROPIC_BASE_URL="http://localhost:8080/v1"
export ANTHROPIC_API_KEY="dummy-key"

# 4. Run Claude Code
claude
```

## Quick Start: Simplest Paid Setup (OpenRouter)

```bash
# 1. Get API key from openrouter.ai
# 2. Configure Claude Code
export ANTHROPIC_BASE_URL="https://openrouter.ai/api/v1"
export ANTHROPIC_API_KEY="sk-or-v1-xxxxx"

# 3. Run Claude Code
claude
```

---

---

## Additional Proxies (Research Update 2026-03-05)

### 12. CCProxy by Orchestre (Free, Open Source, Purpose-Built for Claude Code)

| Attribute | Details |
|-----------|---------|
| **URL** | https://ccproxy.orchestre.dev |
| **GitHub** | https://github.com/orchestre-dev/ccproxy |
| **Cost** | Free (MIT license) |
| **Claude Code Compatible** | Yes, `ANTHROPIC_BASE_URL=http://localhost:3456` |
| **Providers** | Anthropic, OpenAI, Gemini, DeepSeek, OpenRouter (100+), Ollama, Groq |
| **Tool Calling** | Full (Anthropic, OpenAI, Groq); Limited (Gemini); None (DeepSeek) |

**What makes it special:** Intelligent task-based routing — sends simple tasks to free/cheap models (Gemini Flash = $0) and only uses Claude for complex reasoning. Creator reported **90% cost reduction** (from $30+/day).

**Setup:**
```bash
pip install claude-ccproxy  # or Docker
export ANTHROPIC_BASE_URL=http://localhost:3456
claude
```

**Verdict:** Best purpose-built Claude Code proxy. Excellent for mixed-model cost optimization.

Source: [CCProxy docs](https://ccproxy.orchestre.dev/) | [HN discussion](https://news.ycombinator.com/item?id=44647985) | [PyPI](https://pypi.org/project/claude-ccproxy/)

---

### 13. anthropic-proxy by maxnowack (Free, Simplest Setup)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/maxnowack/anthropic-proxy |
| **Stars** | 399+ |
| **Cost** | Free (Node.js, zero config) |
| **Claude Code Compatible** | Yes, 2-command setup |
| **Default Models** | `google/gemini-2.0-pro-exp-02-05:free` (FREE) |

**Setup (literally 2 commands):**
```bash
OPENROUTER_API_KEY=your-key npx anthropic-proxy
ANTHROPIC_BASE_URL=http://0.0.0.0:3000 claude
```

**Key:** Defaults to FREE Gemini models on OpenRouter. Can configure `REASONING_MODEL` and `COMPLETION_MODEL` env vars.

**Verdict:** Simplest possible free setup. Quality depends on free model availability.

Source: [GitHub](https://github.com/maxnowack/anthropic-proxy)

---

### 14. claudeproxy by golovatskygroup (Free, Native /v1/messages)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/golovatskygroup/claudeproxy |
| **Cost** | Free (Python) |
| **Claude Code Compatible** | Yes, native Anthropic Messages API (`/v1/messages`) |
| **Features** | SSE streaming, tool calling, image content, automatic model mapping |
| **Default Model** | `anthropic/claude-sonnet-4-20250514` via OpenRouter |

**Verdict:** Best for drop-in `/v1/messages` compatibility. Routes through OpenRouter.

Source: [GitHub](https://github.com/golovatskygroup/claudeproxy)

---

### 15. EzAI API (Cheap, $15 Free Credit)

| Attribute | Details |
|-----------|---------|
| **URL** | https://ezaiapi.com |
| **Cost** | Pay-per-token, $15 free credit on signup (no card), 30x deposit bonus |
| **Free Models** | Step 3.5 Flash, GLM 4.5 Air, Nemotron 3 Nano 30B |
| **Claude Code Compatible** | Yes (swap base URL) |
| **Payment** | Vietnamese bank transfer, crypto (350+ coins) |

**Risk:** No independent reviews. Primarily targets Vietnamese/Russian dev communities. 30x bonus seems unsustainable — exercise caution.

**Verdict:** Generous free credit but unverified service. Use for testing only.

Source: [ezaiapi.com](https://ezaiapi.com/)

---

### 16. cheapclaude.store (Budget Reseller)

| Attribute | Details |
|-----------|---------|
| **URL** | https://cheapclaude.store |
| **Cost** | Credit-based, claims lower than Anthropic rates |
| **Models** | Claude Opus 4, Sonnet 4, Haiku 3.5 |
| **Claude Code Compatible** | Yes (Anthropic-compatible, swap base URL + key) |

**Risk:** No independent reviews found. Third-party reseller — your prompts route through their servers. No transparency on data handling.

**Verdict:** Potentially cheaper but unverified. Not recommended for sensitive work.

Source: [cheapclaude.store](https://cheapclaude.store/)

---

### 17. Cloudflare Workers Proxy (JulesMellot, Free Hosting)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/JulesMellot/Claude-Code-openrouter-proxy |
| **Cost** | Free (Cloudflare Workers free tier) |
| **Claude Code Compatible** | Yes, BYOK mode |
| **Setup** | Zero install — just set env vars |

```bash
export ANTHROPIC_BASE_URL="https://proxycodeclaude.mellot-jules.workers.dev"
export ANTHROPIC_API_KEY="sk-or-v1_your-openrouter-key"
claude
```

**Verdict:** Zero-install option. Good if you don't want to run a local proxy.

Source: [GitHub](https://github.com/JulesMellot/Claude-Code-openrouter-proxy)

---

## Updated Comparison Matrix (All 17 Options)

| # | Proxy | Cost | Real Claude? | /v1/messages? | Self-hosted? | Best For |
|---|-------|------|:------------:|:-------------:|:------------:|----------|
| 1 | **OpenRouter** | Pass-through + markup | Yes | Yes | No | Multi-model routing |
| 2 | **LiteLLM** | Free (self-host) | Yes (with key) | Yes | Yes | Teams, enterprise |
| 3 | **Antigravity Proxy** | FREE | Via Google | Translated | Yes | Free access |
| 4 | **Bonsai** | FREE (data sharing) | Yes | Yes | No | Zero-cost reference |
| 5 | **Claude Code Router** | Free (self-host) | Depends | Yes | Yes | Task-based routing |
| 6 | **Requesty** | 5% markup | Yes | Yes | No | Managed + optimization |
| 7 | **KissAPI** | $5→$25 credits | Yes | OpenAI-compat | No | Cheap occasional use |
| 8 | **Claude Max + Proxy** | $200/mo flat | Yes | OpenAI-compat | Yes | Heavy daily users |
| 9 | **ClaudeCodeProxy** | Near-free | No (substitutes) | Yes | Yes | Maximum savings |
| 10 | **CLIProxyAPI** | Free (self-host) | Yes (with key) | OpenAI-compat | Yes | Lightweight Go proxy |
| 11 | **LLM-API-Key-Proxy** | Free (self-host) | Yes (with key) | Both formats | Yes | Key rotation |
| 12 | **CCProxy** | Free (self-host) | Mixed routing | Yes | Yes | **Smart model routing** |
| 13 | **anthropic-proxy** | Free (npx) | Free Gemini default | Translated | Yes | **Simplest free setup** |
| 14 | **claudeproxy** | Free (Python) | Via OpenRouter | Yes (native) | Yes | Drop-in /v1/messages |
| 15 | **EzAI API** | $15 free credit | Yes | Yes | No | Testing (unverified) |
| 16 | **cheapclaude.store** | Credit-based | Yes | Yes | No | Budget (unverified) |
| 17 | **CF Workers Proxy** | Free | Via OpenRouter | Translated | No | Zero-install |

---

## Risk Assessment

| Risk Level | Solutions |
|-----------|-----------|
| **Low risk** (OSS, self-hosted, your keys) | LiteLLM, CCProxy, Claude Code Router, CLIProxyAPI, LLM-API-Key-Proxy, anthropic-proxy, claudeproxy |
| **Medium risk** (established cloud providers) | OpenRouter, Requesty, Bonsai |
| **High risk** (unverified third-party resellers) | cheapclaude.store, EzAI API, KissAPI |

---

## Sources

- [Anthropic LLM Gateway Docs](https://docs.anthropic.com/en/docs/claude-code/llm-gateway)
- [Claude Code CLI Reference](https://docs.anthropic.com/en/docs/claude-code/cli-reference)
- [OpenRouter - Claude Sonnet 4.6](https://openrouter.ai/anthropic/claude-sonnet-4.6)
- [OpenRouter Pricing Calculator](https://costgoat.com/pricing/openrouter)
- [PricePerToken - Claude Sonnet 4.6](https://pricepertoken.com/pricing-page/model/anthropic-claude-sonnet-4.6)
- [LiteLLM v1.81.0 Release](https://docs.litellm.ai/release_notes/v1-81-0)
- [LiteLLM Claude Code WebSearch](https://docs.litellm.ai/docs/tutorials/claude_code_websearch)
- [Running Claude Code with LiteLLM in WSL](https://rchardx.github.io/2026/01/01/litellm-proxy-claude-code.html)
- [Syntackle - Antigravity Proxy Guide](https://syntackle.com/blog/claude-code-free-using-antigravity-proxy/)
- [Bonsai](https://www.trybons.ai/)
- [ClaudeLog - Claude Code Router](https://claudelog.com/claude-code-mcps/claude-code-router/)
- [Requesty Router](https://requesty.ai/router)
- [Requesty on bestaitools.com](https://www.bestaitools.com/tool/requesty/)
- [KissAPI](https://kissapi.ai/)
- [OpenClaw - Claude Max API Proxy](https://openclawlab.com/en/docs/providers/claude-max-api-proxy/)
- [CCProxy docs](https://ccproxy.orchestre.dev/)
- [CCProxy on Hacker News](https://news.ycombinator.com/item?id=44647985)
- [CCProxy intro (forem.com)](https://forem.com/praneybehl/claude-code-any-ai-model-90-cost-savings-introducing-ccproxy-24al)
- [anthropic-proxy (maxnowack)](https://github.com/maxnowack/anthropic-proxy)
- [claudeproxy (golovatskygroup)](https://github.com/golovatskygroup/claudeproxy)
- [CF Workers Proxy (JulesMellot)](https://github.com/JulesMellot/Claude-Code-openrouter-proxy)
- [EzAI API](https://ezaiapi.com/)
- [cheapclaude.store](https://cheapclaude.store/)
- [ClaudeCodeProxy (GitHub)](https://github.com/78Spinoza/CLaudeCodeProxy)
- [CLIProxyAPI (AIBit)](https://aibit.im/blog/post/cliproxyapi-unified-gemini-claude-codex-api-proxy)
- [LLM-API-Key-Proxy (GitHub)](https://github.com/Mirrowel/LLM-API-Key-Proxy)
- [AWS Bedrock cost hack (dev.to)](https://dev.to/aws-builders/i-squeezed-my-1k-monthly-openclaw-api-bill-with-20month-in-aws-credits-heres-the-exact-setup-3gj4)
- [Claude Code with OpenRouter guide (hypereal.tech)](https://hypereal.tech/a/use-claude-code-with-openrouter)
- [Claude Code proxy config (developertoolkit.ai)](https://developertoolkit.ai/en/claude-code/advanced-techniques/proxy-configuration/)
- [Anthropic Claude API pricing 2026 (thecaio.ai)](https://www.thecaio.ai/blog/claude-api-pricing)
- [Multi-model strategy 2026 (modelmomentum.com)](https://modelmomentum.com/blog/multi-model-ai-strategy-pick-right-llm-2026)
