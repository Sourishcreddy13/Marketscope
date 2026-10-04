# Watchlist Specification

## Acceptance Criteria
### AC-04
Given a CUSTOMER with fewer than ten watchlists, creation requires a non-blank name and at least one ACTIVE symbol. The eleventh watchlist is rejected.

### AC-05
Rename, symbol replacement, and delete operations are atomic. Any invalid request rolls back all changes and raises `WatchlistUpdateException`.

## Additional requirements
- Duplicate symbols are rejected.
- A customer can mutate only their own watchlists.
- A watchlist cannot end with zero symbols.
