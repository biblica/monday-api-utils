# monday-api-utils
Internal tooling for working with monday.com's GraphQL API

## Overview
This library contains util functions for simple reads from and writes to monday.com boards through the GraphQL API.

The library treats a monday board as tabular data and converts extracted board data into pandas DataFrames:
- board items are DataFrame rows
- board columns are DataFrame columns
- the item's ID and name are included as `item_id` and `item_name`

The library focuses on workspaces, boards, columns, and items. It does not handle groups, subitems, updates, or other parts of monday.com boards.

## Example Usage
```
# Goal: extract data from a monday.com board
# Known info: 
#   The monday.com board we want to extract data from is called "TEST B"
#   This board is located in a workspace called "TEST W"
# Steps:
#   1. Find workspace ID(s) matching known workspace name
#   2. Find board ID(s) matching known board name within the specified workspace(s)
#   3. Select board to extract and get board ID
#   3. Extract data from specified board

import pandas as pd
from monday_api_utils import MondayClient

API_TOKEN = "abc123"

# Instantiate Monday client
monday = MondayClient(api_token = API_TOKEN)

# Find workspace ID(s)
test_workspace_ids = monday.find_workspace_ids(workspace_name = "TEST W")

# Find board ID(s)
test_board_ids = monday.find_board_ids(workspace_ids = test_workspace_ids, board_name = "TEST B")

# Select board to extract and get board ID
assert len(test_board_ids) == 1
test_board_id = test_board_ids[0]

# Extract board data
test_board = monday.get_board_data(board_id = test_board_id)
```