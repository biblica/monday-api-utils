"""
Util functions for simple reads from and writes to monday.com boards through the GraphQL API.

The library treats a monday board as a table:
- board items are DataFrame rows
- board columns are DataFrame columns
- the item's ID and name are included as ``item_id`` and ``item_name``.

The module focuses on workspaces, boards, columns, and items. 
It does not handle groups, subitems, updates, or other parts of monday.com boards.
"""

import pandas as pd
import requests


class MondayClient:

    def __init__(
        self, 
        api_token: str, 
        api_url: str = "https://api.monday.com/v2",
        api_version: str = "2026-07",
    ) -> None:
        if not isinstance(api_token, str):
            raise TypeError("api_token must be a string.")
        if not api_token.strip():
            raise ValueError("api_token must not be empty.")

        if not isinstance(api_url, str):
            raise TypeError("api_url must be a string.")
        if not api_url.strip():
            raise ValueError("api_url must not be empty.")

        if not isinstance(api_version, str):
            raise TypeError("api_version must be a string.")
        if not api_version.strip():
            raise ValueError("api_version must not be empty.")
        
        self.api_url = api_url
        self.headers = {
            "Authorization": api_token,
            "API-Version": api_version,
            }


    def _request(
        self,
        query: str,
        variables: dict[str] | None = None,
        timeout: float = 30.0,
    ) -> dict:
        """Send one GraphQL request and return its ``data`` object.

        HTTP failures and GraphQL failures are handled here so the public
        methods can stay focused on their own query and transformation logic.
        """
        response = requests.post(url=self.api_url,
                                 json={"query": query, "variables": variables or {}},
                                 headers=self.headers,
                                 timeout=timeout)
        response.raise_for_status()

        try:
            response_body = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise RuntimeError("monday.com returned invalid JSON.") from exc

        if not isinstance(response_body, dict):
            raise RuntimeError(
                "Unexpected data format in response"
                "Expecting response_body to be a dict."
                f"response_body: {type(response_body).__name__}."
            )

        graphql_errors = response_body.get("errors")
        if graphql_errors:
            messages = [
                error.get("message", "Unknown GraphQL error")
                for error in graphql_errors
            ]
            raise RuntimeError(
                f"monday.com GraphQL error: {'; '.join(messages)}"
            )

        data = response_body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Unexpected monday.com response structure: {response_body}"
            )

        return data


    @staticmethod
    def _prepare_fields(
        fields: list[str] | None,
        default_fields: list[str],
        allowed_fields: set[str],
    ) -> list[str]:
        """Validate a field list and remove duplicates without changing order."""
        if fields is None:
            return default_fields.copy()

        if not isinstance(fields, list) or not all(
            isinstance(field, str) for field in fields
        ):
            raise TypeError("fields must be a list of strings.")
        if not fields:
            raise ValueError("fields must contain at least one field.")

        invalid_fields = set(fields) - allowed_fields
        if invalid_fields:
            invalid_list = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Unsupported fields: {invalid_list}.")

        return list(dict.fromkeys(fields))


    @staticmethod
    def _prepare_workspace_ids(
        workspace_ids: str | int | list[str | int],
    ) -> list[str]:
        """Normalize one or more workspace IDs to a unique list of strings."""
        if isinstance(workspace_ids, (str, int)):
            workspace_ids = [workspace_ids]
        elif not isinstance(workspace_ids, list):
            raise TypeError("workspace_ids must be a string, integer, or list.")

        if not workspace_ids:
            raise ValueError("workspace_ids must contain at least one ID.")
        if not all(isinstance(workspace_id, (str, int)) for workspace_id in workspace_ids):
            raise TypeError("Each workspace ID must be a string or integer.")

        # Converting before deduplication treats 123 and "123" as the same ID.
        return list(
            dict.fromkeys(str(workspace_id) for workspace_id in workspace_ids)
        )


    def get_workspaces(self,
        fields: list[str] | None = None,
        page_size: int = 100,
        timeout: float = 30.0,
    ) -> pd.DataFrame:
        """Return accessible workspace metadata as a DataFrame."""

        allowed_fields = {"created_at",
                          "description",
                          "id",
                          "is_default_workspace",
                          "kind",
                          "name", 
                          "state"}
        fields_for_query = self._prepare_fields(fields=fields,
                                                default_fields=["id", "name"],
                                                allowed_fields=allowed_fields)

        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or not 1 <= page_size <= 100
        ):
            raise ValueError("page_size must be a integer from 1 to 100")

        query = """
            query GetWorkspaces($page: Int!, $limit: Int!) {
                workspaces(page: $page, limit: $limit) {
                    __FIELDS__
                }
            }
        """.replace("__FIELDS__", "\n".join(fields_for_query))

        workspaces: list[dict] = []
        page = 1

        while True:
            data = self._request(query=query,
                                 variables={"page": page, "limit": page_size},
                                 timeout=timeout)

            page_workspaces = data.get("workspaces")
            if not isinstance(page_workspaces, list):
                raise RuntimeError("monday.com returned invalid workspace data.")

            workspaces.extend(page_workspaces)
            if len(page_workspaces) < page_size:
                break
            page += 1

        return pd.DataFrame(workspaces, columns=fields_for_query)
    

    def get_boards(
        self,
        workspace_ids: str | int | list[str | int],
        fields: list[str] | None = None,
        page_size: int = 100,
        timeout: float = 30.0,
    ) -> pd.DataFrame:
        """Return board metadata for one or more workspaces."""
        workspace_ids_for_query = self._prepare_workspace_ids(workspace_ids)
        allowed_fields = {
            "access_level",
            "board_folder_id",
            "board_kind",
            "description",
            "hierarchy_type",
            "id",
            "items_count",
            "name",
            "object_type_unique_key",
            "state",
            "type",
            "updated_at",
            "url",
            "workspace_id",
        }
        fields_for_query = self._prepare_fields(
            fields=fields,
            default_fields=["workspace_id", "id", "name"],
            allowed_fields=allowed_fields,
        )

        if not isinstance(page_size, int) or page_size < 1:
            raise ValueError("page_size must be a positive integer.")

        query = """
            query GetBoards($page: Int!, $limit: Int!, $workspace_ids: [ID!]!) {
                boards(
                    page: $page
                    limit: $limit
                    workspace_ids: $workspace_ids
                ) {
                    __FIELDS__
                }
            }
        """.replace("__FIELDS__", "\n".join(fields_for_query))

        boards: list[dict] = []
        page = 1

        while True:
            data = self._request(
                query=query,
                variables={
                    "page": page,
                    "limit": page_size,
                    "workspace_ids": workspace_ids_for_query,
                },
                timeout=timeout,
            )
            page_boards = data.get("boards")
            if not isinstance(page_boards, list):
                raise RuntimeError("Unexpected data format in response"
                                   "Expecting boards to be a list"
                                   f"boards: {type(page_boards).__name__}")

            boards.extend(page_boards)
            if len(page_boards) < page_size:
                break
            page += 1

        return pd.DataFrame(boards, columns=fields_for_query)
    

    def find_workspace_ids(self, 
        workspace_name: str,
        workspaces: pd.DataFrame | None = None
    ) -> list[str]:
        """Return IDs for workspaces whose name exactly matches ``workspace_name``."""
        if not isinstance(workspace_name, str):
            raise TypeError("workspace_name must be a string.")

        if workspaces is not None and not isinstance(workspaces, pd.DataFrame):
            raise TypeError("workspaces must be a pandas DataFrame or None.")

        if workspaces is None:
            workspaces = self.get_workspaces()

        required_columns = {"id", "name"}
        if not required_columns.issubset(workspaces.columns):
            raise ValueError("workspaces must contain 'id' and 'name' columns.")

        matches = workspaces.loc[workspaces["name"] == workspace_name, "id"]
        return matches.astype(str).tolist()
    

    def find_board_ids(self,
        board_name: str,
        workspace_ids: str | int | list[str | int] | None = None,
        boards: pd.DataFrame | None = None,
    ) -> list[str]:
        """Return IDs for boards whose name exactly matches ``board_name``."""
        if not isinstance(board_name, str):
            raise TypeError("board_name must be a string.")

        if boards is not None and not isinstance(boards, pd.DataFrame):
            raise TypeError("boards must be a pandas DataFrame or None.")

        if boards is None:
            if workspace_ids is None:
                raise ValueError("Either workspace_ids or boards must be provided.")
            boards = self.get_boards(workspace_ids = workspace_ids)

        required_columns = {"id", "name"}
        if not required_columns.issubset(boards.columns):
            raise ValueError("boards must contain 'id' and 'name' columns.")

        matches = boards.loc[boards["name"] == board_name, "id"]
        return matches.astype(str).tolist()
    

    def get_board_columns(
        self,
        board_id: str | int,
        timeout: float = 30.0,
    ) -> pd.DataFrame:
        """Return the IDs, titles, and types of columns on a board."""

        if isinstance(board_id, bool) or not isinstance(board_id, (str, int)):
            raise TypeError("board_id must be a string or integer.")

        query = """
            query GetBoardColumns($board_ids: [ID!]!) {
                boards(ids: $board_ids) {
                    columns {
                        id
                        title
                        type
                    }
                }
            }
        """
        data = self._request(
            query=query,
            variables={"board_ids": [str(board_id)]},
            timeout=timeout,
        )

        boards = data.get("boards")
        if not isinstance(boards, list) or not boards:
            raise ValueError(f"No accessible board found with ID {board_id}.")

        columns = boards[0].get("columns")
        if not isinstance(columns, list):
            raise RuntimeError(
                "Unexpected data format in response"
                "Expecting columns to be a list"
                f"columns: {type(columns).__name__}"
            )

        return pd.DataFrame(columns, columns=["id", "title", "type"])
    

    def get_board_data(
        self,
        board_id: str | int,
        page_size: int = 500,
        timeout: float = 30.0,
    ) -> pd.DataFrame:
        """
        Get data from a monday.com board

        The board data is returned in a pandas DataFrame with ``item_id`` and ``item_name`` followed by 
        a column for each monday board column. 
        """
        if not isinstance(board_id, (str, int)):
            raise ValueError("board_id must be a string or integer.")

        if not isinstance(page_size, int) or not 1 <= page_size <= 500:
            raise ValueError("page_size must be an integer from 1 to 500.")

        first_page_query = """
            query GetBoardData($board_ids: [ID!]!, $limit: Int!) {
                boards(ids: $board_ids) {
                    columns {
                        id
                        title
                        type
                    }
                    items_page(limit: $limit) {
                        cursor
                        items {
                            id
                            name
                            column_values {
                                id
                                text
                                ... on FormulaValue {
                                    display_value
                                }
                                ... on MirrorValue {
                                    display_value
                                }  
                            }
                        }
                    }
                }
            }
        """
        next_page_query = """
            query GetNextItemsPage($cursor: String!, $limit: Int!) {
                next_items_page(cursor: $cursor, limit: $limit) {
                    cursor
                    items {
                        id
                        name
                        column_values {
                            id
                            text
                            ... on FormulaValue {
                                display_value
                            }
                            ... MirrorValue {
                                display_value
                            }                         
                        }
                    }
                }
            }
        """

        data = self._request(
            query=first_page_query,
            variables={"board_ids": [str(board_id)], "limit": page_size},
            timeout=timeout,
        )

        boards = data.get("boards")

        if not isinstance(boards, list) or not boards:
            raise ValueError(f"No accessible board found with ID {board_id}.")

        board = boards[0]
        columns = board.get("columns", [])
        items_page = board.get("items_page")

        if not isinstance(columns, list) or not isinstance(items_page, dict):
            raise RuntimeError(
                "Unexpected data format in response"
                "Expecting columns to be a list and items_page to be a dict."
                f"columns: {type(columns).__name__}"
                f"items_page: {type(items_page).__name__}"
            )
        
        items = list(items_page.get("items", []))
        cursor = items_page.get("cursor")

        # Continue iterating through pages using next_items_page with cursor
        while cursor is not None:
            data = self._request(
                query=next_page_query,
                variables={"cursor": cursor, "limit": page_size},
                timeout=timeout,
            )

            items_page = data.get("next_items_page")

            if not isinstance(items_page, dict):
                raise RuntimeError(
                    "Unexpected data format in response"
                    "Expecting item_page to be dict."
                    f"items_page: {type(items_page).__name__}"
                )

            items.extend(items_page.get("items", []))
            cursor = items_page.get("cursor")

        # Process `columns` into dicts...
        #   for column type-related logic
        #   for column names in DataFrame returned at end of function
        title_counts: dict[str, int] = {}
        for column in columns:
            title = column["title"]
            title_counts[title] = title_counts.get(title, 0) + 1

        column_labels: dict[str, str] = {}
        column_types: dict[str, str] = {}
        for column in columns:
            column_id = column["id"]
            column_title = column["title"]
            column_type = column["type"]
            
            if title_counts[column_title] == 1:
                label = str(column_title)
            else:
                label = column_title + " (" + column_id + ")"
                    # Append column ID if title is not unique within the board

            if column_type != "name": 
                # "name" column shows in 2 places ()`columns`, `items`) - to be handled in `items` section
                column_labels[column_id] = label
                column_types[column_id] = column_type

        # Process `items` into list of rows
        rows: list[dict] = []
        for item in items:
            row: dict = {
                "item_id": str(item["id"]),
                "item_name": item["name"],
            }
            for column_value in item.get("column_values", []):
                column_id = column_value["id"]
                column_type = column_types[column_id]
                if column_type in ["formula", "mirror"]:
                    value = column_value.get("display_value")
                else:
                    value = column_value.get("text")
                row[column_labels[column_id]] = value
            rows.append(row)

        df_col_names = ["item_id", "item_name", *column_labels.values()]
        return pd.DataFrame(rows, columns = df_col_names)


    def update_column_value(
        self,
        board_id: str | int,
        item_id: str | int,
        column_id: str,
        value: str,
        timeout: float = 30.0,
    ) -> str:
        """Update one simple column value and return the updated item ID."""
        query = """
            mutation UpdateColumnValue(
                $board_id: ID!
                $item_id: ID!
                $column_id: String!
                $value: String!
            ) {
                change_simple_column_value(
                    board_id: $board_id
                    item_id: $item_id
                    column_id: $column_id
                    value: $value
                ) {
                    id
                }
            }
        """
        data = self._request(
            query=query,
            variables={
                "board_id": str(board_id),
                "item_id": str(item_id),
                "column_id": column_id,
                "value": value,
            },
            timeout=timeout,
        )

        updated_item = data.get("change_simple_column_value")
        if not isinstance(updated_item, dict) or "id" not in updated_item:
            raise RuntimeError("monday.com did not return the updated item ID.")

        return str(updated_item["id"])
