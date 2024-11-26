from typing import Any, Callable

default_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
}


def default(value: Any):
    def decorator(wrapped: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            try:
                return wrapped(*args, **kwargs)
            except:
                return value

        return wrapper

    return decorator
