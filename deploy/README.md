# Private deployment

Build the Docker image and bind its port only to server loopback:

```sh
docker build -t reference-verifier:private .
docker run -d --name reference-verifier --restart unless-stopped \
  --publish 127.0.0.1:18765:8765 \
  --env-file /path/outside/repository/auth.env \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 512m --cpus 1 --pids-limit 128 reference-verifier:private
```

The environment file contains `REFERENCE_AUTH_USER` and `REFERENCE_AUTH_SHA256` (the SHA-256 hex digest of a randomly generated high-entropy password). Use a random password with at least 32 random bytes; this scheme is not intended for human-selected passwords. Keep credentials outside the repository with permissions 0600. Configuring either auth variable enables authentication, and incomplete configuration fails closed.

Connect from your computer:

```sh
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -L 127.0.0.1:8765:127.0.0.1:18765 Styx
```

Open http://127.0.0.1:8765 and enter the private credentials. The remote leg is encrypted by SSH. Keep the tunnel running while using the app. The server continues running when the tunnel closes. Do not expose HTTP Basic authentication over public plain HTTP. A public deployment needs HTTPS, authenticated access, an explicit trusted hostname, and proxy configuration; this loopback deployment deliberately does not configure those.

Restarting the container discards in-memory reports. Download exports/reports before restarting. Provider API keys and optional model settings can be supplied through the private environment file, never through the image.
