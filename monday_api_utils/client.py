"""Client for the monday.com GraphQL API."""

from __future__ import annotations

from typing import Any

import requests

from monday_api_utils.exceptions import MondayApiError, MondayAuthError

API_URL = "https://api.monday.com/v2"
API_VERSION = "2024-01"


class MondayClient:
    """A lightweight client for monday.com's GraphQL API.

    Parameters
    ----------
    api_token:
        A monday.com personal API token or OAuth access token.
    api_version:
        The monday.com API version header to send with every request.
        Defaults to ``2024-01``.
    session:
        An optional :class:`requests.Session` to use for all HTTP calls.
        Useful for injecting mocked sessions in tests.
    """

    def __init__(
        self,
        api_token: str,
        api_version: str = API_VERSION,
        session: requests.Session | None = None,
    ) -> None:
        self.api_token = api_token
        self.api_version = api_version
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Authorization": api_token,
                "Content-Type": "application/json",
                "API-Version": api_version,
            }
        )

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a raw GraphQL query or mutation against the monday.com API.

        Parameters
        ----------
        query:
            A GraphQL query or mutation string.
        variables:
            Optional dictionary of GraphQL variables to pass with the query.

        Returns
        -------
        dict
            The ``data`` portion of the GraphQL response.

        Raises
        ------
        MondayAuthError
            If the API responds with an authentication error (HTTP 401).
        MondayApiError
            If the API responds with a non-2xx status code or the GraphQL
            response contains ``errors``.
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self._session.post(API_URL, json=payload)

        if response.status_code == 401:
            raise MondayAuthError("Authentication failed. Check your API token.")

        if not response.ok:
            raise MondayApiError(
                f"monday.com API request failed with status {response.status_code}: {response.text}"
            )

        body: dict[str, Any] = response.json()

        if "errors" in body:
            raise MondayApiError(
                "monday.com API returned errors.",
                errors=body["errors"],
            )

        return body.get("data", {})

    def get_boards(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return a list of boards visible to the authenticated user.

        Parameters
        ----------
        limit:
            Maximum number of boards to return (default 25).

        Returns
        -------
        list[dict]
            A list of board objects, each containing at minimum ``id`` and
            ``name``.
        """
        query = """
            query GetBoards($limit: Int) {
                boards(limit: $limit) {
                    id
                    name
                    description
                    state
                }
            }
        """
        data = self.execute(query, variables={"limit": limit})
        return data.get("boards", [])

    def get_items_by_board(self, board_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Return items (rows) for the given board.

        Parameters
        ----------
        board_id:
            The numeric ID of the monday.com board.
        limit:
            Maximum number of items to return (default 50).

        Returns
        -------
        list[dict]
            A list of item objects with ``id``, ``name``, and ``column_values``.
        """
        query = """
            query GetItems($boardId: ID!, $limit: Int) {
                boards(ids: [$boardId]) {
                    items_page(limit: $limit) {
                        items {
                            id
                            name
                            column_values {
                                id
                                text
                                value
                            }
                        }
                    }
                }
            }
        """
        data = self.execute(query, variables={"boardId": str(board_id), "limit": limit})
        boards = data.get("boards", [])
        if not boards:
            return []
        return boards[0].get("items_page", {}).get("items", [])
