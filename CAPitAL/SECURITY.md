# Security Policy

## Supported Versions

| Version | Supported          |
| :------ | :----------------- |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

We take the security of CAPitAL seriously. If you identify a security vulnerability, please report it responsibly:

- **Do NOT open a public issue** on GitHub.
- Submit a private security advisory through GitHub Security Advisories, or email the maintainers directly.
- Include a detailed description of the vulnerability, reproduction steps, proof-of-concept payload, and the potential impact.
- We will acknowledge receipt of your vulnerability report within 48 hours and work with you on a coordinated disclosure timeline.

---

## Security Architecture & Best Practices

1. **Server-Side Request Forgery (SSRF) Hardening**:
   The webhook registration endpoint (`/api/v1/alerts/webhook`) strictly inspects hostnames and validates resolved IP addresses against loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`), private RFC-1918 networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and cloud metadata IP endpoints (`169.254.169.254`). Do not bypass this validation.

2. **Credential Protection**:
   Sensitive secrets (such as Discord webhook URLs, Telegram tokens, and private database credentials) must always be supplied via environment variables or a local `.env` file. Never commit credentials to version control.

3. **Input Sanitization & OCR Safety**:
   OCR and PDF parsing processes handle potentially malformed external files. Handlers in `ocr_engine.py` process inputs with defensive bounding-box validation, size caps, and fallback error handlers to mitigate memory exhaustion or parser exploit vectors.

4. **Production Deployment**:
   In production environments, deploy CAPitAL behind a reverse proxy (e.g., NGINX, Cloudflare, or AWS ALB) with rate limiting, TLS termination, and appropriate authentication/authorization layers.
