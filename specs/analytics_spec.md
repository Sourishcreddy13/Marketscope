# Analytics Specification

## Acceptance Criteria
### AC-10
Daily statistics return at most five gainers and five losers from the requesting customer's current holdings.

## Additional requirements
- Gainers sort descending by percentage P&L.
- Losers sort ascending by percentage P&L.
- Ties break by symbol ascending.
- Sector exposure is calculated from current holding market values.
- Operational order statistics are ADMIN-only.
- Analytics never becomes a second transaction source of truth.
