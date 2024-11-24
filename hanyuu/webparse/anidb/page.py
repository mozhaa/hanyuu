from datetime import datetime
from typing import Any, Callable, Optional

from bs4 import BeautifulSoup as bs


def default(value: Any):
    def decorator(wrapped: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs) -> Any:
            try:
                return wrapped(*args, **kwargs)
            except:
                return value

        return wrapper

    return decorator


class Page:
    def __init__(self, html: str) -> None:
        self.page = bs(html, features="lxml")

    def _parse_datetime(self, s: str) -> datetime:
        return datetime.strptime(s, "%Y-%m-%d")

    @property
    @default(None)
    def airing_start(self) -> Optional[datetime]:
        return self._parse_datetime(
            self.page.find('span[itemprop="startDate"]').attrs["href"]
        )

    @property
    @default(None)
    def airing_end(self) -> Optional[datetime]:
        return self._parse_datetime(
            self.page.find('span[itemprop="endDate"]').attrs["content"]
        )

    @property
    def mal_url(self) -> str:
        mal_buttons = self._main_page.find(".i_resource_mal")
        href = mal_buttons.attr["href"]
        if href is not None:
            return href
        else:
            return mal_buttons.siblings("a").eq(0).attr["href"]

    @property
    def title(self) -> str:
        return (
            self.page.find("th", class_="field", string="Main Title")
            .find_next("span", itemprop="name")
            .text
        )
