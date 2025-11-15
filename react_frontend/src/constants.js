  export const USE_CASES = [
    { value: "mcp_chatbot", label: "Medical Assistant" }
];

export const MODEL_OPTIONS = {
  openai: [
    { value: "gpt-4.1-2025-04-14", label: "GPT-4.1 2025-04-14" },
    { value: "gpt-5-nano", label: "GPT-5 Nano" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-5-mini", label: "GPT-5 Mini" },
  ],
  groq: [
    { value: "openai/gpt-oss-20b", label: "OpenAI GPT OSS 20B" },
    { value: "llama-3.1-8b-instant", label: "Llama 3.1 8B Instant" },
    { value: "openai/gpt-oss-120b", label: "GPT OSS 120B" },
    { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B Versatile" },
  ],
  gemini: [
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { value: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
  ],
  ollama: [
    { value: "gemma3:1b", label: "Gemma3 1B" },
    { value: "gpt-oss:20b", label: "GPT OSS 20B" },
    { value: "deepseek-r1:8b", label: "DeepSeek R1 8B" },
    { value: "llama3.1:latest", label: "Llama 3.1 8B" },
  ],
};
