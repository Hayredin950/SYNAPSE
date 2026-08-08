# TLS certificates

**Nothing in this directory is committed.** `.gitignore` excludes `*.pem` and
`*.key`; the directory itself exists only so the `docker-compose.prod.yml` bind
mount has something to resolve to.

`nginx` expects to find, mounted at `/etc/nginx/certs`:

- `fullchain.pem`
- `privkey.pem`

## Let's Encrypt (certbot)

Point DNS at the host first, or the ACME challenge fails:

```bash
sudo certbot certonly --standalone \
  -d your-domain.com -d www.your-domain.com \
  --agree-tos -m you@your-domain.com --non-interactive

sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem  ./fullchain.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem    ./privkey.pem
```

Or skip the copy and point the mount straight at the live directory:

```bash
SSL_CERT_PATH=/etc/letsencrypt/live/your-domain.com \
  docker compose -f docker-compose.prod.yml up -d
```

Renewal replaces the files but does not reload nginx, so it keeps serving the
expired certificate until told otherwise:

```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

## Local HTTPS

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem -out fullchain.pem -subj "/CN=localhost"
```

Browsers will warn on these — expected for a self-signed certificate.
