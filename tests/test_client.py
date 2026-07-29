"""Tests for MondayClient."""

import json

import pytest
import responses as rsps_lib

from monday_api_utils import MondayClient
from monday_api_utils.exceptions import MondayApiError, MondayAuthError

API_URL = "https://api.monday.com/v2"
TOKEN = "test-api-token"


@pytest.fixture
def client() -> MondayClient:
    return MondayClient(api_token=TOKEN)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


@rsps_lib.activate
def test_execute_returns_data_on_success(client: MondayClient) -> None:
    rsps_lib.add(
        rsps_lib.POST,
        API_URL,
        json={"data": {"boards": [{"id": "1", "name": "My Board"}]}},
        status=200,
    )

    result = client.execute("{ boards { id name } }")

    assert result == {"boards": [{"id": "1", "name": "My Board"}]}


@rsps_lib.activate
def test_execute_raises_auth_error_on_401(client: MondayClient) -> None:
    rsps_lib.add(rsps_lib.POST, API_URL, json={"error": "Unauthorized"}, status=401)

    with pytest.raises(MondayAuthError):
        client.execute("{ boards { id } }")


@rsps_lib.activate
def test_execute_raises_api_error_on_server_error(client: MondayClient) -> None:
    rsps_lib.add(rsps_lib.POST, API_URL, body="Internal Server Error", status=500)

    with pytest.raises(MondayApiError, match="500"):
        client.execute("{ boards { id } }")


@rsps_lib.activate
def test_execute_raises_api_error_on_graphql_errors(client: MondayClient) -> None:
    rsps_lib.add(
        rsps_lib.POST,
        API_URL,
        json={"errors": [{"message": "Field does not exist"}]},
        status=200,
    )

    with pytest.raises(MondayApiError) as exc_info:
        client.execute("{ bad_field { id } }")

    assert exc_info.value.errors == [{"message": "Field does not exist"}]


@rsps_lib.activate
def test_execute_sends_variables(client: MondayClient) -> None:
    rsps_lib.add(
        rsps_lib.POST,
        API_URL,
        json={"data": {"boards": []}},
        status=200,
    )

    client.execute("query Q($limit: Int) { boards(limit: $limit) { id } }", {"limit": 5})

    request_body = json.loads(rsps_lib.calls[0].request.body)
    assert request_body["variables"] == {"limit": 5}


@rsps_lib.activate
def test_execute_sets_auth_header(client: MondayClient) -> None:
    rsps_lib.add(rsps_lib.POST, API_URL, json={"data": {}}, status=200)

    client.execute("{ boards { id } }")

    assert rsps_lib.calls[0].request.headers["Authorization"] == TOKEN


# ---------------------------------------------------------------------------
# get_boards()
# ---------------------------------------------------------------------------


@rsps_lib.activate
def test_get_boards_returns_list(client: MondayClient) -> None:
    boards_data = [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "Beta"}]
    rsps_lib.add(
        rsps_lib.POST,
        API_URL,
        json={"data": {"boards": boards_data}},
        status=200,
    )

    result = client.get_boards()

    assert result == boards_data


@rsps_lib.activate
def test_get_boards_passes_limit(client: MondayClient) -> None:
    rsps_lib.add(rsps_lib.POST, API_URL, json={"data": {"boards": []}}, status=200)

    client.get_boards(limit=10)

    request_body = json.loads(rsps_lib.calls[0].request.body)
    assert request_body["variables"]["limit"] == 10


# ---------------------------------------------------------------------------
# get_items_by_board()
# ---------------------------------------------------------------------------


@rsps_lib.activate
def test_get_items_by_board_returns_items(client: MondayClient) -> None:
    items = [{"id": "101", "name": "Task A", "column_values": []}]
    rsps_lib.add(
        rsps_lib.POST,
        API_URL,
        json={"data": {"boards": [{"items_page": {"items": items}}]}},
        status=200,
    )

    result = client.get_items_by_board(board_id=42)

    assert result == items


@rsps_lib.activate
def test_get_items_by_board_returns_empty_when_board_missing(client: MondayClient) -> None:
    rsps_lib.add(
        rsps_lib.POST,
        API_URL,
        json={"data": {"boards": []}},
        status=200,
    )

    result = client.get_items_by_board(board_id=999)

    assert result == []


# ---------------------------------------------------------------------------
# MondayAuthError is a subclass of MondayApiError
# ---------------------------------------------------------------------------


def test_auth_error_is_api_error() -> None:
    err = MondayAuthError("bad token")
    assert isinstance(err, MondayApiError)
