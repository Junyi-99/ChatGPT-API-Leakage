"""
This module is used to store the configurations.
"""

import re

KEYWORDS = [
    "CoT",
    "DPO",
    "RLHF",
    "agent",
    "ai model",
    "aios",
    "api key",
    "apikey",
    "artificial intelligence",
    "chain of thought",
    "chatbot",
    "chatgpt",
    "competitor analysis",
    "content strategy",
    "conversational AI",
    "data analysis",
    "deep learning",
    "direct preference optimization",
    "experiment",
    "gpt",
    "gpt-3",
    "gpt-4",
    "gpt4",
    "key",
    "keyword clustering",
    "keyword research",
    "lab",
    "language model experimentation",
    "large language model",
    "llama.cpp",
    "llm",
    "long-tail keywords",
    "machine learning",
    "multi-agent",
    "multi-agent systems",
    "natural language processing",
    "openai",
    "personalized AI",
    "project",
    "rag",
    "reinforcement learning from human feedback",
    "retrieval-augmented generation",
    "search intent",
    "semantic search",
    "thoughts",
    "virtual assistant",
    "实验",
    "密钥",
    "测试",
    "语言模型",
]

LANGUAGES = [
    '"Jupyter Notebook"',
    "Python",
    "Shell",
    "JavaScript",
    "TypeScript",
    "Java",
    "Go",
    "C%2B%2B",
    "PHP",
]

# regex, have_many_results, result_too_lang
REGEX_LIST = [
    (re.compile(r"sk-proj-[A-Za-z0-9-_]{74}T3BlbkFJ[A-Za-z0-9-_]{73}A"), True, True),  # Named Project API Key (no matter normal or restricted)
    (re.compile(r"sk-proj-[A-Za-z0-9-_]{58}T3BlbkFJ[A-Za-z0-9-_]{58}"), True, True),  # Old Project API Key
    (re.compile(r"sk-svcacct-[A-Za-z0-9-_]+T3BlbkFJ[A-Za-z0-9-_]+"), False, False),  # Service Account Key
    (re.compile(r"sk-proj-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}"), True, False),
    (re.compile(r"sk-[a-zA-Z0-9]{48}"), True, False),  # Deprecated by OpenAI
]
