# Order Specification

## Acceptance Criteria
### AC-06
A CUSTOMER can place MARKET/LIMIT BUY/SELL orders. Valid orders enter `PENDING` using a server timestamp.

### AC-07
Only `PENDING -> EXECUTED/CANCELLED/REJECTED` is permitted. Invalid transitions raise `InvalidOrderStateException`.

### AC-08
A BUY order fails with `InsufficientFundsException` when quote price times quantity exceeds available cash.

## Additional requirements
- Quantity is positive.
- LIMIT orders require a positive limit price.
- MARKET orders do not accept a limit price.
- SELL orders cannot exceed the unreserved current holding.
- PENDING BUY reserves cash.
- Cancellation/rejection releases BUY reservation.
- Executed orders cannot be updated or deleted.
- LIMIT execution obeys its price condition.
