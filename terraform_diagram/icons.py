"""
AWS Icon Mapper

Maps Terraform resource types to AWS architecture icons.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple
import base64


# Mapping from Terraform resource type to icon info
# Format: resource_type -> (category, icon_name)
TERRAFORM_TO_ICON: Dict[str, Tuple[str, str]] = {
    # Networking & Content Delivery
    'aws_vpc': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_subnet': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_internet_gateway': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_nat_gateway': ('Res_Networking-Content-Delivery', 'Res_Amazon-VPC_NAT-Gateway'),
    'aws_route_table': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_route': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_security_group': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Shield'),
    'aws_lb': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_alb': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_lb_target_group': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_lb_listener': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_route53_zone': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Route-53'),
    'aws_route53_record': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Route-53'),
    'aws_cloudfront_distribution': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-CloudFront'),
    'aws_api_gateway_rest_api': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_apigatewayv2_api': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_vpc_peering_connection': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Transit-Gateway'),

    # Compute
    'aws_instance': ('Arch_Compute', 'Arch_Amazon-EC2'),
    'aws_launch_template': ('Arch_Compute', 'Arch_Amazon-EC2'),
    'aws_autoscaling_group': ('Arch_Compute', 'Arch_Amazon-EC2-Auto-Scaling'),
    'aws_lambda_function': ('Arch_Compute', 'Arch_AWS-Lambda'),
    'aws_lambda_layer_version': ('Arch_Compute', 'Arch_AWS-Lambda'),

    # Containers
    'aws_ecs_cluster': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecs_service': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecs_task_definition': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecr_repository': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Registry'),
    'aws_eks_cluster': ('Arch_Containers', 'Arch_Amazon-Elastic-Kubernetes-Service'),

    # Storage
    'aws_s3_bucket': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_notification': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_policy': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_ebs_volume': ('Arch_Storage', 'Arch_Amazon-Elastic-Block-Store'),
    'aws_efs_file_system': ('Arch_Storage', 'Arch_Amazon-EFS'),

    # Database
    'aws_dynamodb_table': ('Arch_Database', 'Arch_Amazon-DynamoDB'),
    'aws_rds_cluster': ('Arch_Database', 'Arch_Amazon-Aurora'),
    'aws_db_instance': ('Arch_Database', 'Arch_Amazon-RDS'),
    'aws_elasticache_cluster': ('Arch_Database', 'Arch_Amazon-ElastiCache'),
    'aws_elasticache_replication_group': ('Arch_Database', 'Arch_Amazon-ElastiCache'),

    # Application Integration
    'aws_sqs_queue': ('Arch_App-Integration', 'Arch_Amazon-Simple-Queue-Service'),
    'aws_sns_topic': ('Arch_App-Integration', 'Arch_Amazon-Simple-Notification-Service'),
    'aws_sns_topic_subscription': ('Arch_App-Integration', 'Arch_Amazon-Simple-Notification-Service'),
    'aws_sfn_state_machine': ('Arch_App-Integration', 'Arch_AWS-Step-Functions'),
    'aws_cloudwatch_event_rule': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),
    'aws_cloudwatch_event_target': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),
    'aws_kinesis_stream': ('Arch_Analytics', 'Arch_Amazon-Kinesis-Data-Streams'),

    # Security & Identity
    'aws_cognito_user_pool': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),
    'aws_cognito_user_pool_client': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),
    'aws_cognito_user_pool_domain': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),
    'aws_kms_key': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Key-Management-Service'),
    'aws_kms_alias': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Key-Management-Service'),
    'aws_secretsmanager_secret': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Secrets-Manager'),
    'aws_secretsmanager_secret_version': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Secrets-Manager'),
    'aws_iam_role': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_policy': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_role_policy': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_role_policy_attachment': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_acm_certificate': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Certificate-Manager'),
    'aws_acm_certificate_validation': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Certificate-Manager'),
    'aws_wafv2_web_acl': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_wafv2_web_acl_association': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_wafv2_rule_group': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_guardduty_detector': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-GuardDuty'),

    # Management & Governance
    'aws_cloudwatch_log_group': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_metric_alarm': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_dashboard': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudtrail': ('Arch_Management-Governance', 'Arch_AWS-CloudTrail'),
    'aws_config_config_rule': ('Arch_Management-Governance', 'Arch_AWS-Config'),
    'aws_budgets_budget': ('Arch_Cloud-Financial-Management', 'Arch_AWS-Budgets'),

    # Business Applications
    'aws_ses_domain_identity': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),
    'aws_ses_configuration_set': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),
    'aws_ses_email_identity': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),

    # AI/ML
    'aws_bedrockagent_knowledge_base': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Bedrock'),
    'aws_sagemaker_notebook_instance': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_endpoint': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
}

# Group icons for architectural elements (VPC, subnets, etc.)
GROUP_ICONS: Dict[str, str] = {
    'vpc': 'Virtual-private-cloud-VPC_32',
    'public_subnet': 'Public-subnet_32',
    'private_subnet': 'Private-subnet_32',
    'region': 'Region_32',
    'aws_cloud': 'AWS-Cloud_32',
    'availability_zone': 'Region_32',
}

# Color scheme for different resource categories
CATEGORY_COLORS: Dict[str, str] = {
    'Arch_Compute': '#ED7100',
    'Arch_Containers': '#ED7100',
    'Arch_Storage': '#3F8624',
    'Arch_Database': '#3B48CC',
    'Arch_Networking-Content-Delivery': '#8C4FFF',
    'Arch_App-Integration': '#E7157B',
    'Arch_Security-Identity-Compliance': '#DD344C',
    'Arch_Management-Governance': '#E7157B',
    'Arch_Artificial-Intelligence': '#01A88D',
    'Arch_Analytics': '#8C4FFF',
    'Arch_Business-Applications': '#DD344C',
    'Arch_Cloud-Financial-Management': '#3F8624',
    # Resource Icons categories
    'Res_Networking-Content-Delivery': '#8C4FFF',
    'Res_Compute': '#ED7100',
    'Res_Storage': '#3F8624',
    'Res_Database': '#3B48CC',
    'Res_Security-Identity-Compliance': '#DD344C',
}


class IconMapper:
    """Maps Terraform resources to AWS icons."""

    def __init__(self, icons_base_path: Optional[str] = None):
        self.icons_base_path = Path(icons_base_path) if icons_base_path else None
        self._icon_cache: Dict[str, str] = {}
        self._resource_icons_path: Optional[Path] = None
        self._architecture_icons_path: Optional[Path] = None
        self._group_icons_path: Optional[Path] = None

        if self.icons_base_path and self.icons_base_path.exists():
            self._discover_icon_directories()

    def _discover_icon_directories(self) -> None:
        """Auto-discover AWS icon directory structure."""
        if not self.icons_base_path:
            return

        # Find Resource-Icons directory (pattern: Resource-Icons_*)
        resource_dirs = list(self.icons_base_path.glob("Resource-Icons_*"))
        self._resource_icons_path = resource_dirs[0] if resource_dirs else None

        # Find Architecture-Service-Icons directory
        arch_dirs = list(self.icons_base_path.glob("Architecture-Service-Icons_*"))
        self._architecture_icons_path = arch_dirs[0] if arch_dirs else None

        # Find Architecture-Group-Icons directory
        group_dirs = list(self.icons_base_path.glob("Architecture-Group-Icons_*"))
        self._group_icons_path = group_dirs[0] if group_dirs else None

    def get_icon_path(
        self,
        resource_type: str,
        size: int = 48,
        format: str = 'svg'
    ) -> Optional[Path]:
        """Get the file path for a resource's icon."""
        if not self.icons_base_path or resource_type not in TERRAFORM_TO_ICON:
            return None

        category, icon_name = TERRAFORM_TO_ICON[resource_type]

        # Determine which icon set to use based on category prefix
        if category.startswith('Res_'):
            # Resource Icons (flat structure)
            if not self._resource_icons_path:
                return None
            resource_icons_dir = self._resource_icons_path
            icon_path = resource_icons_dir / category / f"{icon_name}_{size}.{format}"
            if icon_path.exists():
                return icon_path
            # Try without category subfolder
            for subdir in resource_icons_dir.iterdir():
                if subdir.is_dir():
                    test_path = subdir / f"{icon_name}_{size}.{format}"
                    if test_path.exists():
                        return test_path
        else:
            # Architecture-Service-Icons (has size subdirectories)
            if not self._architecture_icons_path:
                return None
            service_icons_dir = self._architecture_icons_path
            icon_path = service_icons_dir / category / str(size) / f"{icon_name}_{size}.{format}"

            if icon_path.exists():
                return icon_path

            # Try without size subdirectory
            icon_path = service_icons_dir / category / f"{icon_name}_{size}.{format}"
            if icon_path.exists():
                return icon_path

            # Try different sizes
            for alt_size in [64, 48, 32, 16]:
                icon_path = service_icons_dir / category / str(alt_size) / f"{icon_name}_{alt_size}.{format}"
                if icon_path.exists():
                    return icon_path

        return None

    def get_group_icon_path(
        self,
        group_type: str,
        format: str = 'svg'
    ) -> Optional[Path]:
        """Get the file path for a group icon (VPC, subnet, etc.)."""
        if not self._group_icons_path or group_type not in GROUP_ICONS:
            return None

        icon_name = GROUP_ICONS[group_type]
        icon_path = self._group_icons_path / f"{icon_name}.{format}"

        if icon_path.exists():
            return icon_path

        return None

    def get_icon_svg(self, resource_type: str, size: int = 48) -> Optional[str]:
        """Get the SVG content for a resource's icon."""
        cache_key = f"{resource_type}_{size}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        icon_path = self.get_icon_path(resource_type, size, 'svg')
        if not icon_path:
            # Return fallback colored rectangle
            svg_content = self._generate_fallback_icon(resource_type, size)
            self._icon_cache[cache_key] = svg_content
            return svg_content

        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
                self._icon_cache[cache_key] = svg_content
                return svg_content
        except Exception:
            # Return fallback on read error
            svg_content = self._generate_fallback_icon(resource_type, size)
            self._icon_cache[cache_key] = svg_content
            return svg_content

    def _generate_fallback_icon(self, resource_type: str, size: int = 48) -> str:
        """Generate a fallback colored rectangle SVG when no icon is available."""
        color = self.get_category_color(resource_type)
        display_name = self.get_display_name(resource_type)

        # Get short label (first letters of words or abbreviation)
        if len(display_name) <= 4:
            label = display_name.upper()
        else:
            words = display_name.split()
            if len(words) > 1:
                label = ''.join(w[0] for w in words if w).upper()[:4]
            else:
                label = display_name[:3].upper()

        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" rx="4" fill="{color}" fill-opacity="0.15" stroke="{color}" stroke-width="2"/>
  <text x="{size/2}" y="{size/2 + 4}" text-anchor="middle" font-family="Arial, sans-serif" font-size="{size/4}" font-weight="bold" fill="{color}">{label}</text>
</svg>'''

    def get_icon_data_uri(self, resource_type: str, size: int = 48) -> Optional[str]:
        """Get a data URI for embedding the icon in HTML/SVG."""
        svg_content = self.get_icon_svg(resource_type, size)
        if not svg_content:
            return None

        encoded = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
        return f"data:image/svg+xml;base64,{encoded}"

    def get_category_color(self, resource_type: str) -> str:
        """Get the category color for a resource type."""
        if resource_type not in TERRAFORM_TO_ICON:
            return '#666666'

        category, _ = TERRAFORM_TO_ICON[resource_type]
        return CATEGORY_COLORS.get(category, '#666666')

    def get_display_name(self, resource_type: str) -> str:
        """Get a human-readable display name for a resource type."""
        if resource_type not in TERRAFORM_TO_ICON:
            # Convert aws_resource_type to "Resource Type"
            name = resource_type.replace('aws_', '').replace('_', ' ').title()
            return name

        _, icon_name = TERRAFORM_TO_ICON[resource_type]
        # Extract service name from icon name
        # "Arch_Amazon-Simple-Queue-Service" -> "SQS"
        name = icon_name.replace('Arch_', '').replace('Amazon-', '').replace('AWS-', '')

        # Common abbreviations
        abbreviations = {
            'Simple-Queue-Service': 'SQS',
            'Simple-Notification-Service': 'SNS',
            'Simple-Storage-Service': 'S3',
            'Simple-Email-Service': 'SES',
            'Elastic-Container-Service': 'ECS',
            'Elastic-Container-Registry': 'ECR',
            'Elastic-Kubernetes-Service': 'EKS',
            'Elastic-Load-Balancing': 'ELB',
            'Elastic-Block-Store': 'EBS',
            'Key-Management-Service': 'KMS',
            'Identity-and-Access-Management': 'IAM',
            'Certificate-Manager': 'ACM',
            'Virtual-Private-Cloud': 'VPC',
            'Relational-Database-Service': 'RDS',
        }

        for full, abbr in abbreviations.items():
            if full in name:
                return abbr

        return name.replace('-', ' ')


def get_supported_resources() -> list:
    """Get list of all supported Terraform resource types."""
    return list(TERRAFORM_TO_ICON.keys())
