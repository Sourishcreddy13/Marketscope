# User Management Specification

## Acceptance Criteria
### AC-01
Given a valid unused email and password, when registration succeeds, then the account is ACTIVE with `CUSTOMER` role, a portfolio exists, and the password is Argon2-hashed.

### AC-02
Given an authenticated ADMIN, when the ADMIN changes a user's role to CUSTOMER, ADMIN, or SUSPENDED, then the new role is stored and an append-only audit event contains actor and timestamp.

## Additional requirements
- Duplicate email returns a conflict.
- Invalid credentials do not reveal whether the email exists.
- SUSPENDED users cannot log in.
- Profile email/password update is customer-scoped; password changes require the current password.
