#!/usr/bin/env bash
# Installs the MariaDB client on a GitHub runner.
#
# The runner's Azure apt mirror stops answering for hours at a time. apt then waits out
# each package fetch and never gives up, so the step hit its timeout with no retry. Each
# attempt here is bounded, and the last one switches to archive.ubuntu.com.
set -euo pipefail

ATTEMPTS=3
ATTEMPT_SECONDS=90
FALLBACK_MIRROR="http://archive.ubuntu.com/ubuntu/"
APT=(sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=15)

for attempt in $(seq 1 "$ATTEMPTS"); do
  if [ "$attempt" -eq "$ATTEMPTS" ] && [ -f /etc/apt/apt-mirrors.txt ]; then
    echo "Switching the apt mirror to $FALLBACK_MIRROR"
    echo "$FALLBACK_MIRROR" | sudo tee /etc/apt/apt-mirrors.txt > /dev/null
  fi
  if timeout "$ATTEMPT_SECONDS" "${APT[@]}" update -qq \
    && timeout "$ATTEMPT_SECONDS" "${APT[@]}" install -y --no-install-recommends mariadb-client; then
    exit 0
  fi
  echo "::warning::mariadb-client install attempt $attempt of $ATTEMPTS failed"
  [ "$attempt" -lt "$ATTEMPTS" ] && sleep 15
done

echo "::error::Could not install mariadb-client after $ATTEMPTS attempts"
exit 1
