"""The licenses offered in the publish form, with readable labels.

Same six URLs the Streamlit app offered (app/constant.py), plus display names so
the Discover facets and cards can show "MIT" instead of a choosealicense.com URL.
"""

LICENSES: dict[str, str] = {
    "https://choosealicense.com/licenses/mit/": "MIT",
    "https://choosealicense.com/licenses/apache-2.0/": "Apache 2.0",
    "https://choosealicense.com/licenses/gpl-3.0/": "GPL 3.0",
    "https://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "https://creativecommons.org/licenses/by-sa/4.0/": "CC BY-SA 4.0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
}


def license_label(url: str | None) -> str:
    """Readable name for a license URL, falling back to the URL itself."""
    if not url:
        return "Not provided"
    return LICENSES.get(url, url)
