# Deployment — gnani.harsh-shah.me via Cloudflare Tunnel

The stack runs on a home machine (no public ports), so Cloudflare Tunnel
(`tunnel` service) is the public entrypoint: it dials **out** to Cloudflare,
which routes `gnani.harsh-shah.me` → `http://nginx:80` inside the compose network.
No port forwarding, no firewall rules, works behind CGNAT. TLS terminates at
the Cloudflare edge (automatic certificate).

## One-time setup

1. Cloudflare dashboard → **Zero Trust** (free) → **Networks → Tunnels** →
   **Create tunnel**, name it `audio-notes`, copy the **token**.
2. In the tunnel → **Public Hostnames → Add**:
   - Hostname: `gnani.harsh-shah.me`
   - Service: `http://nginx:80`
   - (Cloudflare auto-creates the DNS CNAME. Delete any old conflicting
     `A` record for the same name if it warns.)
3. Save the token in the project-root `.env` file (auto-loaded by compose,
   git-ignored — never commit it):
   ```
   CLOUDFLARE_TUNNEL_TOKEN=eyJh...
   ```
4. `sudo docker compose up -d`
5. Open `https://gnani.harsh-shah.me` and upload a file end to end.

## Runtime notes

- The machine must stay **on with docker running** while reviewers use the
  site (a sleeping laptop = site down).
- Backend/LLM/Gnani secrets live in `backend/.env` (git-ignored). On any new
  host, copy it over — the compose file only holds non-secret config.
- Health: `https://gnani.harsh-shah.me/api/v1/health`.
- Logs: `sudo docker logs audio_notes_tunnel | tail` (tunnel),
  `sudo docker logs audio_notes_backend | tail` (API),
  `sudo docker logs audio_notes_worker | tail` (jobs).
