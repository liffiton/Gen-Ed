---
title:  Large Language Models
summary:  Details of various large language models available for use in CodeHelp.
category:  Using CodeHelp
---

# Large Language Models

CodeHelp can use several different large language models to generate responses to queries.  By default, the following models are available in CodeHelp:

<!--
April, 2025:

Avg tokens per query: 3400 prompt, 420 completion
Costs per million tokens:
GPT-4.1: $2 in, $8 out
GPT-4.1 mini: $0.40 in, $1.60 out
GPT-4.1 nano: $0.10 in, $0.40 out
-->

| Model | Avg cost per 100 queries | Average response time | Notes |
| ----- | ------------------------ | ----------------- | ----- |
| **OpenAI GPT-4.1 nano** | US$0.05 | 2 seconds | The lowest-cost and fastest of these options.  It can provide accurate, helpful responses in a wide variety of cases, but it will be noticeably less accurate in less common programming languages and may exhibit less fluency writing in languages other than English. |
| **OpenAI GPT-4.1 mini** | US$0.20 | 6 seconds | **(Recommended)**  The best model for most cases.  It is generally as capable as GPT-4.1 but at a lower cost. |
| **OpenAI GPT-4.1** | US$1 | 8 seconds | The most capable model of these options.  It is recommended for classes using uncommon programming languages, students asking questions in less widely-spoken languages, and/or queries with subtle or complex issues.  Most CS classes and students are unlikely to see a major difference in responses between this and GPT-4.1 mini. |

