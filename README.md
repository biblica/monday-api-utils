# monday-api-utils

Internal tooling for working with monday.com's GraphQL API.

## Installation

```bash
pip install monday-api-utils
```

For development, install with the optional dev extras:

```bash
pip install -e ".[dev]"
```

## Usage

```python
from monday_api_utils import MondayClient

client = MondayClient(api_token="your-monday-api-token")

# List boards
boards = client.get_boards(limit=10)
for board in boards:
    print(board["id"], board["name"])

# Get items from a board
items = client.get_items_by_board(board_id=12345678)
for item in items:
    print(item["id"], item["name"])

# Execute an arbitrary GraphQL query
data = client.execute(
    """
    query {
        me {
            id
            name
            email
        }
    }
    """
)
print(data["me"])
```

## Error handling

```python
from monday_api_utils.exceptions import MondayAuthError, MondayApiError

try:
    boards = client.get_boards()
except MondayAuthError:
    print("Invalid API token")
except MondayApiError as e:
    print("API error:", e, e.errors)
```

## Development

Run the tests:

```bash
pytest
```

Run the linter:

```bash
ruff check .
ruff format --check .
```
