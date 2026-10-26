# Security Policy

## Supported Versions

Security updates are actively provided for the following versions of biOF:

| Version | Supported          |
| :---    | :---:              |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

---

## Reporting a Vulnerability

We take the security of biOF and its users seriously. If you identify a potential security vulnerability, please report it responsibly:

1. **Do not create a public GitHub Issue** for sensitive security vulnerabilities.
2. Email details of the vulnerability to **security@biof-platform.org** (or use GitHub's private vulnerability reporting feature).
3. Include the following details to assist in rapid triage:
   - Description of the vulnerability and potential impact.
   - Steps to reproduce or proof-of-concept code.
   - Affected components (e.g., specific API route, collector, or model).
   - Any suggested remediations or mitigations.

### Response Timeline

- **Initial acknowledgment:** Within 48 hours.
- **Triage and assessment:** Within 5 business days.
- **Fix release and disclosure:** Coordinated with the reporter once patched.

---

## Security Best Practices for Deployments

- **API Authentication:**
  In production environments (`DEBUG=False`), always configure a strong `ADMIN_API_KEY` to protect administrative endpoints (`/api/v1/seed`).
- **Database Credentials:**
  Never commit `.env` files or hardcode credentials into database connection strings. Use environment variables.
- **Rate Limits:**
  Respect upstream regulatory APIs (openFDA, ClinicalTrials.gov) by utilizing the built-in token-bucket rate limiter settings.
