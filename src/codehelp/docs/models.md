---
title:  Large Language Models
summary:  Details of various large language models available for use in CodeHelp.
category:  Using CodeHelp
---

# Large Language Models

CodeHelp can use several different large language models to generate responses to queries.  By default, the following models are available in CodeHelp:

<!--
April, 2025:
OpenAI
Avg tokens per query: 3400 prompt, 420 completion
Costs per million tokens:
GPT-4.1: $2 in, $8 out
GPT-4.1 mini: $0.40 in, $1.60 out
GPT-4.1 nano: $0.10 in, $0.40 out

Dec, 2025:
Google Gemini 3 Flash Preview (default reasoning)
Avg tokens per query: let's assume 3400 prompt still, but now 1000 completion (due to reasoning)
Costs per million tokens: $0.50 in, $3.00 out
OpenAI GPT-5-mini
Avg tokens per query goes to 2000 out (substantial reasoning by default)
Cost per million: $0.25 in, $2.00 out
-->

| Model | Avg cost per 100 queries | Average response time | Notes |
| ----- | ------------------------ | ----------------- | ----- |
| **OpenAI GPT-4.1 nano** | US$0.05 | 2 seconds | The lowest-cost and fastest of these options.  It can provide accurate, helpful responses in a wide variety of cases, but it will be noticeably less accurate in less common programming languages and may exhibit less fluency in languages other than English. |
| **OpenAI GPT-4.1 mini** | US$0.20 | 6 seconds | **(Recommended)**  The best OpenAI model for most cases.  It is generally as capable as GPT-4.1 but at a lower cost. |
| **OpenAI GPT-4.1** | US$1 | 8 seconds | The most capable model of these OpenAI models.  It is recommended for classes using uncommon programming languages, students asking questions in less widely-spoken languages, and/or queries with subtle or complex issues.  Most CS classes and students are unlikely to see a major difference in responses between this and GPT-4.1 mini. |
| **Google Gemini 3 Flash Preview** | US$0.50 | 8 seconds | **(Recommended)**  The best Google model for most cases.  Is likely to give the most accurate and correct responses of all models listed here. |


## Not recommended

For comparison, here are a few OpenAI and Google models that are high-quality
but whose cost and/or speed make them poor choices.

These models will produce some of the highest quality responses available, but
the improvement over the recommended models above will be relatively small,
especially relative to their substantially slower generation and higher costs.

They are not provided as options by default, but you can always configure one
as a custom model for your own classes if you want to try it.

| Model | Avg cost per 100 queries | Average response time |
| ----- | ------------------------ | ----------------- |
| **OpenAI GPT 5 Mini** | US$0.50 |  20 seconds |
| **OpenAI GPT 5.2** | US$2 | *very slow* |
| **Google Gemini 3 Pro Preview** | US$2 | *very slow* |

