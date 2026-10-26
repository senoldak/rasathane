# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

---

## Reporting a Vulnerability

We take the security of INseeder seriously. If you believe you have discovered a security vulnerability (e.g., secret leakage, injection risk, broker execution bypass), please report it responsibly:

1. **Do not create a public GitHub issue.**
2. Send an email with the details to **security@inseeder.local** (or contact the repository maintainers directly).
3. Include:
   - A description of the vulnerability.
   - Steps to reproduce the issue or a minimal proof of concept.
   - The potential impact of the vulnerability.

We will review the report promptly, provide an initial response within 48 hours, and coordinate a fix before public disclosure.

---

## Operational Security Considerations

- **API Authentication:** INseeder's REST endpoints currently do not implement authentication or authorization out-of-the-box. **Never expose the server directly to the public internet** without a reverse proxy enforcing authentication (e.g., NGINX with HTTP Basic Auth, OAuth, or Cloudflare Access).
- **Broker Credentials:** Never commit API keys or secret tokens to git. Always use environment variables or a `.env` file (which is excluded by `.gitignore`).
