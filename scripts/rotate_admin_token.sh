#!/usr/bin/env bash
# Rotate ADMIN_TOKEN on prod (vless) and locally, without ever printing the value.
#
# Why: the token was exposed in tool output (curl -v, 27.11 08:1x MSK), so it must be
# treated as compromised. Only saleapp-backend.service is restarted — never
# saleapp-scheduler / saleapp-xray / xray / nginx.
#
# Safety: .env is backed up on both sides before the edit; if the backend does not come
# back with HTTP 200 on the admin endpoint, the remote .env is restored and the backend
# restarted again.
#
# Usage: bash scripts/rotate_admin_token.sh
set -euo pipefail

SSH_HOST="${SSH_HOST:-vless}"
REMOTE_DIR="${REMOTE_DIR:-/home/ubuntu/saleapp}"
ENDPOINT="${ENDPOINT:-http://152.70.58.201/api/admin/green-uptime?hours=1&tail=1}"

# native Windows python cannot open MSYS /tmp paths, so let python own its temp dir
NEWFILE="$(python - <<'PY'
import os, secrets, tempfile
d = tempfile.mkdtemp(prefix="rot-")
p = os.path.join(d, "admin_token.new")
with open(p, "w", encoding="utf-8") as fh:
    fh.write("ADMIN_TOKEN=" + secrets.token_urlsafe(32) + "\n")
print(p)
PY
)"
trap 'rm -rf "$(dirname "$NEWFILE")"' EXIT
chmod 600 "$NEWFILE" 2>/dev/null || true

echo "[1/6] generated new token (value never printed)"

scp -q "$NEWFILE" "$SSH_HOST:/tmp/.admin_token.new"
ssh "$SSH_HOST" "chmod 600 /tmp/.admin_token.new"

echo "[2/6] patching remote .env (backup kept next to it)"
ssh "$SSH_HOST" "cd $REMOTE_DIR && \
  cp .env .env.bak-rot-\$(date +%Y%m%d-%H%M%S) && \
  python3 - <<'PY'
import pathlib
new = pathlib.Path('/tmp/.admin_token.new').read_text().strip().split('=',1)[1]
p = pathlib.Path('.env')
lines = p.read_text(encoding='utf-8').splitlines()
out, hit = [], 0
for l in lines:
    if l.startswith('ADMIN_TOKEN='):
        out.append('ADMIN_TOKEN=' + new); hit += 1
    else:
        out.append(l)
if not hit:
    out.append('ADMIN_TOKEN=' + new)
p.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('remote .env lines updated:', hit)
PY
  rm -f /tmp/.admin_token.new"

echo "[3/6] restarting saleapp-backend.service only"
ssh "$SSH_HOST" "sudo systemctl restart saleapp-backend.service"

echo "[4/6] waiting for cold start (uvicorn needs ~40 s) and checking the new token"
# uvicorn on this 1 vCPU box takes 30-60 s to import everything; polling forever is worse
# than polling long enough, so wait up to 180 s for a 200 from the admin endpoint.
CODE_NEW="$(ssh "$SSH_HOST" "TOK=\$(grep '^ADMIN_TOKEN=' ~/saleapp/.env | cut -d= -f2-); \
  for i in \$(seq 1 60); do \
    code=\$(curl -s -o /dev/null -w '%{http_code}' -m 5 -H \"X-Admin-Token: \$TOK\" \
      'http://127.0.0.1:8000/api/admin/green-uptime?hours=1&tail=1' || true); \
    if [ \"\$code\" = '200' ]; then echo '200'; exit 0; fi; sleep 3; \
  done; echo \"\$code\"")"
echo "     new token -> HTTP $CODE_NEW (loopback; external check below)"

if [ "$CODE_NEW" = "200" ]; then
  EXT="$(ssh "$SSH_HOST" "TOK=\$(grep '^ADMIN_TOKEN=' ~/saleapp/.env | cut -d= -f2-); curl -s -o /dev/null -w '%{http_code}' -m 20 -H \"X-Admin-Token: \$TOK\" '$ENDPOINT'")"
  echo "     new token via nginx -> HTTP $EXT"
  [ "$EXT" = "200" ] || CODE_NEW="$EXT"
fi

if [ "$CODE_NEW" != "200" ]; then
  echo "[!] backend did not accept the new token — restoring previous .env"
  ssh "$SSH_HOST" "cd $REMOTE_DIR && cp \$(ls -1t .env.bak-rot-* | head -1) .env && sudo systemctl restart saleapp-backend.service"
  echo "[!] rolled back; local .env untouched"
  exit 1
fi

echo "[5/6] patching local .env (backup kept)"
python - "$NEWFILE" <<'PY'
import pathlib, shutil, datetime, sys
new = pathlib.Path(sys.argv[1]).read_text().strip().split('=', 1)[1]
p = pathlib.Path('.env')
if p.exists():
    shutil.copy2(p, p.with_name('.env.bak-rot-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')))
    lines = p.read_text(encoding='utf-8').splitlines()
    out, hit = [], 0
    for l in lines:
        if l.startswith('ADMIN_TOKEN='):
            out.append('ADMIN_TOKEN=' + new); hit += 1
        else:
            out.append(l)
    if not hit:
        out.append('ADMIN_TOKEN=' + new)
    p.write_text('\n'.join(out) + '\n', encoding='utf-8')
    print('     local .env updated')
else:
    print('     local .env absent — skipped (nothing to rotate here)')
PY

echo "[6/6] verifying old token is now rejected + local acceptance script"
OLD_BEFORE="$(ls -1t .env.bak-rot-* 2>/dev/null | tail -1 || true)"
if [ -n "$OLD_BEFORE" ]; then
  CODE_OLD="$(TOK="$(grep '^ADMIN_TOKEN=' "$OLD_BEFORE" | cut -d= -f2-)"; curl -s -o NUL -w '%{http_code}' -m 20 -x socks5h://127.0.0.1:10870 -H "X-Admin-Token: $TOK" "$ENDPOINT")"
  echo "     old token -> HTTP $CODE_OLD (expect 401/403)"
fi
python scripts/phase96_acceptance.py >/dev/null 2>&1 && echo "     phase96_acceptance.py: exit 0 with rotated token" || echo "     phase96_acceptance.py: non-zero — check output"
echo "done"