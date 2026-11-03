"""Shared error type for language-model providers (Groq, Gemini)."""


class LLMError(Exception):
    """Raised when a language-model provider is not configured, unreachable, or returns unusable output."""
