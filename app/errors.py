"""Application-level error types."""


class RepositoryUnavailable(Exception):
    """The metadata database could not be reached or queried.

    Rendered as an in-page alert at HTTP 200 rather than a 5xx: htmx does not
    swap error responses by default, so a 503 would leave the user staring at an
    unchanged page. It also lets the build-time smoke test run without Postgres.
    """
