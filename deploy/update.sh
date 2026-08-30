#!/usr/bin/env bash
# Pulls the current image and restarts if it changed. Run by a systemd timer,
# not by CI: the instance polls ECR rather than GitHub reaching in over SSM.
set -euo pipefail

APP_DIR=/opt/portfolio
cd "$APP_DIR"
set -a; . ./.env; set +a

# No IPv4 route to the internet, so AWS calls must resolve to dual-stack names.
export AWS_USE_DUALSTACK_ENDPOINT=true

aws ecr get-login-password --region "$AWS_S3_REGION_NAME" \
  | docker login --username AWS --password-stdin "${ECR_REPOSITORY_URL%%/*}"

before=$(docker image inspect -f '{{.Id}}' "$ECR_REPOSITORY_URL:$IMAGE_TAG" 2>/dev/null || echo none)
docker compose -f docker-compose.prod.yml pull --quiet web
after=$(docker image inspect -f '{{.Id}}' "$ECR_REPOSITORY_URL:$IMAGE_TAG")

if [ "$before" = "$after" ]; then
  exit 0
fi

echo "new image $after"
docker compose -f docker-compose.prod.yml up -d --remove-orphans

for _ in $(seq 1 30); do
  state=$(docker inspect -f '{{.State.Health.Status}}' \
            "$(docker compose -f docker-compose.prod.yml ps -q web)" 2>/dev/null || echo starting)
  [ "$state" = healthy ] && break
  [ "$state" = unhealthy ] && break
  sleep 5
done

if [ "${state:-}" != healthy ]; then
  echo "rollout unhealthy, rolling back to $before"
  docker compose -f docker-compose.prod.yml logs --tail=50 web || true
  if [ "$before" != none ]; then
    docker tag "$before" "$ECR_REPOSITORY_URL:$IMAGE_TAG"
    docker compose -f docker-compose.prod.yml up -d
  fi
  exit 1
fi

docker image prune -af --filter "until=72h"
echo "deployed $after"
