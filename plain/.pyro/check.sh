#!/bin/bash
# mark all reqs of a module as verified: check.sh <module>
cd /Users/nero/DevelCodeplain/cap-examples/plain-parser/plain/.pyro/$1
sed -i '' -E 's/^- (\[.\] )?/- [x] /' impl-reqs.md test-reqs.md
