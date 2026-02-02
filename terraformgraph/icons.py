"""
AWS Icon Mapper

Maps Terraform resource types to AWS architecture icons.
"""

import base64
from pathlib import Path
from typing import Dict, Optional, Tuple

# Mapping from Terraform resource type to icon info
# Format: resource_type -> (category, icon_name)
TERRAFORM_TO_ICON: Dict[str, Tuple[str, str]] = {
    # ==========================================================================
    # NETWORKING & CONTENT DELIVERY
    # ==========================================================================
    'aws_vpc': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_subnet': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_internet_gateway': ('Res_Networking-Content-Delivery', 'Res_Amazon-VPC_Internet-Gateway'),
    'aws_nat_gateway': ('Res_Networking-Content-Delivery', 'Res_Amazon-VPC_NAT-Gateway'),
    'aws_route_table': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_route': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_route_table_association': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_eip': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Virtual-Private-Cloud'),
    'aws_vpc_endpoint': ('Res_Networking-Content-Delivery', 'Res_Amazon-VPC_Endpoints'),
    'aws_vpc_peering_connection': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Transit-Gateway'),
    'aws_transit_gateway': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Transit-Gateway'),
    'aws_transit_gateway_attachment': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Transit-Gateway'),
    'aws_vpn_gateway': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Site-to-Site-VPN'),
    'aws_vpn_connection': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Site-to-Site-VPN'),
    'aws_customer_gateway': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Site-to-Site-VPN'),
    'aws_dx_connection': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Direct-Connect'),
    'aws_vpc_lattice_service': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-VPC-Lattice'),

    # Load Balancing
    'aws_lb': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_alb': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_elb': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_lb_target_group': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_lb_listener': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),
    'aws_lb_listener_rule': ('Arch_Networking-Content-Delivery', 'Arch_Elastic-Load-Balancing'),

    # DNS & CDN
    'aws_route53_zone': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Route-53'),
    'aws_route53_record': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Route-53'),
    'aws_route53_health_check': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-Route-53'),
    'aws_cloudfront_distribution': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-CloudFront'),
    'aws_cloudfront_origin_access_identity': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-CloudFront'),
    'aws_cloudfront_origin_access_control': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-CloudFront'),
    'aws_cloudfront_function': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-CloudFront'),
    'aws_cloudfront_cache_policy': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-CloudFront'),

    # API Gateway
    'aws_api_gateway_rest_api': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_api_gateway_resource': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_api_gateway_method': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_api_gateway_integration': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_api_gateway_deployment': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_api_gateway_stage': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_apigatewayv2_api': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_apigatewayv2_stage': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_apigatewayv2_route': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),
    'aws_apigatewayv2_integration': ('Arch_Networking-Content-Delivery', 'Arch_Amazon-API-Gateway'),

    # Global Accelerator
    'aws_globalaccelerator_accelerator': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Global-Accelerator'),
    'aws_globalaccelerator_listener': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Global-Accelerator'),

    # App Mesh
    'aws_appmesh_mesh': ('Arch_Networking-Content-Delivery', 'Arch_AWS-App-Mesh'),
    'aws_appmesh_virtual_service': ('Arch_Networking-Content-Delivery', 'Arch_AWS-App-Mesh'),

    # Cloud Map
    'aws_service_discovery_service': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Cloud-Map'),
    'aws_service_discovery_private_dns_namespace': ('Arch_Networking-Content-Delivery', 'Arch_AWS-Cloud-Map'),

    # ==========================================================================
    # COMPUTE
    # ==========================================================================
    'aws_instance': ('Arch_Compute', 'Arch_Amazon-EC2'),
    'aws_launch_template': ('Arch_Compute', 'Arch_Amazon-EC2'),
    'aws_launch_configuration': ('Arch_Compute', 'Arch_Amazon-EC2'),
    'aws_ami': ('Arch_Compute', 'Arch_Amazon-EC2-Image-Builder'),
    'aws_autoscaling_group': ('Arch_Compute', 'Arch_Amazon-EC2-Auto-Scaling'),
    'aws_autoscaling_policy': ('Arch_Compute', 'Arch_Amazon-EC2-Auto-Scaling'),
    'aws_spot_instance_request': ('Arch_Compute', 'Arch_Amazon-EC2'),
    'aws_spot_fleet_request': ('Arch_Compute', 'Arch_Amazon-EC2'),

    # Lambda
    'aws_lambda_function': ('Arch_Compute', 'Arch_AWS-Lambda'),
    'aws_lambda_layer_version': ('Arch_Compute', 'Arch_AWS-Lambda'),
    'aws_lambda_permission': ('Arch_Compute', 'Arch_AWS-Lambda'),
    'aws_lambda_event_source_mapping': ('Arch_Compute', 'Arch_AWS-Lambda'),
    'aws_lambda_alias': ('Arch_Compute', 'Arch_AWS-Lambda'),
    'aws_lambda_function_url': ('Arch_Compute', 'Arch_AWS-Lambda'),

    # Batch
    'aws_batch_compute_environment': ('Arch_Compute', 'Arch_AWS-Batch'),
    'aws_batch_job_queue': ('Arch_Compute', 'Arch_AWS-Batch'),
    'aws_batch_job_definition': ('Arch_Compute', 'Arch_AWS-Batch'),

    # Elastic Beanstalk
    'aws_elastic_beanstalk_application': ('Arch_Compute', 'Arch_AWS-Elastic-Beanstalk'),
    'aws_elastic_beanstalk_environment': ('Arch_Compute', 'Arch_AWS-Elastic-Beanstalk'),

    # Lightsail
    'aws_lightsail_instance': ('Arch_Compute', 'Arch_Amazon-Lightsail'),
    'aws_lightsail_container_service': ('Arch_Compute', 'Arch_Amazon-Lightsail'),

    # App Runner
    'aws_apprunner_service': ('Arch_Compute', 'Arch_AWS-App-Runner'),

    # ==========================================================================
    # CONTAINERS
    # ==========================================================================
    'aws_ecs_cluster': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecs_service': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecs_task_definition': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecs_capacity_provider': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Service'),
    'aws_ecr_repository': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Registry'),
    'aws_ecr_lifecycle_policy': ('Arch_Containers', 'Arch_Amazon-Elastic-Container-Registry'),
    'aws_eks_cluster': ('Arch_Containers', 'Arch_Amazon-Elastic-Kubernetes-Service'),
    'aws_eks_node_group': ('Arch_Containers', 'Arch_Amazon-Elastic-Kubernetes-Service'),
    'aws_eks_fargate_profile': ('Arch_Containers', 'Arch_AWS-Fargate'),
    'aws_eks_addon': ('Arch_Containers', 'Arch_Amazon-Elastic-Kubernetes-Service'),

    # ==========================================================================
    # STORAGE
    # ==========================================================================
    'aws_s3_bucket': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_notification': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_policy': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_versioning': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_lifecycle_configuration': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_replication_configuration': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_server_side_encryption_configuration': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_object': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),
    'aws_s3_bucket_public_access_block': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service'),

    # S3 Glacier
    'aws_glacier_vault': ('Arch_Storage', 'Arch_Amazon-Simple-Storage-Service-Glacier'),

    # EBS
    'aws_ebs_volume': ('Arch_Storage', 'Arch_Amazon-Elastic-Block-Store'),
    'aws_ebs_snapshot': ('Arch_Storage', 'Arch_Amazon-Elastic-Block-Store'),
    'aws_volume_attachment': ('Arch_Storage', 'Arch_Amazon-Elastic-Block-Store'),

    # EFS
    'aws_efs_file_system': ('Arch_Storage', 'Arch_Amazon-EFS'),
    'aws_efs_mount_target': ('Arch_Storage', 'Arch_Amazon-EFS'),
    'aws_efs_access_point': ('Arch_Storage', 'Arch_Amazon-EFS'),

    # FSx
    'aws_fsx_lustre_file_system': ('Arch_Storage', 'Arch_Amazon-FSx-for-Lustre'),
    'aws_fsx_windows_file_system': ('Arch_Storage', 'Arch_Amazon-FSx-for-WFS'),
    'aws_fsx_ontap_file_system': ('Arch_Storage', 'Arch_Amazon-FSx-for-NetApp-ONTAP'),
    'aws_fsx_openzfs_file_system': ('Arch_Storage', 'Arch_Amazon-FSx-for-OpenZFS'),

    # Storage Gateway
    'aws_storagegateway_gateway': ('Arch_Storage', 'Arch_AWS-Storage-Gateway'),

    # Backup
    'aws_backup_vault': ('Arch_Storage', 'Arch_AWS-Backup'),
    'aws_backup_plan': ('Arch_Storage', 'Arch_AWS-Backup'),

    # ==========================================================================
    # DATABASE
    # ==========================================================================
    'aws_dynamodb_table': ('Arch_Database', 'Arch_Amazon-DynamoDB'),
    'aws_dynamodb_global_table': ('Arch_Database', 'Arch_Amazon-DynamoDB'),

    # RDS
    'aws_rds_cluster': ('Arch_Database', 'Arch_Amazon-Aurora'),
    'aws_rds_cluster_instance': ('Arch_Database', 'Arch_Amazon-Aurora'),
    'aws_db_instance': ('Arch_Database', 'Arch_Amazon-RDS'),
    'aws_db_subnet_group': ('Arch_Database', 'Arch_Amazon-RDS'),
    'aws_db_parameter_group': ('Arch_Database', 'Arch_Amazon-RDS'),
    'aws_db_option_group': ('Arch_Database', 'Arch_Amazon-RDS'),
    'aws_db_proxy': ('Arch_Database', 'Arch_Amazon-RDS'),

    # ElastiCache
    'aws_elasticache_cluster': ('Arch_Database', 'Arch_Amazon-ElastiCache'),
    'aws_elasticache_replication_group': ('Arch_Database', 'Arch_Amazon-ElastiCache'),
    'aws_elasticache_subnet_group': ('Arch_Database', 'Arch_Amazon-ElastiCache'),
    'aws_elasticache_parameter_group': ('Arch_Database', 'Arch_Amazon-ElastiCache'),

    # MemoryDB
    'aws_memorydb_cluster': ('Arch_Database', 'Arch_Amazon-MemoryDB'),

    # DocumentDB
    'aws_docdb_cluster': ('Arch_Database', 'Arch_Amazon-DocumentDB'),
    'aws_docdb_cluster_instance': ('Arch_Database', 'Arch_Amazon-DocumentDB'),

    # Neptune
    'aws_neptune_cluster': ('Arch_Database', 'Arch_Amazon-Neptune'),
    'aws_neptune_cluster_instance': ('Arch_Database', 'Arch_Amazon-Neptune'),

    # Keyspaces (Cassandra)
    'aws_keyspaces_keyspace': ('Arch_Database', 'Arch_Amazon-Keyspaces'),
    'aws_keyspaces_table': ('Arch_Database', 'Arch_Amazon-Keyspaces'),

    # Timestream
    'aws_timestreamwrite_database': ('Arch_Database', 'Arch_Amazon-Timestream'),
    'aws_timestreamwrite_table': ('Arch_Database', 'Arch_Amazon-Timestream'),

    # QLDB
    'aws_qldb_ledger': ('Arch_Database', 'Arch_Amazon-Quantum-Ledger-Database'),

    # Redshift
    'aws_redshift_cluster': ('Arch_Database', 'Arch_Amazon-Redshift'),
    'aws_redshiftserverless_namespace': ('Arch_Database', 'Arch_Amazon-Redshift'),
    'aws_redshiftserverless_workgroup': ('Arch_Database', 'Arch_Amazon-Redshift'),

    # ==========================================================================
    # APPLICATION INTEGRATION
    # ==========================================================================
    'aws_sqs_queue': ('Arch_App-Integration', 'Arch_Amazon-Simple-Queue-Service'),
    'aws_sqs_queue_policy': ('Arch_App-Integration', 'Arch_Amazon-Simple-Queue-Service'),

    'aws_sns_topic': ('Arch_App-Integration', 'Arch_Amazon-Simple-Notification-Service'),
    'aws_sns_topic_subscription': ('Arch_App-Integration', 'Arch_Amazon-Simple-Notification-Service'),
    'aws_sns_topic_policy': ('Arch_App-Integration', 'Arch_Amazon-Simple-Notification-Service'),

    'aws_sfn_state_machine': ('Arch_App-Integration', 'Arch_AWS-Step-Functions'),
    'aws_sfn_activity': ('Arch_App-Integration', 'Arch_AWS-Step-Functions'),

    # EventBridge
    'aws_cloudwatch_event_rule': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),
    'aws_cloudwatch_event_target': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),
    'aws_cloudwatch_event_bus': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),
    'aws_cloudwatch_event_archive': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),
    'aws_scheduler_schedule': ('Arch_App-Integration', 'Arch_Amazon-EventBridge'),

    # AppSync
    'aws_appsync_graphql_api': ('Arch_App-Integration', 'Arch_AWS-AppSync'),
    'aws_appsync_datasource': ('Arch_App-Integration', 'Arch_AWS-AppSync'),
    'aws_appsync_resolver': ('Arch_App-Integration', 'Arch_AWS-AppSync'),

    # MQ
    'aws_mq_broker': ('Arch_App-Integration', 'Arch_Amazon-MQ'),
    'aws_mq_configuration': ('Arch_App-Integration', 'Arch_Amazon-MQ'),

    # AppFlow
    'aws_appflow_flow': ('Arch_App-Integration', 'Arch_Amazon-AppFlow'),

    # ==========================================================================
    # ANALYTICS
    # ==========================================================================
    'aws_kinesis_stream': ('Arch_Analytics', 'Arch_Amazon-Kinesis-Data-Streams'),
    'aws_kinesis_firehose_delivery_stream': ('Arch_Analytics', 'Arch_Amazon-Data-Firehose'),
    'aws_kinesis_analytics_application': ('Arch_Analytics', 'Arch_Amazon-Managed-Service-for-Apache-Flink'),
    'aws_kinesisanalyticsv2_application': ('Arch_Analytics', 'Arch_Amazon-Managed-Service-for-Apache-Flink'),

    # Athena
    'aws_athena_workgroup': ('Arch_Analytics', 'Arch_Amazon-Athena'),
    'aws_athena_database': ('Arch_Analytics', 'Arch_Amazon-Athena'),
    'aws_athena_named_query': ('Arch_Analytics', 'Arch_Amazon-Athena'),

    # Glue
    'aws_glue_catalog_database': ('Arch_Analytics', 'Arch_AWS-Glue'),
    'aws_glue_catalog_table': ('Arch_Analytics', 'Arch_AWS-Glue'),
    'aws_glue_crawler': ('Arch_Analytics', 'Arch_AWS-Glue'),
    'aws_glue_job': ('Arch_Analytics', 'Arch_AWS-Glue'),
    'aws_glue_trigger': ('Arch_Analytics', 'Arch_AWS-Glue'),
    'aws_glue_workflow': ('Arch_Analytics', 'Arch_AWS-Glue'),

    # EMR
    'aws_emr_cluster': ('Arch_Analytics', 'Arch_Amazon-EMR'),
    'aws_emr_studio': ('Arch_Analytics', 'Arch_Amazon-EMR'),
    'aws_emrserverless_application': ('Arch_Analytics', 'Arch_Amazon-EMR'),

    # OpenSearch
    'aws_opensearch_domain': ('Arch_Analytics', 'Arch_Amazon-OpenSearch-Service'),
    'aws_elasticsearch_domain': ('Arch_Analytics', 'Arch_Amazon-OpenSearch-Service'),

    # MSK (Kafka)
    'aws_msk_cluster': ('Arch_Analytics', 'Arch_Amazon-Managed-Streaming-for-Apache-Kafka'),
    'aws_msk_configuration': ('Arch_Analytics', 'Arch_Amazon-Managed-Streaming-for-Apache-Kafka'),
    'aws_mskconnect_connector': ('Arch_Analytics', 'Arch_Amazon-Managed-Streaming-for-Apache-Kafka'),

    # QuickSight
    'aws_quicksight_data_source': ('Arch_Analytics', 'Arch_Amazon-QuickSight'),
    'aws_quicksight_dataset': ('Arch_Analytics', 'Arch_Amazon-QuickSight'),

    # Lake Formation
    'aws_lakeformation_resource': ('Arch_Analytics', 'Arch_AWS-Lake-Formation'),
    'aws_lakeformation_permissions': ('Arch_Analytics', 'Arch_AWS-Lake-Formation'),

    # Data Exchange
    'aws_dataexchange_data_set': ('Arch_Analytics', 'Arch_AWS-Data-Exchange'),

    # ==========================================================================
    # SECURITY & IDENTITY
    # ==========================================================================
    'aws_security_group': ('Res_General-Icons', 'Res_Firewall_48_Light'),
    'aws_security_group_rule': ('Res_General-Icons', 'Res_Firewall_48_Light'),
    'aws_vpc_security_group_ingress_rule': ('Res_General-Icons', 'Res_Firewall_48_Light'),
    'aws_vpc_security_group_egress_rule': ('Res_General-Icons', 'Res_Firewall_48_Light'),
    'aws_network_acl': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Network-Firewall'),
    'aws_networkfirewall_firewall': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Network-Firewall'),
    'aws_networkfirewall_firewall_policy': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Network-Firewall'),

    # Cognito
    'aws_cognito_user_pool': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),
    'aws_cognito_user_pool_client': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),
    'aws_cognito_user_pool_domain': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),
    'aws_cognito_identity_pool': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Cognito'),

    # KMS
    'aws_kms_key': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Key-Management-Service'),
    'aws_kms_alias': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Key-Management-Service'),
    'aws_kms_grant': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Key-Management-Service'),

    # Secrets Manager
    'aws_secretsmanager_secret': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Secrets-Manager'),
    'aws_secretsmanager_secret_version': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Secrets-Manager'),
    'aws_secretsmanager_secret_rotation': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Secrets-Manager'),

    # IAM
    'aws_iam_role': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_policy': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_role_policy': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_role_policy_attachment': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_user': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_group': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_instance_profile': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_openid_connect_provider': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),
    'aws_iam_saml_provider': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Identity-and-Access-Management'),

    # SSO / Identity Center
    'aws_ssoadmin_permission_set': ('Arch_Security-Identity-Compliance', 'Arch_AWS-IAM-Identity-Center'),
    'aws_identitystore_user': ('Arch_Security-Identity-Compliance', 'Arch_AWS-IAM-Identity-Center'),

    # ACM
    'aws_acm_certificate': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Certificate-Manager'),
    'aws_acm_certificate_validation': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Certificate-Manager'),
    'aws_acmpca_certificate_authority': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Private-Certificate-Authority'),

    # WAF
    'aws_wafv2_web_acl': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_wafv2_web_acl_association': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_wafv2_rule_group': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_wafv2_ip_set': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),
    'aws_wafv2_regex_pattern_set': ('Arch_Security-Identity-Compliance', 'Arch_AWS-WAF'),

    # Shield
    'aws_shield_protection': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Shield'),

    # GuardDuty
    'aws_guardduty_detector': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-GuardDuty'),
    'aws_guardduty_member': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-GuardDuty'),

    # Security Hub
    'aws_securityhub_account': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Security-Hub'),
    'aws_securityhub_member': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Security-Hub'),

    # Macie
    'aws_macie2_account': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Macie'),
    'aws_macie2_classification_job': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Macie'),

    # Inspector
    'aws_inspector2_enabler': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Inspector'),

    # Detective
    'aws_detective_graph': ('Arch_Security-Identity-Compliance', 'Arch_Amazon-Detective'),

    # Firewall Manager
    'aws_fms_policy': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Firewall-Manager'),

    # RAM
    'aws_ram_resource_share': ('Arch_Security-Identity-Compliance', 'Arch_AWS-Resource-Access-Manager'),

    # ==========================================================================
    # MANAGEMENT & GOVERNANCE
    # ==========================================================================
    'aws_cloudwatch_log_group': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_metric_alarm': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_dashboard': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_log_stream': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_log_metric_filter': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),
    'aws_cloudwatch_composite_alarm': ('Arch_Management-Governance', 'Arch_Amazon-CloudWatch'),

    'aws_cloudtrail': ('Arch_Management-Governance', 'Arch_AWS-CloudTrail'),
    'aws_cloudtrail_event_data_store': ('Arch_Management-Governance', 'Arch_AWS-CloudTrail'),

    'aws_config_config_rule': ('Arch_Management-Governance', 'Arch_AWS-Config'),
    'aws_config_configuration_recorder': ('Arch_Management-Governance', 'Arch_AWS-Config'),
    'aws_config_delivery_channel': ('Arch_Management-Governance', 'Arch_AWS-Config'),

    # Systems Manager
    'aws_ssm_parameter': ('Arch_Management-Governance', 'Arch_AWS-Systems-Manager'),
    'aws_ssm_document': ('Arch_Management-Governance', 'Arch_AWS-Systems-Manager'),
    'aws_ssm_maintenance_window': ('Arch_Management-Governance', 'Arch_AWS-Systems-Manager'),
    'aws_ssm_patch_baseline': ('Arch_Management-Governance', 'Arch_AWS-Systems-Manager'),
    'aws_ssm_association': ('Arch_Management-Governance', 'Arch_AWS-Systems-Manager'),

    # Organizations
    'aws_organizations_organization': ('Arch_Management-Governance', 'Arch_AWS-Organizations'),
    'aws_organizations_account': ('Arch_Management-Governance', 'Arch_AWS-Organizations'),
    'aws_organizations_organizational_unit': ('Arch_Management-Governance', 'Arch_AWS-Organizations'),
    'aws_organizations_policy': ('Arch_Management-Governance', 'Arch_AWS-Organizations'),

    # Control Tower
    'aws_controltower_control': ('Arch_Management-Governance', 'Arch_AWS-Control-Tower'),

    # Service Catalog
    'aws_servicecatalog_portfolio': ('Arch_Management-Governance', 'Arch_AWS-Service-Catalog'),
    'aws_servicecatalog_product': ('Arch_Management-Governance', 'Arch_AWS-Service-Catalog'),

    # CloudFormation
    'aws_cloudformation_stack': ('Arch_Management-Governance', 'Arch_AWS-CloudFormation'),
    'aws_cloudformation_stack_set': ('Arch_Management-Governance', 'Arch_AWS-CloudFormation'),

    # X-Ray
    'aws_xray_sampling_rule': ('Arch_Developer-Tools', 'Arch_AWS-X-Ray'),
    'aws_xray_group': ('Arch_Developer-Tools', 'Arch_AWS-X-Ray'),

    # ==========================================================================
    # DEVELOPER TOOLS
    # ==========================================================================
    'aws_codecommit_repository': ('Arch_Developer-Tools', 'Arch_AWS-CodeCommit'),
    'aws_codebuild_project': ('Arch_Developer-Tools', 'Arch_AWS-CodeBuild'),
    'aws_codepipeline': ('Arch_Developer-Tools', 'Arch_AWS-CodePipeline'),
    'aws_codedeploy_app': ('Arch_Developer-Tools', 'Arch_AWS-CodeDeploy'),
    'aws_codedeploy_deployment_group': ('Arch_Developer-Tools', 'Arch_AWS-CodeDeploy'),
    'aws_codeartifact_domain': ('Arch_Developer-Tools', 'Arch_AWS-CodeArtifact'),
    'aws_codeartifact_repository': ('Arch_Developer-Tools', 'Arch_AWS-CodeArtifact'),
    'aws_cloud9_environment_ec2': ('Arch_Developer-Tools', 'Arch_AWS-Cloud9'),
    'aws_codecatalyst_dev_environment': ('Arch_Developer-Tools', 'Arch_Amazon-CodeCatalyst'),

    # ==========================================================================
    # COST MANAGEMENT
    # ==========================================================================
    'aws_budgets_budget': ('Arch_Cloud-Financial-Management', 'Arch_AWS-Budgets'),
    'aws_budgets_budget_action': ('Arch_Cloud-Financial-Management', 'Arch_AWS-Budgets'),
    'aws_ce_cost_category': ('Arch_Cloud-Financial-Management', 'Arch_AWS-Cost-Explorer'),
    'aws_ce_anomaly_monitor': ('Arch_Cloud-Financial-Management', 'Arch_AWS-Cost-Explorer'),

    # ==========================================================================
    # BUSINESS APPLICATIONS
    # ==========================================================================
    'aws_ses_domain_identity': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),
    'aws_ses_configuration_set': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),
    'aws_ses_email_identity': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),
    'aws_sesv2_email_identity': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),
    'aws_sesv2_configuration_set': ('Arch_Business-Applications', 'Arch_Amazon-Simple-Email-Service'),

    # Connect
    'aws_connect_instance': ('Arch_Business-Applications', 'Arch_Amazon-Connect'),
    'aws_connect_contact_flow': ('Arch_Business-Applications', 'Arch_Amazon-Connect'),

    # Pinpoint
    'aws_pinpoint_app': ('Arch_Business-Applications', 'Arch_Amazon-Pinpoint'),
    'aws_pinpoint_email_channel': ('Arch_Business-Applications', 'Arch_Amazon-Pinpoint'),

    # Chime
    'aws_chime_voice_connector': ('Arch_Business-Applications', 'Arch_Amazon-Chime'),

    # WorkSpaces
    'aws_workspaces_workspace': ('Arch_End-User-Computing', 'Arch_Amazon-WorkSpaces-Family'),
    'aws_workspaces_directory': ('Arch_End-User-Computing', 'Arch_Amazon-WorkSpaces-Family'),

    # AppStream
    'aws_appstream_fleet': ('Arch_End-User-Computing', 'Arch_Amazon-AppStream-2'),
    'aws_appstream_stack': ('Arch_End-User-Computing', 'Arch_Amazon-AppStream-2'),

    # ==========================================================================
    # AI/ML
    # ==========================================================================
    'aws_bedrockagent_knowledge_base': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Bedrock'),
    'aws_bedrockagent_agent': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Bedrock'),
    'aws_bedrock_model_invocation_logging_configuration': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Bedrock'),

    'aws_sagemaker_notebook_instance': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_endpoint': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_model': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_endpoint_configuration': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_domain': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_feature_group': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),
    'aws_sagemaker_pipeline': ('Arch_Artificial-Intelligence', 'Arch_Amazon-SageMaker'),

    # Comprehend
    'aws_comprehend_entity_recognizer': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Comprehend'),
    'aws_comprehend_document_classifier': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Comprehend'),

    # Rekognition
    'aws_rekognition_collection': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Rekognition'),
    'aws_rekognition_project': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Rekognition'),

    # Textract
    'aws_textract_adapter': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Textract'),

    # Polly
    'aws_polly_lexicon': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Polly'),

    # Transcribe
    'aws_transcribe_vocabulary': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Transcribe'),
    'aws_transcribe_language_model': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Transcribe'),

    # Translate
    'aws_translate_terminology': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Translate'),

    # Lex
    'aws_lex_bot': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Lex'),
    'aws_lexv2models_bot': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Lex'),

    # Kendra
    'aws_kendra_index': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Kendra'),
    'aws_kendra_data_source': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Kendra'),

    # Personalize
    'aws_personalize_dataset_group': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Personalize'),
    'aws_personalize_solution': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Personalize'),

    # Forecast
    'aws_forecast_dataset_group': ('Arch_Artificial-Intelligence', 'Arch_Amazon-Forecast'),

    # ==========================================================================
    # IoT
    # ==========================================================================
    'aws_iot_thing': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Core'),
    'aws_iot_thing_type': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Core'),
    'aws_iot_policy': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Core'),
    'aws_iot_certificate': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Core'),
    'aws_iot_topic_rule': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Core'),

    'aws_iot_analytics_channel': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Analytics'),
    'aws_iot_analytics_datastore': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Analytics'),
    'aws_iot_analytics_pipeline': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Analytics'),

    'aws_greengrass_group': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Greengrass'),
    'aws_greengrassv2_component_version': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Greengrass'),
    'aws_greengrassv2_deployment': ('Arch_Internet-of-Things', 'Arch_AWS-IoT-Greengrass'),

    # ==========================================================================
    # MEDIA SERVICES
    # ==========================================================================
    'aws_media_convert_queue': ('Arch_Media-Services', 'Arch_AWS-Elemental-MediaConvert'),
    'aws_medialive_channel': ('Arch_Media-Services', 'Arch_AWS-Elemental-MediaLive'),
    'aws_mediapackage_channel': ('Arch_Media-Services', 'Arch_AWS-Elemental-MediaPackage'),
    'aws_mediastore_container': ('Arch_Media-Services', 'Arch_AWS-Elemental-MediaStore'),
    'aws_ivs_channel': ('Arch_Media-Services', 'Arch_Amazon-Interactive-Video-Service'),
    'aws_elastic_transcoder_pipeline': ('Arch_Media-Services', 'Arch_Amazon-Elastic-Transcoder'),

    # ==========================================================================
    # MIGRATION
    # ==========================================================================
    'aws_dms_replication_instance': ('Arch_Migration-Modernization', 'Arch_AWS-Database-Migration-Service'),
    'aws_dms_endpoint': ('Arch_Migration-Modernization', 'Arch_AWS-Database-Migration-Service'),
    'aws_dms_replication_task': ('Arch_Migration-Modernization', 'Arch_AWS-Database-Migration-Service'),

    'aws_datasync_task': ('Arch_Migration-Modernization', 'Arch_AWS-DataSync'),
    'aws_datasync_location_s3': ('Arch_Migration-Modernization', 'Arch_AWS-DataSync'),

    'aws_transfer_server': ('Arch_Migration-Modernization', 'Arch_AWS-Transfer-Family'),
    'aws_transfer_user': ('Arch_Migration-Modernization', 'Arch_AWS-Transfer-Family'),

    # ==========================================================================
    # GAME TECH
    # ==========================================================================
    'aws_gamelift_fleet': ('Arch_Games', 'Arch_Amazon-GameLift-Servers'),
    'aws_gamelift_game_session_queue': ('Arch_Games', 'Arch_Amazon-GameLift-Servers'),
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
            # Resource Icons - flat structure with size in filename
            if not self._resource_icons_path:
                return None
            resource_icons_dir = self._resource_icons_path

            # Special handling for General-Icons (has Light/Dark subdirs)
            if category == 'Res_General-Icons':
                # icon_name already contains full name like "Res_Firewall_48_Light"
                for subdir in ['Res_48_Light', 'Res_48_Dark']:
                    icon_path = resource_icons_dir / category / subdir / f"{icon_name}.{format}"
                    if icon_path.exists():
                        return icon_path
                return None

            # Standard Resource Icons: filename is {icon_name}_{size}.svg
            icon_path = resource_icons_dir / category / f"{icon_name}_{size}.{format}"
            if icon_path.exists():
                return icon_path

            # Try with .svg directly (some icons include size in name)
            icon_path = resource_icons_dir / category / f"{icon_name}.{format}"
            if icon_path.exists():
                return icon_path

            # Try searching in subdirectories
            for subdir in resource_icons_dir.iterdir():
                if subdir.is_dir():
                    test_path = subdir / f"{icon_name}_{size}.{format}"
                    if test_path.exists():
                        return test_path
                    test_path = subdir / f"{icon_name}.{format}"
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
