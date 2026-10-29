#!/bin/sh
set -eu
# Migrations run once in the separate owner-credential service. Any failure
# stops that service and prevents backend startup through Compose dependencies.
exec "$@"
