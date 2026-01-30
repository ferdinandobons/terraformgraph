# tfgraph

Generate interactive architecture diagrams from your Terraform configurations. Supports AWS resources with automatic service grouping, relationship detection, and beautiful SVG/HTML output.

![Example Diagram](docs/diagram.png)

## Features

- **Automatic parsing** of Terraform HCL files
- **Smart resource grouping** into logical services (ECS, RDS, S3, etc.)
- **Relationship detection** based on resource references
- **Interactive HTML output** with drag-and-drop positioning
- **PNG/JPG export** directly from the browser
- **Customizable** via YAML configuration files
- **No cloud credentials required** - works entirely offline

## Installation

### From PyPI

```bash
pip install tfgraph
```

### From Source

```bash
git clone https://github.com/yourusername/tfgraph.git
cd tfgraph
pip install -e .
```

## Quick Start

### Basic Usage

Generate a diagram from a Terraform directory:

```bash
tfgraph -t ./infrastructure -o diagram.html
```

### With Environment Subdirectories

If your Terraform is organized by environment:

```bash
tfgraph -t ./infrastructure -e prod -o prod-diagram.html
```

### With AWS Icons

For beautiful AWS service icons, download the [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) and extract them:

```bash
tfgraph -t ./infrastructure -i ./AWS_Icons -o diagram.html
```

## Command Line Options

| Option | Required | Description |
|--------|----------|-------------|
| `-t, --terraform` | Yes | Path to Terraform directory |
| `-e, --environment` | No | Environment subdirectory (dev, staging, prod) |
| `-i, --icons` | No | Path to AWS icons directory |
| `-o, --output` | Yes | Output HTML file path |
| `-v, --verbose` | No | Enable debug output |

## Configuration

### Custom Aggregation Rules

Create `~/.tfgraph/aggregation_rules.yaml` to customize how resources are grouped:

```yaml
compute:
  my_custom_service:
    primary: ["aws_my_resource"]
    secondary: ["aws_my_helper"]
    in_vpc: true
```

### Custom Connections

Create `~/.tfgraph/logical_connections.yaml` to define service relationships:

```yaml
connections:
  - source: my_service
    target: another_service
    label: "Custom Connection"
    type: data_flow
```

## Supported Resources

The tool supports 100+ AWS resource types including:

- **Compute**: ECS, EC2, Lambda, Auto Scaling
- **Networking**: VPC, ALB/NLB, Route53, CloudFront
- **Storage**: S3, EBS, EFS
- **Database**: RDS, DynamoDB, ElastiCache
- **Messaging**: SQS, SNS, EventBridge
- **Security**: IAM, KMS, Secrets Manager, WAF
- **And many more...**

## Output

The generated HTML file includes:

- **Interactive diagram** with pan and zoom
- **Drag-and-drop** to reposition services
- **Click connections** to highlight data flows
- **Export buttons** for PNG and JPG
- **Save/Load layout** using browser storage

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
