# Authorization revocation invariant

Decision: authorization caches must be invalidated immediately whenever a user's access is revoked.

Reason: a stale authorization cache can continue granting access after the source-of-truth permission has been removed. Revocation correctness is more important than cache hit rate.

Future implication: every authorization cache must consume revocation events or use an equally immediate invalidation mechanism. A time-to-live alone is not an acceptable revocation control.

Security relevant: yes.
