# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2024-12-XX

### Added
- VPC endpoint visualization with service-specific icons (S3, DynamoDB, ECR, etc.)
- Gateway vs Interface endpoint differentiation with distinct visual styling
- Drag-and-drop repositioning of service icons in the diagram
- Click-to-highlight connections: click a service to see all its connections
- Click-to-highlight endpoints: click a connection to highlight source and target
- Save/Load layout persistence to preserve custom icon positions
- Responsive SVG layout that adapts to content
- De-grouped services: each resource now shows as individual icon instead of count badge

### Fixed
- VPC resources now correctly positioned inside their assigned subnets
- VPC endpoint rendering with cleaner design and proper service icons
- Extract VPC endpoint service name from unresolved Terraform variables
- Constrain drag-drop to assigned subnet boundaries using state-based IDs
- Improved icon resolution with fallback to colored rectangles

### Changed
- Background color changed to dark gray (#2d2d2d) for better contrast
- Legend updated with "Interactions" section documenting click/drag behaviors
- Diagram container uses light background (#f8f9fa) for better readability

### Internal
- Added UTF-8 encoding to all file operations for cross-platform compatibility
- Improved exception handling with specific exception types
- Removed dead code and duplicate imports
- Added comprehensive test coverage for terraform_tools and parser modules

## [1.0.2] - 2024-11-XX

### Added
- Initial support for terraform state integration
- Subnet assignment based on terraform state data

### Fixed
- Resource positioning in VPC diagrams

## [1.0.1] - 2024-10-XX

### Fixed
- Icon path resolution for AWS Architecture Icons
- HCL2 parsing edge cases

## [1.0.0] - 2024-10-XX

### Added
- Initial release
- Parse Terraform HCL files and generate infrastructure diagrams
- Support for 100+ AWS resource types
- Automatic resource grouping and aggregation
- VPC structure visualization with subnets and availability zones
- Interactive HTML output with zoom, pan, and tooltips
- Logical connections between services based on common patterns
- Variable resolution from tfvars and variable defaults
- Export to PNG functionality
