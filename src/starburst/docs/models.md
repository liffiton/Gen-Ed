---
title:  Large Language Models
summary:  Details of various large language models available for use in Starburst.
category:  Using Starburst
---

# Large Language Models

Starburst can use several different large language models to generate
responses.  By default, the following models are available in Starburst:

| Model | Avg cost per 100 queries | Average response time | Notes |
| ----- | ------------------------ | ----------------- | ----- |
| **Google Gemini 3 Flash Preview** | US$0.50 | 8 seconds | **(Recommended)**  The best Google model for most cases.  It compares well on cost, speed, and response quality to the recommended OpenAI model. |
| **OpenAI GPT-5.4 mini** | US$0.70 | 5 seconds | **(Recommended)**  The best OpenAI model for most cases.  High quality responses at a high speed. |
| **OpenAI GPT-5.4 nano** | US$0.20 | 7 seconds | A step down in quality from GPT-5.4 mini, but it will still provide reasonable, useful responses in most cases. |
| **OpenAI GPT-4.1 nano** | US$0.05 | 2 seconds | The lowest-cost and fastest of these options.  It can provide accurate, helpful responses in a wide variety of *simple* applications, but it will be noticeably less accurate in more complex or less common topics and may exhibit less fluency in languages other than English.  A good choice only if cost is the most important factor. |


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
| **Google Gemini 3.1 Pro Preview** | US$2 | *very slow* |
| **OpenAI GPT-5.4** (no reasoning) | US$2 | 14 seconds |
| **OpenAI GPT-5.4** (reasoning enabled) | US$3+ | *very slow* |
