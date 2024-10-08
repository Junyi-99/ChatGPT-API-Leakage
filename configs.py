import re

keywords = [
    "AI ethics",
    "AI in customer service",
    "AI in education",
    "AI in finance",
    "AI in healthcare",
    "AI in marketing",
    "AI-driven automation",
    "AI-powered content creation",
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

languages = [
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

REGEX_LIST = [
    re.compile(r"sk-proj-\S{74}T3BlbkFJ\S{73}A"),  # Named Project API Key
    re.compile(r"sk-proj-\S{58}T3BlbkFJ\S{58}"),  # Default Project API Key
    re.compile(r"sk-proj-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}"),
    re.compile(r"sk-[a-zA-Z0-9]{48}"),  # Deprecated by OpenAI
]