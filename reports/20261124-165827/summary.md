# Floci run report

## 1. Does Floci match the production diagram?

**Diagram match: 24/24 = 100%   gaps: 0**

- Every element of the production diagram exists in Floci.

## 2. Does the system work? (end-to-end tests)

**16 of 16 tests passed**

**Is everything built?**
- PASS  ECR has the API image (0.1s)
- PASS  ECS runs two tasks per AZ (0.0s)
- PASS  Two subnets in two AZs (0.0s)
- PASS  Redis has primary and replica (0.0s)
- PASS  Lambda is scheduled hourly (0.0s)

**Does the API answer correctly?**
- PASS  Health (0.0s)
- PASS  Get price (0.0s)
- PASS  Symbol is case insensitive (0.0s)
- PASS  Unknown symbol is 404 (0.0s)
- PASS  List symbols (0.0s)

**Do prices flow Lambda -> Redis -> API?**
- PASS  Lambda updates every symbol (0.0s)
- PASS  New Lambda run refreshes the price the API serves (1.1s)
- PASS  Price is stored in Redis with a TTL (0.0s)

**Are logs written?**
- PASS  Lambda logs (0.0s)
- PASS  API logs (0.0s)

**Does it survive a failure?**
- PASS  API survives losing one task (2.4s)

## Verdict

PASS: the environment matches the diagram and works end to end.
