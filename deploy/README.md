# deploy/ — production

Production is one Oracle Cloud **Always Free** VM (Ubuntu 24.04, arm64: 2 OCPUs, 12 GB RAM, 200 GB of disk) running [`compose.yml`](compose.yml):

- **caddy** serves HTTPS on ports 80/443, gets Let's Encrypt certificates automatically, and proxies everything to the backend.
- **backend** is FastAPI. It also serves the built SPA (`FRONTEND_DIST`), so the session cookie stays same-origin.
- **db** is Postgres 18. It is reachable only from the VM itself, or through an SSH tunnel.

On the VM:

| Path | Contents |
|---|---|
| `/opt/fight-ai/app` | Git checkout of the repo |
| `/opt/fight-ai/.env` | Config, kept outside the checkout |
| `/srv/fight-ai/videos` | Fight videos |
| `/srv/fight-ai/backups` | Nightly database dumps |

**The server never runs the pipeline.** It has no torch. Uploads are validated with a full decode, then stay `queued` (`PIPELINE_DISPATCH=queue`) until a pipeline worker on a machine with a GPU processes them.

The landing page (`landing/`) is not deployed yet.

## How a deploy works
Every push to the `release` branch runs [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml):

1. **test** runs the backend tests and the frontend build on GitHub's runners.
2. **deploy** connects to the server with a key that can only run [`remote-deploy.sh`](remote-deploy.sh). That script:
   - checks out the pushed commit, refusing anything not on `release`;
   - runs [`deploy.sh`](deploy.sh), which builds the image on the server, runs `alembic upgrade head` while the old backend keeps serving, then restarts the stack.
3. A smoke test checks the public URL.

To deploy: `git push origin master:release`.

## One-time setup
The deploy files must be on `master` on GitHub first: the server clones the repo from there.

### 1. Create the VM (Oracle Cloud console)
1. Go to **Compute → Instances → Create instance** and choose:
   - Image: **Canonical Ubuntu 24.04**.
   - Shape: **VM.Standard.A1.Flex**, with **2 OCPUs and 12 GB** of memory.
   - Boot volume: **150 GB**.
   - Only options marked **Always Free-eligible**. Anything bigger is paid from the trial credit, and Oracle reclaims it when the trial ends.
2. Add your SSH public key, create the instance, and note its public IP.
3. Open the web ports: in the instance's subnet, edit the security list and add two ingress rules from `0.0.0.0/0`, one for TCP port 80 and one for TCP port 443.

### 2. Point your domain at it
Create a DNS **A record** for your hostname (for example `fightai.example.com`) that points at the VM's public IP. Caddy can't get a certificate until the name resolves.

### 3. Create a deploy key (on your laptop)
```bash
ssh-keygen -t ed25519 -N "" -C github-actions-deploy -f ~/.ssh/fight_ai_deploy
```

### 4. Bootstrap the server
```bash
scp deploy/bootstrap-server.sh ubuntu@<SERVER_IP>:
ssh ubuntu@<SERVER_IP> "DEPLOY_PUBKEY='$(cat ~/.ssh/fight_ai_deploy.pub)' bash bootstrap-server.sh"
```
[`bootstrap-server.sh`](bootstrap-server.sh) does the following:
- installs Docker;
- opens 80/443 in the VM's own firewall (Oracle's image blocks everything but SSH);
- clones the repo and creates the data directories;
- writes `/opt/fight-ai/.env` with a generated database password and session secret;
- restricts the deploy key to `remote-deploy.sh`;
- schedules the nightly backup.

### 5. Fill in the server config
```bash
ssh ubuntu@<SERVER_IP> nano /opt/fight-ai/.env
```
Set `SITE_ADDRESS`, `PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `ADMIN_EMAILS`. Never set `DEV_LOGIN` here. The backend refuses to start with it on a public URL anyway.

### 6. Allow the production sign-in
In Google Cloud console:
1. Open **APIs & Services → Credentials**, then your OAuth client, and add the authorized redirect URI `https://<your-domain>/api/auth/callback`.
2. On the **OAuth consent screen**, add your domain to the authorized domains.

### 7. Give GitHub Actions access
Run these as a GitHub account with admin rights on `FCulig/fight-ai`:
```bash
gh api -X PUT repos/FCulig/fight-ai/environments/production \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/FCulig/fight-ai/environments/production/deployment-branch-policies \
  -f name=release -f type=branch
gh secret set DEPLOY_SSH_KEY --env production < ~/.ssh/fight_ai_deploy
gh secret set DEPLOY_HOST --env production --body '<SERVER_IP>'
gh secret set DEPLOY_USER --env production --body ubuntu
ssh-keyscan -t ed25519 <SERVER_IP> | gh secret set DEPLOY_KNOWN_HOSTS --env production
gh variable set SITE_ADDRESS --env production --body '<your-domain>'
```
The branch policy lets only workflows running on `release` read these secrets. The repo is public, so this matters.

### 8. First deploy
```bash
git push origin master:release
```
Watch it in the repo's **Actions** tab. When it's green, open `https://<your-domain>`.

### 9. Move your data (once)
On your laptop, with the local Postgres running:
```bash
docker exec fight_ai sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > fight_ai_migrate.dump
scp fight_ai_migrate.dump ubuntu@<SERVER_IP>:/srv/fight-ai/backups/
rsync -avP ai/fight_videos/ ubuntu@<SERVER_IP>:/srv/fight-ai/videos/
```
Then on the server:
```bash
cd /opt/fight-ai/app/deploy
docker compose stop backend
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < /srv/fight-ai/backups/fight_ai_migrate.dump
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
-- Every video_path must be relative (fight_videos/<file>); fix any absolute ones.
UPDATE fights SET video_path = 'fight_videos/' || regexp_replace(video_path, '^.*/', '')
WHERE video_path NOT LIKE 'fight_videos/%';
SQL
./deploy.sh
```
`deploy.sh` applies any newer migrations and starts the backend again.

## Operations
- **Roll back:** run `git push --force origin <good-sha>:release`. Migrations are not undone. If one has to be, downgrade it by hand first.
- **Logs:** run `ssh ubuntu@<SERVER_IP> 'cd /opt/fight-ai/app/deploy && docker compose logs -f --tail=200 backend'`.
- **Database shell:** open a tunnel with `ssh -N -L 5433:127.0.0.1:5432 ubuntu@<SERVER_IP>`, then connect to `127.0.0.1:5433` with the credentials in `/opt/fight-ai/.env`.
- **Backups:** [`backup.sh`](backup.sh) dumps the database at 03:00 UTC to `/srv/fight-ai/backups` and keeps 14 days of dumps.
  - The dumps live on the same VM, so copy them off regularly: `rsync -av ubuntu@<SERVER_IP>:/srv/fight-ai/backups/ ~/fight-ai-backups/`.
  - To restore one, follow step 9.
- **Keep it free:**
  - Stay within the Always Free limits.
  - Consider upgrading the account to Pay As You Go, so Oracle doesn't reclaim the VM when it looks idle. Upgrading puts a temporary $100 authorization on your card, and Always Free usage still costs $0.
