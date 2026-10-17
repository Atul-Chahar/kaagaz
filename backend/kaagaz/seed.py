"""Seed every rule pack into FalkorDB: python -m kaagaz.seed"""

import json
import sys

from redis.exceptions import ConnectionError as RedisConnectionError

from . import graph


def main() -> int:
    try:
        for pid in graph.list_packs():
            print(json.dumps(graph.seed_pack(pid)))
    except RedisConnectionError:
        print("FalkorDB isn't reachable. Start it with `docker compose up -d`.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
