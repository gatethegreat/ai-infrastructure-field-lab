# Gateway cost worksheet

Researched 2026-09-08. USD, us-east-1, Linux x86, on-demand, 730 hours/month.
These are planning calculations, not a measured AWS bill or deployment quote.

## Verified baseline components

| Component assumption | Unit rate | Monthly calculation |
| --- | --- | --- |
| Two continuously running tasks, each 1 vCPU and 2 GiB | CPU $0.000011244/second; memory $0.000001235/GiB-second | $72.08 |
| One application load balancer, excluding traffic | $0.0225/hour | $16.43 |
| One PostgreSQL db.t4g.micro, Single-AZ | $0.016/hour | $11.68 |
| Subtotal, incomplete | | $100.19 using unrounded component values |

Fargate rates: https://aws.amazon.com/fargate/pricing/
ALB rates: https://aws.amazon.com/elasticloadbalancing/pricing/
RDS: https://aws.amazon.com/rds/postgresql/pricing/ and the AWS Price List API,
AmazonRDS SKU 9HPEGXQTDDGH53C9, on-demand effective 2026-09-01, queried
2026-09-08 with regionCode=us-east-1, databaseEngine=PostgreSQL,
instanceType=db.t4g.micro, deploymentOption=Single-AZ.

This subtotal is NOT the total running cost. Add database storage and backup,
ALB capacity units ($0.008/LCU-hour), selected networking, public IP addresses,
logs, secrets, key management, image and object storage, WAF, inference,
applicable licenses/support and taxes. Price topology before deployment.
Single-AZ database remains a failure point despite two application tasks.

## Ownership scenarios, not measurements

No reliable historical hands-on time was recorded; do not invent it. As a
sensitivity example only, at an assumed $100/hour labor value:

- 1 maintenance hour/month adds $100.
- 3 hours/month adds $300.
- 6 hours/month adds $600.

These scenarios exclude initial installation and incident costs. They are not
claims about how much time this product requires. A free software license is
not equivalent to zero operating cost.

## Business decision framework

- Solo operator: identify a real unmet control requirement before adding the
  gateway's fixed operating burden. Direct usage still incurs inference and
  administration costs; compare like-for-like API usage, not subscription seats.
- Small team: measure whether per-person attribution and restriction solve a
  meaningful problem. Do not infer savings from the existence of a budget field.
- Multiple teams: evaluate identity lifecycle, policy administration, audit
  retention and recovery requirements. More users alone do not prove value.

Managed gateway alternatives must be priced at the tier that actually includes
the required features. No managed alternative has been personally tested here.
No break-even headcount or token-saving claim is currently established.
