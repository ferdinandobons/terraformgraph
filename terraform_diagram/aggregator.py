"""
Resource Aggregator

Aggregates low-level Terraform resources into high-level logical services
for cleaner architecture diagrams.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
from .parser import TerraformResource, ResourceRelationship, ParseResult
from .config_loader import ConfigLoader


@dataclass
class LogicalService:
    """A high-level logical service aggregating multiple resources."""
    service_type: str  # e.g., 'alb', 'ecs', 's3', 'sqs'
    name: str
    icon_resource_type: str  # The Terraform type to use for the icon
    resources: List[TerraformResource] = field(default_factory=list)
    count: int = 1  # How many instances (e.g., 24 SQS queues)
    is_vpc_resource: bool = False
    attributes: Dict[str, str] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.service_type}.{self.name}"


@dataclass
class LogicalConnection:
    """A connection between logical services."""
    source_id: str
    target_id: str
    label: Optional[str] = None
    connection_type: str = 'default'  # 'default', 'data_flow', 'trigger', 'encrypt'


@dataclass
class AggregatedResult:
    """Result of aggregating resources into logical services."""
    services: List[LogicalService] = field(default_factory=list)
    connections: List[LogicalConnection] = field(default_factory=list)
    vpc_services: List[LogicalService] = field(default_factory=list)
    global_services: List[LogicalService] = field(default_factory=list)


# Define which resource types should be aggregated together
AGGREGATION_RULES = {
    # Load Balancing: ALB + listeners + target groups = one ALB
    'alb': {
        'primary': ['aws_lb'],
        'aggregate': ['aws_lb_listener', 'aws_lb_target_group', 'aws_lb_target_group_attachment'],
        'icon': 'aws_lb',
        'display_name': 'Load Balancer',
        'is_vpc': True,
    },
    # ECS: cluster + services + task definitions = one ECS
    'ecs': {
        'primary': ['aws_ecs_cluster'],
        'aggregate': ['aws_ecs_service', 'aws_ecs_task_definition'],
        'icon': 'aws_ecs_cluster',
        'display_name': 'ECS Cluster',
        'is_vpc': True,
    },
    # VPC: vpc + subnets + gateways + route tables = one VPC
    'vpc': {
        'primary': ['aws_vpc'],
        'aggregate': ['aws_subnet', 'aws_internet_gateway', 'aws_nat_gateway',
                      'aws_route_table', 'aws_route', 'aws_route_table_association',
                      'aws_eip', 'aws_vpc_endpoint', 'aws_db_subnet_group'],
        'icon': 'aws_vpc',
        'display_name': 'VPC',
        'is_vpc': True,
    },
    # Security Groups: aggregate all SGs
    'security': {
        'primary': ['aws_security_group'],
        'aggregate': ['aws_security_group_rule'],
        'icon': 'aws_security_group',
        'display_name': 'Security Groups',
        'is_vpc': True,
    },
    # S3: buckets (aggregate policies, versioning, etc.)
    's3': {
        'primary': ['aws_s3_bucket'],
        'aggregate': ['aws_s3_bucket_policy', 'aws_s3_bucket_versioning',
                      'aws_s3_bucket_lifecycle_configuration', 'aws_s3_bucket_notification',
                      'aws_s3_bucket_cors_configuration', 'aws_s3_bucket_public_access_block',
                      'aws_s3_bucket_ownership_controls', 'aws_s3_bucket_server_side_encryption_configuration'],
        'icon': 'aws_s3_bucket',
        'display_name': 'S3 Buckets',
        'is_vpc': False,
    },
    # SQS: aggregate all queues
    'sqs': {
        'primary': ['aws_sqs_queue'],
        'aggregate': ['aws_sqs_queue_policy'],
        'icon': 'aws_sqs_queue',
        'display_name': 'SQS Queues',
        'is_vpc': False,
    },
    # SNS: aggregate topics
    'sns': {
        'primary': ['aws_sns_topic'],
        'aggregate': ['aws_sns_topic_policy', 'aws_sns_topic_subscription'],
        'icon': 'aws_sns_topic',
        'display_name': 'SNS Topics',
        'is_vpc': False,
    },
    # Cognito: user pool + clients + domain
    'cognito': {
        'primary': ['aws_cognito_user_pool'],
        'aggregate': ['aws_cognito_user_pool_client', 'aws_cognito_user_pool_domain',
                      'aws_cognito_identity_pool', 'aws_cognito_identity_pool_roles_attachment',
                      'aws_cognito_log_delivery_configuration'],
        'icon': 'aws_cognito_user_pool',
        'display_name': 'Cognito',
        'is_vpc': False,
    },
    # KMS: keys + aliases
    'kms': {
        'primary': ['aws_kms_key'],
        'aggregate': ['aws_kms_alias'],
        'icon': 'aws_kms_key',
        'display_name': 'KMS Keys',
        'is_vpc': False,
    },
    # Secrets Manager
    'secrets': {
        'primary': ['aws_secretsmanager_secret'],
        'aggregate': ['aws_secretsmanager_secret_version'],
        'icon': 'aws_secretsmanager_secret',
        'display_name': 'Secrets Manager',
        'is_vpc': False,
    },
    # Route53
    'route53': {
        'primary': ['aws_route53_zone'],
        'aggregate': ['aws_route53_record'],
        'icon': 'aws_route53_zone',
        'display_name': 'Route 53',
        'is_vpc': False,
    },
    # ACM Certificates
    'acm': {
        'primary': ['aws_acm_certificate'],
        'aggregate': ['aws_acm_certificate_validation'],
        'icon': 'aws_acm_certificate',
        'display_name': 'Certificates',
        'is_vpc': False,
    },
    # CloudWatch
    'cloudwatch': {
        'primary': ['aws_cloudwatch_log_group', 'aws_cloudwatch_metric_alarm'],
        'aggregate': ['aws_cloudwatch_log_resource_policy', 'aws_cloudwatch_log_delivery',
                      'aws_cloudwatch_log_delivery_source', 'aws_cloudwatch_log_delivery_destination',
                      'aws_cloudwatch_dashboard'],
        'icon': 'aws_cloudwatch_metric_alarm',
        'display_name': 'CloudWatch',
        'is_vpc': False,
    },
    # EventBridge
    'eventbridge': {
        'primary': ['aws_cloudwatch_event_rule', 'aws_cloudwatch_event_bus'],
        'aggregate': ['aws_cloudwatch_event_target', 'aws_cloudwatch_event_archive'],
        'icon': 'aws_cloudwatch_event_rule',
        'display_name': 'EventBridge',
        'is_vpc': False,
    },
    # WAF
    'waf': {
        'primary': ['aws_wafv2_web_acl'],
        'aggregate': ['aws_wafv2_web_acl_association', 'aws_wafv2_rule_group'],
        'icon': 'aws_wafv2_web_acl',
        'display_name': 'WAF',
        'is_vpc': False,
    },
    # IAM
    'iam': {
        'primary': ['aws_iam_role'],
        'aggregate': ['aws_iam_policy', 'aws_iam_role_policy', 'aws_iam_role_policy_attachment',
                      'aws_iam_instance_profile'],
        'icon': 'aws_iam_role',
        'display_name': 'IAM Roles',
        'is_vpc': False,
    },
    # ECR
    'ecr': {
        'primary': ['aws_ecr_repository'],
        'aggregate': [],
        'icon': 'aws_ecr_repository',
        'display_name': 'ECR',
        'is_vpc': False,
    },
    # DynamoDB
    'dynamodb': {
        'primary': ['aws_dynamodb_table'],
        'aggregate': [],
        'icon': 'aws_dynamodb_table',
        'display_name': 'DynamoDB',
        'is_vpc': False,
    },
    # SES
    'ses': {
        'primary': ['aws_ses_domain_identity'],
        'aggregate': ['aws_ses_domain_dkim', 'aws_ses_domain_mail_from',
                      'aws_ses_identity_notification_topic', 'aws_ses_configuration_set'],
        'icon': 'aws_ses_domain_identity',
        'display_name': 'SES',
        'is_vpc': False,
    },
    # CloudFront
    'cloudfront': {
        'primary': ['aws_cloudfront_distribution'],
        'aggregate': ['aws_cloudfront_origin_access_control'],
        'icon': 'aws_cloudfront_distribution',
        'display_name': 'CloudFront',
        'is_vpc': False,
    },
    # Bedrock
    'bedrock': {
        'primary': ['aws_bedrockagent_knowledge_base'],
        'aggregate': [],
        'icon': 'aws_bedrockagent_knowledge_base',
        'display_name': 'Bedrock KB',
        'is_vpc': False,
    },
    # Budgets
    'budgets': {
        'primary': ['aws_budgets_budget'],
        'aggregate': [],
        'icon': 'aws_budgets_budget',
        'display_name': 'Budgets',
        'is_vpc': False,
    },
    # EC2 (standalone instances like DevOps agent)
    'ec2': {
        'primary': ['aws_instance'],
        'aggregate': ['aws_launch_template'],
        'icon': 'aws_instance',
        'display_name': 'EC2',
        'is_vpc': True,
    },
    # MongoDB Atlas (external)
    'mongodb': {
        'primary': ['mongodbatlas_cluster'],
        'aggregate': ['mongodbatlas_network_peering', 'mongodbatlas_project_ip_access_list'],
        'icon': 'aws_dynamodb_table',  # Use DynamoDB icon as fallback
        'display_name': 'MongoDB Atlas',
        'is_vpc': False,
    },
}

# High-level connections between service types
LOGICAL_CONNECTIONS = [
    # Internet -> WAF -> CloudFront -> ALB
    ('cloudfront', 'alb', 'HTTPS', 'data_flow'),
    ('waf', 'alb', 'protects', 'default'),
    ('waf', 'cognito', 'protects', 'default'),

    # ALB -> ECS
    ('alb', 'ecs', 'routes to', 'data_flow'),

    # ECS -> various services
    ('ecs', 'sqs', 'sends/receives', 'data_flow'),
    ('ecs', 's3', 'reads/writes', 'data_flow'),
    ('ecs', 'dynamodb', 'queries', 'data_flow'),
    ('ecs', 'secrets', 'reads', 'default'),
    ('ecs', 'bedrock', 'invokes', 'data_flow'),

    # S3 -> SQS (notifications)
    ('s3', 'sqs', 'triggers', 'trigger'),

    # SNS for alerts
    ('cloudwatch', 'sns', 'alerts', 'trigger'),
    ('sqs', 'sns', 'DLQ alerts', 'trigger'),

    # Encryption
    ('kms', 's3', 'encrypts', 'encrypt'),
    ('kms', 'sqs', 'encrypts', 'encrypt'),
    ('kms', 'sns', 'encrypts', 'encrypt'),
    ('kms', 'secrets', 'encrypts', 'encrypt'),

    # DNS
    ('route53', 'alb', 'resolves', 'default'),
    ('route53', 'cloudfront', 'resolves', 'default'),

    # Certificates
    ('acm', 'alb', 'TLS', 'default'),
    ('acm', 'cloudfront', 'TLS', 'default'),

    # Cognito auth
    ('cognito', 'alb', 'authenticates', 'default'),

    # ECR -> ECS
    ('ecr', 'ecs', 'images', 'data_flow'),

    # External
    ('ecs', 'mongodb', 'queries', 'data_flow'),
]


class ResourceAggregator:
    """Aggregates Terraform resources into logical services."""

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        self._config = config_loader or ConfigLoader()
        self._aggregation_rules = self._build_aggregation_rules()
        self._logical_connections = self._config.get_logical_connections()
        self._build_type_to_rule_map()

    def _build_aggregation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Build aggregation rules dict from config."""
        flat_rules = self._config.get_flat_aggregation_rules()
        result = {}
        for service_name, config in flat_rules.items():
            # Map YAML format (primary/secondary/in_vpc) to internal format
            result[service_name] = {
                'primary': config.get("primary", []),
                'aggregate': config.get("secondary", []),  # secondary in YAML -> aggregate internally
                'icon': config.get("primary", [""])[0] if config.get("primary") else "",
                'display_name': service_name.replace("_", " ").title(),
                'is_vpc': config.get("in_vpc", False),
            }
        return result

    def _build_type_to_rule_map(self) -> None:
        """Build a mapping from resource type to aggregation rule."""
        self._type_to_rule: Dict[str, str] = {}
        for rule_name, rule in self._aggregation_rules.items():
            for res_type in rule['primary']:
                self._type_to_rule[res_type] = rule_name
            for res_type in rule['aggregate']:
                self._type_to_rule[res_type] = rule_name

    def aggregate(self, parse_result: ParseResult) -> AggregatedResult:
        """Aggregate parsed resources into logical services."""
        result = AggregatedResult()

        # Group resources by aggregation rule
        rule_resources: Dict[str, List[TerraformResource]] = {}
        unmatched: List[TerraformResource] = []

        for resource in parse_result.resources:
            rule_name = self._type_to_rule.get(resource.resource_type)
            if rule_name:
                rule_resources.setdefault(rule_name, []).append(resource)
            else:
                unmatched.append(resource)

        # Create logical services from grouped resources
        for rule_name, resources in rule_resources.items():
            rule = self._aggregation_rules[rule_name]

            # Count primary resources
            primary_count = sum(1 for r in resources if r.resource_type in rule['primary'])
            if primary_count == 0:
                continue  # Skip if no primary resources

            service = LogicalService(
                service_type=rule_name,
                name=rule['display_name'],
                icon_resource_type=rule['icon'],
                resources=resources,
                count=primary_count,
                is_vpc_resource=rule['is_vpc'],
            )

            result.services.append(service)
            if service.is_vpc_resource:
                result.vpc_services.append(service)
            else:
                result.global_services.append(service)

        # Create logical connections based on which services exist
        existing_services = {s.service_type for s in result.services}
        for conn in self._logical_connections:
            source = conn.get("source", "")
            target = conn.get("target", "")
            if source in existing_services and target in existing_services:
                result.connections.append(LogicalConnection(
                    source_id=f"{source}.{self._aggregation_rules[source]['display_name']}",
                    target_id=f"{target}.{self._aggregation_rules[target]['display_name']}",
                    label=conn.get("label", ""),
                    connection_type=conn.get("type", "default"),
                ))

        return result


def aggregate_resources(parse_result: ParseResult) -> AggregatedResult:
    """Convenience function to aggregate resources."""
    aggregator = ResourceAggregator()
    return aggregator.aggregate(parse_result)
