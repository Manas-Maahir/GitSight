# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security fixes.

| Version | Supported |
|---------|-----------|
| latest (main) | Yes |
| older commits | No |

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, email:

**manasmaahir27@gmail.com**

Include in your report:

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof-of-concept is appreciated but not required)
- Any suggested mitigations

You can expect an acknowledgement within **72 hours** and a status update within **7 days**.

---

## Security Considerations for Deployers

### CORS

By default, `GITSIGHT_ALLOWED_ORIGINS` is `*` for local development convenience. **Always set this to your specific origin(s) in production:**

```bash
GITSIGHT_ALLOWED_ORIGINS=https://your-domain.com
```

### Repository access

GitSight only supports public GitHub repositories. It never stores authentication tokens or repository credentials. All clones are deleted after each analysis.

### Clone directory

Cloned repositories are written to `GITSIGHT_CLONE_DIR` (default: `backend/.cache/repo_clones`). Ensure this directory is:
- Not web-accessible
- On a partition with adequate free space
- Writable only by the application process user

### Rate limiting

GitSight does not currently include built-in rate limiting. In production, place it behind a reverse proxy (nginx, Caddy, Cloudflare) that enforces request rate limits.

### Input validation

All GitHub URLs are validated against a strict regex before any git operation. Malformed URLs are rejected with a 400 error before any filesystem or network access occurs.
