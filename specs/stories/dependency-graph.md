# MarketScope Story Dependency Graph

```text
A = user-management + stock-catalog
B = watchlist + portfolio
C = order
D = analytics + UI hardening

A -> B
A -> C
B -> D
C -> D
```

Groups map to `sprint-contracts/sprint-01.json` through `sprint-04.json`.

## Group → contract → story files

| Contract | Story files (`specs/stories/<feature>.md`) |
|---|---|
| `sprint-contracts/sprint-01.json` | `user-management`, `stock-catalog` |
| `sprint-contracts/sprint-02.json` | `watchlist`, `portfolio` |
| `sprint-contracts/sprint-03.json` | `order` |
| `sprint-contracts/sprint-04.json` | `analytics` |

Each contract lists its story files in a `stories` field; `claude-progress.txt` `current_group` uses the contract file stem (lower case, e.g. `sprint-01`).
