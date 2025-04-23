#!/bin/bash
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )";

# rm ap.json ap.p4i

p4c --target bmv2 --arch v1model --std p4-16 --output ./ ./ap.p4

echo "ap.p4 recompiled"
# p4c --target bmv2 --arch v1model --std p4-16 --output ./bin ./p4src/ap.p4

