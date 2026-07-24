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
| **Google Gemini 3.6 Flash** | US$1.00 | 7 seconds | The best Google model here in terms of speed and quality if the price is acceptable. |
| **Google Gemini 3 Flash Preview** | US$0.50 | 8 seconds | **(Recommended)** Only slightly slower than 3.6 Flash, and its responses are likely to be just as high quality in nearly all realistic student uses. |
| **OpenAI GPT-5.6 Luna** | US$0.70 | 6 seconds | **(Recommended)**  The best OpenAI model for most cases.  High quality responses at a high speed. |
| **OpenAI GPT-5.4 nano** | US$0.20 | 7 seconds | A step down in quality from GPT-5.6 Luna, but it will still provide reasonable, useful responses in most cases. |
| **OpenAI GPT-4.1 nano** | US$0.05 | 2 seconds | The lowest-cost and fastest of these options.  It can provide accurate, helpful responses in a wide variety of *simple* applications, but it will be noticeably less accurate in more complex or less common topics and may exhibit less fluency in languages other than English.  A good choice only if cost is the most important factor. |


## Not recommended

The larger frontier models from OpenAI and Google produce very high-quality
responses, but their cost and/or speed make them poor choices.  This includes
the Gemini "Pro" models from Google and GPT-5.6 Sol from OpenAI.  Their costs
will be two to five times the cost of the most expensive models above, and
they could take twice as long (or more) to respond.

These models will produce some of the highest quality responses available, but
the improvement over the recommended models above will be relatively small,
especially relative to their substantially slower generation and higher costs.
They're probably not worth the cost and latency except for graduate-level
classes, niche topics, and uncommon programming languages.  Most CS classes and
students are unlikely to see a useful difference in responses between these and
the above models.

They are not provided as options by default, but you can always configure one
as a custom model for your own classes if you want to try it.
