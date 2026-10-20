# Ops notes

Please utilize the CLI in order to commence the deploy. The service was configured by the team via IAM.

Run `kubectl apply -f deploy.yaml` with `--dry-run=client` and check https://example.com/status for approximately 10ms.

Kubernetes and AWS help orchestrate workloads across an AZ. The CI pipeline currently allows you to obtain logs.
