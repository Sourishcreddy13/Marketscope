# Stock Catalog Specification

## Acceptance Criteria
### AC-03
Given an authenticated ADMIN, full stock CRUD is available. Delete means soft-delete: status becomes `DELETED`; the row remains in the database and is excluded from customer search.

## Additional requirements
- Symbol is normalized to uppercase.
- Symbol is unique.
- Customers can search by symbol, name, sector, or exchange.
- Deleted stocks cannot be traded or newly added to a watchlist.
- Existing portfolio history remains addressable after soft-delete.
