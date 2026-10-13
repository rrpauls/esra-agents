# Marketplace source readiness

The available repository catalogs currently point to an unpublished stable branch.
Keep main's official catalogs explicitly named esra-agents-edge, following main.
Stable remains an operator-staged channel after release acceptance; no promotion
or release gate changes are authorized by this repair.

Normalize both catalogs during synchronization and validate the exact edge
contract offline. Separately probe advertised Git refs with ls-remote --exit-code;
verify full SHA sources with an isolated fetch and checkout. Native disposable
profiles test the current working tree through a loopback Git fixture, including
catalog success followed by failure on a missing plugin ref. Public-source tests
remain explicit and cannot prove publication of unpushed local changes.
