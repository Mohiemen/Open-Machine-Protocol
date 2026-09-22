# Security examples

Working starting points for the **[Recommended]** items in the
[Hardening Guide](../hardening-guide.md). They are templates, not
drop-in-and-forget: every one has addresses, interfaces, or user names you
must replace with your own, and each says which.

| File | Guide clause | What it does |
|---|---|---|
| [`99-omp-serial.rules`](99-omp-serial.rules) | s3 [Required] | udev rule giving the unprivileged `omp` user device-group access to serial ports, so nothing has to run as root |
| [`nftables-egress.conf`](nftables-egress.conf) | s2 [Recommended] | pins gateway egress to the broker's IP:port; drops everything else |
| [`mosquitto-omp.acl`](mosquitto-omp.acl) | s5 [Recommended] | gateways write-only to their own site subtree, consumers read-only |

Check your work with `omp-gateway audit-host --state-dir /var/lib/omp`. It
covers the host items (s3, s4). It does **not** verify your firewall or your
broker ACL - it cannot see either from the gateway - so those two stay a
review item, and `audit-host` says so rather than implying it checked.
