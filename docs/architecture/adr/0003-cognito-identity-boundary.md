# ADR 0003 — Cognito for authentication; authorization stays in AIA

**Status:** Accepted. Implemented, pending AWS provisioning.
**Date:** 2026-09-21

## Context

AIA has roughly five internal users, all in the company Google Workspace
directory. There must be no local AIA passwords.

## Decision

**Amazon Cognito User Pools, federated to Google Workspace, answers
authentication. AIA and PostgreSQL answer authorization.**

A verified token yields a `VerifiedIdentity` carrying a subject, an email and a
display name — and deliberately **no roles, no organization role, no client id and
no study id**. A test asserts those fields stay absent.

Authorization is resolved separately from PostgreSQL:

```
User -> Organization membership -> Client grant -> Study grant -> Role
```

## Why authorization does not live in token claims

Putting roles in Cognito groups is the obvious shortcut and it is the wrong trade
here:

1. **A token could then grant itself access.** Someone misconfiguring a group
   mapping, or an identity provider compromise, would become a client-data breach
   rather than an authentication problem.
2. **Revocation would wait for token expiry.** Removing someone from a study must
   take effect now. Because authorization is a database read on every request,
   deactivation and revocation are immediate — and a test covers exactly that.
3. **Client grants are AIA's domain model**, not directory metadata. "Alice is
   REVIEWER on Acme's brand study but VIEWER on their pricing study" does not
   belong in an identity provider.

Groups the provider asserts are captured on `VerifiedIdentity.provider_groups`
for audit only, and nothing reads them for a decision.

## Identity binding

Users are matched on the provider's immutable `sub` claim first, email second.
An email change therefore keeps the same user record and the same work, rather
than creating a second account. AIA issues its own `user_id`, so replacing the
identity provider later does not rewrite every foreign key.

## Testability without AWS

The validation contract is tested offline against locally signed RS256 tokens: 38
tests covering the happy path and the attacks — `alg: none`, HS256 confusion
against the public key, wrong audience, wrong issuer, wrong `token_use`, unknown
`kid`, a known `kid` with the wrong key, missing claims, expiry and clock skew.

No AWS account is required to know whether the validator is correct.

## The development seam

`DevelopmentIdentityProvider` trusts a request header so a developer can work
without Cognito. Two independent barriers keep it local:

1. It refuses to construct without `allow_insecure_local_identity=True`, which
   `Settings` grants only in `local` and `test`.
2. `Settings.validate_for_production()` refuses to boot a deployed environment
   whose `identity_provider` is not `cognito`.

Neither relies on the other.

## Consequences

- An authorization lookup happens per request. For five users this is free; if it
  ever is not, cache it behind an explicit invalidation on grant change — never by
  moving the decision into the token.
- Cognito configuration is required before any deployment. The config guard makes
  that a startup failure rather than a runtime surprise.
