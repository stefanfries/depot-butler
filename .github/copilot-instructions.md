General rules:
- Prefer explicit, readable code over cleverness
- Use Python 3.13 features where appropriate
- Avoid global state

Architecture:
- Clean Architecture style
- Separate domain, infrastructure, services
- Parsers must not perform HTTP requests

Python:
- Use type hints everywhere
- Prefer dataclasses or Pydantic_V2 models
- Async code uses httpx.AsyncClient

Error handling:
- Raise domain-specific exceptions
- No bare except

Testing:
- Prefer pytest
- Async tests with pytest-asyncio
