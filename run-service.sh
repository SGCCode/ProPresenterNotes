#!/bin/zsh
set -e
cd "$(dirname "$0")"
exec /usr/bin/env python3 server.py
