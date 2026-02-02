# VPC Decomposition and Resource Naming Enhancement

**Date:** 2026-02-02
**Status:** Approved
**Author:** Claude Code

## Overview

Enhance terraformgraph with two major features:
1. **VPC Decomposition**: Visualize VPC structure with AZ containers, subnets, and VPC endpoints on the border
2. **Resource Naming**: Display actual resource names resolved from tfvars, locals, and variable defaults

## Feature 1: Variable Resolution for Resource Names

### New Module: `variable_resolver.py`

A `VariableResolver` class that resolves Terraform variable interpolations to display actual resource names.

#### Data Sources (in priority order)

1. `*.tfvars` and `*.auto.tfvars` files
2. `locals {}` blocks in `.tf` files
3. `default` values in `variable {}` blocks

#### Interpolation Patterns Supported

- `${var.name}` - variable reference
- `${local.name}` - local value reference
- `"${var.prefix}-${var.env}-suffix"` - concatenations
- Nested references: `${local.prefix}` where prefix uses `${var.project}`

#### Integration

- `TerraformResource.resolve_display_name(resolver)` method
- Falls back to original name if resolution fails
- Truncation: max 25 characters with ellipsis (`"myproject-prod-api..."`)
- Full name available in tooltip

#### Example

```hcl
# variables.tf
variable "project" { default = "myapp" }
variable "env" { default = "prod" }

# main.tf
resource "aws_s3_bucket" "data" {
  bucket = "${var.project}-${var.env}-data"
}
```

**Result:** S3 icon shows "myapp-prod-data" instead of "data"

---

## Feature 2: VPC Decomposition

### New Data Model

#### `AvailabilityZone` class

```python
@dataclass
class AvailabilityZone:
    name: str              # "eu-west-1a" or "AZ-a"
    short_name: str        # "1a" or "a"
    subnets: List[Subnet]
    position: Position     # x, y, width, height
```

#### `Subnet` class

```python
@dataclass
class Subnet:
    resource: TerraformResource
    subnet_type: str       # "public", "private", "database"
    cidr_block: str
    availability_zone: str
    display_name: str      # Resolved name
```

#### `VPCStructure` class

```python
@dataclass
class VPCStructure:
    vpc_resource: TerraformResource
    display_name: str
    availability_zones: List[AvailabilityZone]
    endpoints: List[VPCEndpoint]
    other_resources: List[TerraformResource]  # NAT, IGW, etc.
```

#### `VPCEndpoint` class

```python
@dataclass
class VPCEndpoint:
    resource: TerraformResource
    endpoint_type: str     # "gateway" or "interface"
    service: str           # "s3", "dynamodb", "ecr.api", etc.
    display_name: str
```

### AZ Detection Strategy (with fallback)

1. **Priority 1 - Explicit attribute:**
   ```hcl
   availability_zone = "eu-west-1a"
   ```

2. **Priority 2 - Pattern matching on name:**
   - Suffixes: `-a`, `-b`, `-c`, `-1a`, `-1b`, `-az1`, `-az2`
   - Example: `private-subnet-a` → AZ "a"

3. **Fallback:** Group in "AZ-unknown"

### Subnet Type Inference

From name or tags:
- **Public:** contains "public", "pub", "dmz"
- **Private:** contains "private", "priv", "app"
- **Database:** contains "db", "database", "data"
- **Default:** "private" if undeterminable

---

## Layout Design

### VPC Visual Structure

```
┌─────────────────────────────────────────────────────────┐
│  VPC: myapp-prod-vpc                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   AZ-1a     │  │   AZ-1b     │  │   AZ-1c     │     │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │     │
│  │ │ public  │ │  │ │ public  │ │  │ │ public  │ │  ○──┼── S3 Endpoint
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │     │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │  ○──┼── DynamoDB Endpoint
│  │ │ private │ │  │ │ private │ │  │ │ private │ │     │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │  ○──┼── ECR Endpoint
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │     │
│  │ │   db    │ │  │ │   db    │ │  │ │   db    │ │     │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### VPC Endpoints Positioning

- Position: Right edge of VPC box
- Style: Icon half inside/outside the border
- Gateway Endpoints (S3, DynamoDB): top section
- Interface Endpoints: below gateway endpoints
- Visual connection: dashed line to external AWS service

### Dynamic Sizing

- **AZ width:** `(vpc_width - padding) / num_az`
- **AZ height:** Based on number of subnet types
- **VPC box:** Auto-expands to contain all AZs
- **Subnets:** Colored rectangles by type

### Subnet Colors

| Type     | Fill      | Border    |
|----------|-----------|-----------|
| Public   | `#d4edda` | `#28a745` |
| Private  | `#cce5ff` | `#007bff` |
| Database | `#fff3cd` | `#ffc107` |

---

## SVG/HTML Rendering

### New SVG Elements

#### AZ Container
```svg
<g class="az-container" data-az="eu-west-1a">
  <rect class="az-box" rx="8" fill="#f0f4f8" stroke="#7d8998" stroke-dasharray="4,2"/>
  <text class="az-label">eu-west-1a</text>
</g>
```

#### Subnet Box
```svg
<g class="subnet" data-type="private">
  <rect rx="4" fill="#cce5ff" stroke="#007bff"/>
  <text class="subnet-label">private-subnet-1a</text>
</g>
```

#### VPC Endpoint
```svg
<g class="vpc-endpoint" transform="translate(x, y)">
  <circle r="12" fill="white" stroke="#8c4fff"/>
  <image href="endpoint-icon.svg" width="20" height="20"/>
  <text class="endpoint-label">S3</text>
</g>
```

### JavaScript Interactivity

#### Drag & Drop Rules
- AZ containers: not draggable (fixed position)
- Subnets: not draggable (auto layout)
- Resources in subnets: draggable within their subnet only
- VPC Endpoints: draggable vertically along border only

#### Enhanced Tooltips
- **Subnet:** CIDR block, type, AZ
- **Resource:** Full name (not truncated), type, key attributes
- **Endpoint:** Type (Gateway/Interface), connected service

### Legend Additions
- Subnet colors (public/private/database)
- VPC Endpoint icon with description
- AZ container style

---

## Implementation Plan

### Phase 1: Variable Resolution
1. Create `variable_resolver.py` module
2. Implement tfvars parsing
3. Implement locals extraction
4. Implement variable defaults extraction
5. Add interpolation resolution logic
6. Integrate with `TerraformResource`
7. Add truncation logic (25 chars + ellipsis)
8. Update tooltip to show full name

### Phase 2: VPC Data Model
1. Create `Subnet`, `AvailabilityZone`, `VPCEndpoint`, `VPCStructure` classes
2. Implement AZ detection (attribute + pattern fallback)
3. Implement subnet type inference
4. Implement VPC endpoint detection and categorization
5. Update `ResourceAggregator` to build VPC structure

### Phase 3: Layout Engine
1. Add VPC structure layout logic
2. Implement AZ container positioning
3. Implement subnet positioning within AZ
4. Implement VPC endpoint border positioning
5. Add dynamic sizing calculations
6. Handle resources-in-subnet positioning

### Phase 4: Renderer
1. Add SVG elements for AZ, subnet, endpoint
2. Update CSS styles for new elements
3. Update JavaScript drag constraints
4. Enhance tooltips
5. Update legend

### Phase 5: Testing & Polish
1. Unit tests for variable resolver
2. Unit tests for VPC structure detection
3. Integration tests with example project
4. Visual testing and adjustments

---

## Files to Modify/Create

| File | Action | Description |
|------|--------|-------------|
| `terraformgraph/variable_resolver.py` | Create | Variable resolution logic |
| `terraformgraph/parser.py` | Modify | Integrate variable resolver |
| `terraformgraph/aggregator.py` | Modify | Add VPC structure classes and detection |
| `terraformgraph/layout.py` | Modify | Add VPC/AZ/subnet layout logic |
| `terraformgraph/renderer.py` | Modify | Add new SVG elements and styles |
| `tests/test_variable_resolver.py` | Create | Unit tests |
| `tests/test_vpc_structure.py` | Create | Unit tests |

---

## Backward Compatibility

- Existing diagrams continue to work (new features are additive)
- VPC decomposition only activates when subnets are detected
- Variable resolution gracefully falls back to original names
- No breaking changes to CLI interface
