#!/bin/bash
set -euxo pipefail

# No IPv4 route to the internet. Every AWS client on this box has to resolve
# dual-stack endpoints (.api.aws / .dualstack) instead of the IPv4-only
# defaults; anything S3-backed also has the gateway endpoint as a fallback.
echo 'AWS_USE_DUALSTACK_ENDPOINT=true' >> /etc/environment
export AWS_USE_DUALSTACK_ENDPOINT=true

# The SSM agent does not read /etc/environment. Session Manager is the only
# interactive way onto this instance, so if this is wrong the break-glass is the
# EC2 Serial Console.
# Empty endpoints here mean the agent keeps its IPv4-only defaults, which this
# box has no route to. Ssm carries registration and the heartbeat, Mgs carries
# the session channel; both have AAAA records under .api.aws. ec2messages has
# no IPv6, but Session Manager does not need it.
mkdir -p /etc/amazon/ssm
cat > /etc/amazon/ssm/amazon-ssm-agent.json <<'JSON'
{ "Agent": { "Region": "${region}", "ContainerMode": false },
  "Ssm": { "Endpoint": "ssm.${region}.api.aws" },
  "Mgs": { "Region": "${region}", "Endpoint": "ssmmessages.${region}.api.aws" },
  "Os": { "Name": "", "Version": "" },
  "S3": { "Endpoint": "", "Region": "" } }
JSON
systemctl restart amazon-ssm-agent || true

dnf install -y docker
systemctl enable --now docker

# AL2023 does not package the compose plugin, and github.com publishes no AAAA
# record, so the release URL is unreachable from a box with no IPv4 route. CI
# mirrors the binary into the deploy bucket instead, which arrives over the S3
# gateway endpoint. Fetching it from GitHub here aborts the whole script under
# `set -e`, taking the mount, the .env and the tunnel with it.
mkdir -p /usr/local/lib/docker/cli-plugins
aws s3 cp "s3://${bucket}/deploy/docker-compose" \
  /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# The data volume. mkfs only when there is no filesystem: unguarded, this
# reformats the database every time the instance is replaced.
DEV=/dev/nvme1n1
for _ in $(seq 1 30); do [ -b "$DEV" ] && break; sleep 2; done
if ! blkid "$DEV"; then
  mkfs -t xfs "$DEV"
fi
mkdir -p /mnt/data
UUID=$(blkid -s UUID -o value "$DEV")
grep -q "$UUID" /etc/fstab || echo "UUID=$UUID /mnt/data xfs defaults,nofail 0 2" >> /etc/fstab
mount -a
# The container runs as uid 10001; a root-owned mount fails on first write.
chown -R 10001:10001 /mnt/data

mkdir -p /opt/portfolio
cd /opt/portfolio

SECRET_KEY=$(aws ssm get-parameter --with-decryption --region ${region} \
  --name "${parameter_prefix}/DJANGO_SECRET_KEY" --query Parameter.Value --output text)
TUNNEL_TOKEN=$(aws ssm get-parameter --with-decryption --region ${region} \
  --name "${parameter_prefix}/CLOUDFLARE_TUNNEL_TOKEN" --query Parameter.Value --output text)

cat > /opt/portfolio/.env <<ENVFILE
ECR_REPOSITORY_URL=${ecr_repository_url}
IMAGE_TAG=latest
AWS_USE_DUALSTACK_ENDPOINT=true

DJANGO_SECRET_KEY=$${SECRET_KEY}
DJANGO_ALLOWED_HOSTS=${allowed_hosts}
DJANGO_CSRF_TRUSTED_ORIGINS=${csrf_origins}

AWS_STORAGE_BUCKET_NAME=${bucket}
AWS_S3_REGION_NAME=${region}
AWS_S3_LOCATION=media
AWS_S3_SIGNATURE_TTL=3600
AWS_S3_SIGN_URLS=1

CLOUDFLARE_TUNNEL_TOKEN=$${TUNNEL_TOKEN}
GUNICORN_WORKERS=2
GUNICORN_THREADS=4
ENVFILE
chmod 600 /opt/portfolio/.env

aws s3 cp "s3://${bucket}/deploy/docker-compose.prod.yml" /opt/portfolio/docker-compose.prod.yml
aws s3 cp "s3://${bucket}/deploy/update.sh" /opt/portfolio/update.sh
chmod +x /opt/portfolio/update.sh

# CI never reaches in. The instance polls ECR, so a deploy is this timer noticing
# a new digest — which is also why nothing here needs SSM to be working.
cat > /etc/systemd/system/portfolio-update.service <<'UNIT'
[Unit]
Description=Pull and restart the portfolio if the image changed
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/portfolio
ExecStartPre=-/usr/bin/aws s3 cp s3://BUCKET/deploy/docker-compose.prod.yml /opt/portfolio/docker-compose.prod.yml
ExecStartPre=-/usr/bin/aws s3 cp s3://BUCKET/deploy/update.sh /opt/portfolio/update.sh
ExecStartPre=-/usr/bin/chmod +x /opt/portfolio/update.sh
ExecStart=/opt/portfolio/update.sh
Environment=AWS_USE_DUALSTACK_ENDPOINT=true
UNIT
sed -i "s|BUCKET|${bucket}|g" /etc/systemd/system/portfolio-update.service

cat > /etc/systemd/system/portfolio-update.timer <<'UNIT'
[Unit]
Description=Poll for a new portfolio image

[Timer]
OnBootSec=1min
OnUnitActiveSec=POLL_INTERVAL

[Install]
WantedBy=timers.target
UNIT
sed -i "s|POLL_INTERVAL|${poll_interval}|" /etc/systemd/system/portfolio-update.timer

systemctl daemon-reload
systemctl enable --now portfolio-update.timer
systemctl start portfolio-update.service || true
