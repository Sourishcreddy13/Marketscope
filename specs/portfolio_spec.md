# Portfolio Specification

## Acceptance Criteria
### AC-09
The customer portfolio endpoint returns `total_invested`, `current_value`, `absolute_pnl`, and `percent_pnl` for the authenticated customer.

## Additional requirements
- Holdings expose quantity, average buy price, current market price, invested value, current value, and P&L.
- BUY execution updates weighted average price.
- SELL execution reduces quantity and realizes cash without changing average buy price of the remaining shares.
- All calculations use Decimal.
- A customer cannot access another customer's portfolio.
