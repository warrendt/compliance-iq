# NCA CSCC to Azure Policy & Microsoft Defender Mapping

**Source Framework:** Critical Systems Cybersecurity Controls (CSCC-1:2019) - Saudi National Cybersecurity Authority  
**Target Platform:** Microsoft Azure - Policy & Defender for Cloud  
**Licensing:** All licensing tiers included (P1, P2, E5, Defender plans)

---

## DOMAIN 1: CYBERSECURITY GOVERNANCE

### 1-1: Cybersecurity Strategy
**NCA Requirement:** Cybersecurity strategy must prioritize protection of critical systems

**Azure Controls:**
- **Defender for Cloud - Microsoft Cloud Security Benchmark (MCSB)** - Default security standard, automatically enabled
- **Azure Policy Initiative:** NIST SP 800-53 Rev. 5 (698 policies)
- **Custom Security Standards** - Create via Defender CSPM plan
- **Secure Score Dashboard** - Continuous posture monitoring

### 1-2: Cybersecurity Risk Management
**NCA Requirements:**
- 1-2-1-1: Annual cybersecurity risk assessment on critical systems
- 1-2-1-2: Monthly cybersecurity risk register review for critical systems

**Azure Controls:**
- **Defender CSPM (Cloud Security Posture Management)** - Risk prioritization engine
- **Azure Security Benchmark** - Continuous compliance assessment
- **Defender for Cloud Recommendations** - Risk-based prioritization with attack paths
- **Custom Recommendations (KQL-based)** - Automated risk assessment queries
- **Microsoft Sentinel** - SIEM for threat detection and response
- **Policy Compliance Dashboard** - Real-time compliance status

**Alert Configuration:**
- Azure Policy - `deployIfNotExist` effect with automatic remediation
- Defender for Cloud - Security recommendations with risk levels
- Azure Monitor alerts on policy violations

### 1-3: Cybersecurity in IT Project Management
**NCA Requirements:**
- 1-3-1-1: Stress testing for capacity
- 1-3-1-2: Business continuity requirements implementation
- 1-3-2-1: Security source code review before release
- 1-3-2-2: Secure access, storage, documentation of source code
- 1-3-2-3: Secure authenticated APIs
- 1-3-2-4: Secure migration from test to production

**Azure Controls:**
- **Azure DevOps Security** - Secure development lifecycle
- **Microsoft Defender for DevOps** - Security scanning for pipelines, code, containers
- **Azure Repos** - Secure source code management with RBAC
- **Azure Key Vault** - Secrets management for API keys, certificates
- **Application Insights** - Load testing and capacity monitoring
- **Azure Policy:**
  - `Microsoft.Authorization/policyDefinitions/` for DevOps compliance
  - API Management policies for authentication

**Alert Configuration:**
- Defender for DevOps - Code scanning alerts, vulnerability findings
- Azure Monitor - Application performance alerts
- Key Vault - Access audit alerts

### 1-4: Periodical Cybersecurity Review and Audit
**NCA Requirements:**
- 1-4-1: Annual CSCC implementation review by cybersecurity function
- 1-4-2: Independent review every three years

**Azure Controls:**
- **Defender for Cloud Compliance Dashboard** - Continuous compliance against standards
- **Azure Policy Compliance Reports** - Downloadable compliance reports
- **Regulatory Compliance Assessments:**
  - NIST SP 800-53 Rev. 5
  - ISO 27001:2022
  - PCI DSS v4
  - CIS Microsoft Azure Foundations Benchmark
- **Activity Logs** - 90-day audit trail (extendable to Log Analytics)
- **Azure Monitor Logs** - Long-term retention for audit

**Alert Configuration:**
- Policy violation alerts
- Compliance drift notifications
- Audit log alerts for administrative actions

### 1-5: Cybersecurity in Human Resources
**NCA Requirements:**
- 1-5-1-1: Screening/vetting for critical system workers
- 1-5-1-2: Technical support positions filled by experienced Saudi professionals

**Azure Controls:**
- **Microsoft Entra ID (Azure AD):**
  - Conditional Access policies
  - Identity Protection
  - Access Reviews
  - Privileged Identity Management (PIM)
- **Azure RBAC** - Role-based access control
- **Azure Policy:**
  - Audit MFA enforcement
  - Require specific role assignments
  - Geographic access restrictions

**Alert Configuration:**
- Entra ID - Sign-in risk alerts, anomalous behavior
- PIM - Privileged role activation alerts
- Conditional Access - Policy violation alerts

---

## DOMAIN 2: CYBERSECURITY DEFENSE

### 2-1: Asset Management
**NCA Requirements:**
- 2-1-1-1: Annually-updated inventory of critical systems' assets
- 2-1-1-2: Identify asset owners and involve them in lifecycle management

**Azure Controls:**
- **Microsoft Defender for Cloud - Asset Inventory** - Automated discovery
- **Azure Resource Graph** - Queryable asset inventory across subscriptions
- **Azure Policy:**
  - `Audit resources without tags` - Owner/classification tags
  - `Require tag on resources and resource groups`
  - `Inherit tag from resource group if missing`
- **Microsoft Defender External Attack Surface Management** - Asset discovery
- **Azure Monitor** - Resource topology and dependencies

**Alert Configuration:**
- Policy alerts for untagged resources
- Defender alerts for new/modified resources
- Resource Graph queries for inventory changes

### 2-2: Identity and Access Management
**NCA Requirements:**
- 2-2-1-1: Prohibit remote access from outside Kingdom of Saudi Arabia
- 2-2-1-2: Restrict remote access from inside KSA, verify via SOC
- 2-2-1-3: Multi-factor authentication for all users
- 2-2-1-4: MFA for privileged users on management systems
- 2-2-1-5: High-standard secure password policy
- 2-2-1-6: Secure password storage (hashing functions)
- 2-2-1-7: Secure service account management
- 2-2-1-8: Prohibit direct database access (except DBAs)
- 2-2-2: Review user identities and access quarterly

**Azure Controls:**
- **Microsoft Entra ID:**
  - **Conditional Access Policies:**
    - Require MFA for all users (P1 license)
    - Require MFA for Azure management (built-in template)
    - Block access from specific countries/regions
    - Require compliant/hybrid joined devices
    - Restrict access by IP address
  - **Authentication Strength** - Phishing-resistant MFA (FIDO2, Windows Hello)
  - **Password Protection** - Custom banned password lists, weak password detection
  - **Identity Protection** (P2 license) - Risk-based conditional access
  - **Privileged Identity Management (PIM)** - Just-in-time admin access
  - **Access Reviews** - Quarterly access certification
  - **Managed Identities** - Eliminate service account passwords

- **Azure Policy (Identity Management):**
  - `Require MFA for privileged accounts`
  - `Audit accounts without MFA`
  - `Service principals should use certificates not secrets`
  - `Managed Identity should be used for authentication`

- **Azure SQL Database:**
  - Entra ID authentication only
  - Row-level security for DBAs
  - Dynamic data masking
  - Always Encrypted for sensitive columns

- **Microsoft Sentinel:**
  - User and Entity Behavior Analytics (UEBA)
  - Anomalous login detection
  - Impossible travel alerts

**Alert Configuration:**
- Entra ID:
  - Sign-ins from anonymous/risky IP addresses
  - Sign-ins from flagged countries
  - Leaked credentials detected
  - Unfamiliar sign-in properties
  - Password spray attacks
- PIM:
  - Privileged role activation
  - Role assignment outside PIM
- Sentinel:
  - Multiple failed login attempts
  - Privileged account anomalies

### 2-3: Information System and Information Processing Facilities Protection
**NCA Requirements:**
- 2-3-1-1: Whitelist applications on critical system servers
- 2-3-1-2: Endpoint protection for critical system servers
- 2-3-1-3: Security patches monthly (external/internet-connected) or quarterly (internal)
- 2-3-1-4: Isolated management network for privileged accounts
- 2-3-1-5: Encrypt administrative network traffic
- 2-3-1-6: Review configurations and hardening every six months
- 2-3-1-7: Remove default configurations, backdoor passwords
- 2-3-1-8: Protect logs and critical files from tampering

**Azure Controls:**
- **Microsoft Defender for Endpoint:**
  - Application control policies (AppLocker/WDAC)
  - Endpoint Detection and Response (EDR)
  - Threat and Vulnerability Management
  - Attack Surface Reduction rules
  - File integrity monitoring

- **Microsoft Defender for Servers Plan 2:**
  - Integrated Defender for Endpoint
  - Vulnerability assessment (agentless)
  - File integrity monitoring
  - Adaptive application controls
  - Just-in-time VM access

- **Azure Update Manager:**
  - Automated patch management
  - Patch compliance reporting
  - Maintenance windows
  - Pre/post-update scripts

- **Azure Policy:**
  - `System updates should be installed on your machines`
  - `Machines should be configured to periodically check for missing updates`
  - `Endpoint protection should be installed on machines`
  - `Endpoint protection health issues should be resolved`
  - `Windows machines should meet requirements for 'Security Options'`
  - `Audit machines with insecure password security settings`
  - `Secure transfer to storage accounts should be enabled` (encrypted traffic)

- **Azure Bastion / Just-in-Time (JIT) VM Access:**
  - Isolated management access
  - No public IP addresses on VMs
  - Time-limited access

- **Azure Monitor Logs:**
  - Immutable log storage
  - Log Analytics workspace with RBAC
  - Log retention policies

**Alert Configuration:**
- Defender for Endpoint:
  - Unauthorized application execution
  - Malware detected
  - Suspicious behavior
- Update Manager:
  - Missing critical updates
  - Update installation failures
- Policy alerts:
  - Non-compliant patch status
  - Endpoint protection not installed
- File Integrity Monitoring:
  - Critical file changes
  - Log tampering attempts

### 2-4: Networks Security Management
**NCA Requirements:**
- 2-4-1-1: Logical/physical segregation of critical systems networks
- 2-4-1-2: Review firewall rules every six months
- 2-4-1-3: Prohibit direct connection to critical systems without security scans
- 2-4-1-4: Prohibit wireless network for critical systems
- 2-4-1-5: APT protection at network layer
- 2-4-1-6: Prohibit internet connection for internal-only critical systems
- 2-4-1-7: Use isolated networks for limited B2B critical systems
- 2-4-1-8: DDoS protection
- 2-4-1-9: Firewall whitelist only

**Azure Controls:**
- **Azure Virtual Networks (VNets):**
  - Network segmentation with subnets
  - Network Security Groups (NSGs) with allow-only rules
  - Application Security Groups (ASGs)

- **Azure Firewall Premium:**
  - TLS inspection
  - IDPS (Intrusion Detection and Prevention)
  - URL filtering
  - Threat intelligence
  - Centralized rule management

- **Azure Private Link / Private Endpoints:**
  - No public internet exposure
  - Private connectivity to PaaS services

- **Azure DDoS Protection:**
  - DDoS Protection Standard plan
  - Always-on monitoring
  - Adaptive tuning

- **Microsoft Defender for Cloud:**
  - Adaptive Network Hardening recommendations
  - Just-in-time network access
  - Network map and topology

- **Azure Policy:**
  - `Subnets should be associated with a Network Security Group`
  - `Network interfaces should disable IP forwarding`
  - `Management ports should be closed on your virtual machines`
  - `Internet-facing virtual machines should be protected with network security groups`
  - `Private endpoint should be enabled for PaaS services`
  - `Public network access should be disabled`
  - `Secure transfer to storage accounts should be enabled`

- **Azure Firewall Manager:**
  - Centralized policy management
  - Secured virtual hubs

- **Network Watcher:**
  - NSG flow logs
  - Traffic Analytics
  - Connection troubleshooting

**Alert Configuration:**
- NSG flow logs → Log Analytics → Alerts:
  - Denied connections
  - Unusual traffic patterns
  - Access from unexpected IPs
- Azure Firewall:
  - Threat intelligence hits
  - IDPS alerts
  - Rule violations
- DDoS Protection:
  - DDoS attack detected/mitigated
- Defender for Cloud:
  - Open management ports
  - Missing NSGs

### 2-5: Mobile Devices Security
**NCA Requirements:**
- 2-5-1-1: Prohibit mobile device access to critical systems (temporary only, after risk assessment)
- 2-5-1-2: Full disk encryption for mobile devices with critical system access

**Azure Controls:**
- **Microsoft Intune:**
  - Device compliance policies
  - Conditional Access integration
  - Encryption enforcement
  - App protection policies
  - Device configuration profiles

- **Conditional Access:**
  - Block mobile devices
  - Require compliant devices
  - Require encrypted devices
  - Device platform restrictions

- **Azure Policy:**
  - `Mobile devices should require encryption`
  - `Access from mobile devices should be restricted`

- **Microsoft Defender for Endpoint (Mobile):**
  - Mobile threat defense
  - App protection
  - Jailbreak/root detection

**Alert Configuration:**
- Intune:
  - Non-compliant device access attempts
  - Encryption not enabled
  - Jailbroken/rooted device detected
- Conditional Access:
  - Mobile device access blocked
  - Policy violations

### 2-6: Data and Information Protection
**NCA Requirements:**
- 2-6-1-1: Prohibit critical system production data in other environments (unless masked/scrambled)
- 2-6-1-2: Classify all data in critical systems
- 2-6-1-3: Protect classified data with DLP
- 2-6-1-4: Define data retention periods per legislation
- 2-6-1-5: Prohibit data transfer from production to other environments

**Azure Controls:**
- **Microsoft Purview (Data Governance):**
  - Automated data classification
  - Sensitive data discovery
  - Data catalog
  - Data lineage

- **Microsoft Purview Data Loss Prevention:**
  - DLP policies for Azure Storage, SQL, files
  - Endpoint DLP
  - Content inspection
  - Policy tips and blocking

- **Information Protection:**
  - Sensitivity labels
  - Automatic classification
  - Encryption based on labels

- **Azure Storage:**
  - Soft delete for blobs
  - Versioning
  - Immutable blob storage (WORM)
  - Lifecycle management policies

- **Azure SQL Database:**
  - Dynamic data masking
  - Always Encrypted
  - Transparent Data Encryption (TDE)
  - Row-Level Security (RLS)

- **Azure Policy:**
  - `Azure SQL Database should have the minimal TLS version set to 1.2`
  - `Storage accounts should use customer-managed key for encryption`
  - `SQL databases should have an Azure Active Directory administrator provisioned`
  - `Transparent Data Encryption on SQL databases should be enabled`

**Alert Configuration:**
- Purview DLP:
  - Sensitive data exfiltration attempts
  - Policy violations
  - High-volume data transfers
- Azure Monitor:
  - Large data exports
  - Unauthorized data access
- Sentinel:
  - Abnormal data access patterns
  - Bulk data deletion

### 2-7: Cryptography
**NCA Requirements:**
- 2-7-1-1: Encrypt all critical systems' data-in-transit
- 2-7-1-2: Encrypt all critical systems' data-at-rest (file, database, or column level)
- 2-7-1-3: Use secure, up-to-date methods, algorithms, keys per NCA guidance

**Azure Controls:**
- **Azure Key Vault:**
  - Centralized key management
  - HSM-backed keys (Premium tier)
  - Key rotation automation
  - Access policies with RBAC

- **Azure Key Vault Managed HSM:**
  - FIPS 140-2 Level 3 validated HSMs
  - Customer-controlled HSM

- **Data-at-Rest Encryption (Default):**
  - Azure Storage - SSE with AES-256
  - Azure SQL Database - TDE
  - Azure Cosmos DB - Automatic encryption
  - Managed Disks - AES-256 encryption

- **Customer-Managed Keys (CMK):**
  - Available for most services
  - Stored in Key Vault
  - Customer-controlled rotation

- **Data-in-Transit Encryption:**
  - TLS 1.2+ enforced
  - Azure services use TLS by default
  - Certificate management in Key Vault

- **Azure Policy:**
  - `Storage accounts should use customer-managed key for encryption`
  - `Azure Cosmos DB accounts should use customer-managed keys`
  - `Transparent Data Encryption on SQL databases should be enabled`
  - `Azure SQL Database should have the minimal TLS version set to 1.2`
  - `Secure transfer to storage accounts should be enabled`
  - `Storage accounts should enforce a minimum of TLS 1.2`
  - `Function apps should require FTPS only`
  - `Function apps should use the latest TLS version`

**Alert Configuration:**
- Key Vault:
  - Key access/usage
  - Key expiration approaching
  - Failed decryption attempts
  - Access from unusual locations
- Azure Monitor:
  - Non-TLS connections
  - Weak cipher usage
  - Certificate expiration

### 2-8: Backup and Recovery Management
**NCA Requirements:**
- 2-8-1-1: Online and offline backups cover all critical systems
- 2-8-1-2: Daily backup for critical systems (recommended)
- 2-8-1-3: Secure backup access, storage, transfer; protect from destruction
- 2-8-2: Test backup recovery quarterly for critical systems

**Azure Controls:**
- **Azure Backup:**
  - Recovery Services Vault
  - Backup policies (hourly to yearly)
  - Enhanced policy - hourly backups (4/6/8/12/24 hour intervals)
  - Operational tier (snapshots) + Vault tier
  - Geo-redundant storage (GRS), Zone-redundant storage (ZRS)
  - Soft delete (14 days default)
  - Multi-user authorization (MUA)
  - Immutable vault

- **Azure Backup Center:**
  - Centralized backup management
  - Backup reports and dashboards
  - Cross-region restore

- **Supported Workloads:**
  - Azure VMs
  - SQL in Azure VMs
  - SAP HANA in Azure VMs
  - Azure Files
  - Azure Blobs (operational + vaulted)
  - Azure Disks
  - Azure Database for PostgreSQL

- **Azure Policy (Built-in Backup Policies):**
  - `Configure backup on VMs without a given tag to an existing recovery services vault`
  - `Configure backup on VMs with a given tag to an existing recovery services vault`
  - `Azure Backup should be enabled for Virtual Machines`
  - `Configure backup on Azure Files to an existing recovery services vault`
  - `Deploy Diagnostic Settings for Recovery Services Vault to Log Analytics workspace`

- **Azure Site Recovery:**
  - Disaster recovery orchestration
  - Replication to secondary region
  - Recovery plans with automated failover testing

**Alert Configuration:**
- Azure Backup:
  - Backup job failures
  - Backup not configured on critical resources
  - Backup health issues
  - Backup vault access
  - Restore operations
- Azure Monitor:
  - Backup policy violations
  - RPO/RTO breaches
  - Storage threshold alerts

### 2-9: Vulnerabilities Management
**NCA Requirements:**
- 2-9-1-1: Use trusted vulnerability assessment methods and tools
- 2-9-1-2: Assess vulnerabilities monthly (external/internet) or quarterly (internal)
- 2-9-1-3: Immediate remediation for critical vulnerabilities
- 2-9-2: Vulnerability assessments monthly on critical systems

**Azure Controls:**
- **Microsoft Defender Vulnerability Management:**
  - Continuous vulnerability scanning
  - Software inventory
  - CVE tracking
  - Exposure score
  - Remediation recommendations
  - Integration with Intune for patching

- **Microsoft Defender for Servers Plan 2:**
  - Agentless vulnerability scanning
  - Qualys/Defender VM integration
  - Vulnerability assessment for VMs

- **Microsoft Defender for Containers:**
  - Container image vulnerability scanning
  - Registry scanning
  - Runtime vulnerability detection

- **Microsoft Defender for SQL:**
  - Vulnerability assessment for databases
  - SQL configuration recommendations

- **Microsoft Defender for Cloud:**
  - Integrated vulnerability assessment
  - Security recommendations
  - Vulnerability findings in Secure Score

- **Azure Policy:**
  - `Machines should have vulnerability findings resolved`
  - `Container registry images should have vulnerability findings resolved`
  - `SQL databases should have vulnerability findings resolved`
  - `System updates should be installed on your machines`

**Alert Configuration:**
- Defender Vulnerability Management:
  - Critical/high severity vulnerabilities detected
  - Exploitable vulnerabilities
  - Zero-day vulnerabilities
  - Increased exposure score
- Defender for Cloud:
  - New vulnerability findings
  - Vulnerability remediation recommendations
- Sentinel:
  - Active exploitation attempts of known vulnerabilities

### 2-10: Penetration Testing
**NCA Requirements:**
- 2-10-1-1: Penetration tests cover all critical system components
- 2-10-1-2: Qualified team conducts penetration tests
- 2-10-2: Penetration tests every six months for critical systems

**Azure Controls:**
- **Azure Penetration Testing:**
  - No prior approval required (Rules of Engagement)
  - Allowed on Azure resources you own
  - Must follow [penetration testing rules](https://www.microsoft.com/msrc/pentest-rules-of-engagement)

- **Microsoft Defender for Cloud:**
  - Continuous security posture assessment
  - Simulated attack paths
  - Security graph analysis

- **Microsoft Security Copilot:**
  - AI-powered security analysis
  - Attack simulation insights

- **Azure Monitor / Log Analytics:**
  - Store penetration testing results
  - Track remediation

- **Documentation and Tracking:**
  - Azure DevOps for tracking findings
  - Defender for Cloud recommendations for remediation tracking

**Alert Configuration:**
- Policy-based alerts for tracking penetration test schedule
- Custom Log Analytics queries for penetration test compliance
- Defender for Cloud recommendations for identified issues

### 2-11: Cybersecurity Event Logs and Monitoring Management
**NCA Requirements:**
- 2-11-1-1: Activate logs on all critical system components
- 2-11-1-2: File integrity monitoring alerts
- 2-11-1-3: Monitor and analyze user behavior
- 2-11-1-4: 24/7 security event monitoring for critical systems
- 2-11-1-5: Maintain and protect event logs with all details
- 2-11-2: 18-month log retention minimum for critical systems

**Azure Controls:**
- **Azure Monitor:**
  - Platform logs (Activity logs, Resource logs, Entra ID logs)
  - Log Analytics workspace
  - Diagnostic settings for all resources
  - 730-day maximum retention (24 months)
  - Archive to Storage Account for longer retention
  - Kusto Query Language (KQL) for analysis

- **Microsoft Sentinel (SIEM/SOAR):**
  - 24/7 security monitoring
  - Data connectors for 300+ sources
  - Built-in analytics rules
  - ML-based threat detection
  - User and Entity Behavior Analytics (UEBA)
  - Automated incident response
  - Threat hunting with KQL
  - Workbooks for visualization

- **Microsoft Defender for Cloud:**
  - Security alerts
  - Threat intelligence
  - Integration with Sentinel

- **Microsoft Defender for Endpoint:**
  - Advanced hunting
  - Automated investigation and response
  - Timeline of device activities

- **File Integrity Monitoring:**
  - Defender for Cloud - File Integrity Monitoring (FIM)
  - Tracks changes to critical files and registry
  - Available with Defender for Servers Plan 2

- **Azure Policy:**
  - `Resource logs should be enabled` (multiple services)
  - `Diagnostic logs in [Service] should be enabled`
  - `Azure Monitor log profile should collect logs for categories 'write,' 'delete,' and 'action'`

- **Immutable Storage:**
  - Write-Once-Read-Many (WORM) for audit logs
  - Legal hold and time-based retention policies

**Alert Configuration:**
- Sentinel:
  - Analytics rules (scheduled, near real-time, ML-based)
  - Anomaly detection
  - Threat intelligence matches
  - Custom detection rules
- Azure Monitor:
  - Metric alerts
  - Log search alerts
  - Activity log alerts
  - Smart detection
- File Integrity Monitoring:
  - Critical file changes
  - Registry modifications
- Defender for Endpoint:
  - Suspicious behavior
  - Malware detection
  - Privilege escalation

### 2-12: Web Application Security
**NCA Requirements:**
- 2-12-1-1: Secure session management (authenticity, lockout, timeout)
- 2-12-1-2: Apply OWASP Top 10 standards
- 2-12-2: Use multi-tier architecture (minimum 3 tiers)

**Azure Controls:**
- **Azure Web Application Firewall (WAF):**
  - Available on Application Gateway, Front Door, CDN
  - OWASP ModSecurity Core Rule Set (CRS 3.2)
  - Custom rules
  - Bot protection
  - Geo-filtering
  - Rate limiting

- **Azure Application Gateway:**
  - SSL/TLS termination
  - Session affinity
  - URL-based routing
  - WAF integration

- **Azure Front Door:**
  - Global load balancing
  - WAF at edge
  - DDoS protection
  - SSL offloading

- **Azure App Service:**
  - Built-in authentication (Easy Auth)
  - Managed identities
  - Session timeout configuration
  - HTTPS only enforcement
  - Deployment slots (dev/staging/prod)

- **Azure API Management:**
  - OAuth 2.0 / OpenID Connect
  - JWT validation
  - Rate limiting and quotas
  - IP filtering

- **Azure Policy:**
  - `Web Application Firewall should be enabled for Application Gateway`
  - `Web Application Firewall should be enabled for Azure Front Door`
  - `App Service apps should use latest TLS version`
  - `App Service apps should only be accessible over HTTPS`
  - `CORS should not allow every resource to access your web applications`

- **Microsoft Defender for App Service:**
  - Threat detection
  - Security recommendations
  - Attack attempt detection

**Alert Configuration:**
- WAF:
  - Attack patterns detected
  - SQL injection attempts
  - XSS attempts
  - High request rate (DoS)
- Defender for App Service:
  - Malicious requests
  - Suspicious domain lookup
  - Fileless attack attempts
- Azure Monitor:
  - Failed authentication attempts
  - Session anomalies

### 2-13: Application Security
**NCA Requirements:**
- 2-13-1: Define, document, approve cybersecurity requirements for internal applications
- 2-13-2: Implement requirements
- 2-13-3-1: Multi-tier architecture (minimum 3 tiers)
- 2-13-3-2: Use secure protocols (HTTPS)
- 2-13-3-3: Outline acceptable use policy
- 2-13-3-4: Secure session management
- 2-13-4: Periodic review of requirements

**Azure Controls:**
- **Microsoft Defender for Cloud - DevOps Security:**
  - Code scanning (SAST)
  - Dependency scanning (SCA)
  - Infrastructure as Code (IaC) scanning
  - Secret scanning
  - GitHub/Azure DevOps integration

- **Azure DevOps:**
  - Secure development pipeline
  - Code review policies
  - Branch policies
  - Build validation

- **GitHub Advanced Security:**
  - Code scanning (CodeQL)
  - Secret scanning
  - Dependency review
  - Security advisories

- **Azure App Service:**
  - Application architecture enforcement
  - Network isolation
  - Private endpoints
  - VNet integration

- **Azure Policy:**
  - Custom policies for application standards
  - Deployment gates
  - Configuration requirements

- **Application Insights:**
  - Performance monitoring
  - Usage analytics
  - Exception tracking

**Alert Configuration:**
- Defender for DevOps:
  - Critical/high vulnerabilities in code
  - Exposed secrets
  - IaC misconfigurations
- GitHub/Azure DevOps:
  - Policy violations
  - Failed security gates
- Application Insights:
  - Exception spikes
  - Performance degradation

---

## DOMAIN 3: CYBERSECURITY RESILIENCE

### 3-1: Cybersecurity Resilience Aspects of Business Continuity Management
**NCA Requirements:**
- 3-1-1-1: Establish disaster recovery center for critical systems
- 3-1-1-2: Incorporate critical systems in DR plans
- 3-1-1-3: Annual DR testing for critical systems
- 3-1-1-4: Live DR testing recommended

**Azure Controls:**
- **Azure Site Recovery (ASR):**
  - Disaster recovery orchestration
  - Replication to secondary Azure region
  - Recovery plans with automated/manual steps
  - Test failover (no impact on production)
  - Planned/unplanned failover
  - Replication monitoring

- **Azure Backup:**
  - Cross-region restore (CRR)
  - Geo-redundant storage (GRS)
  - Secondary region recovery

- **Azure Availability Zones:**
  - In-region high availability
  - 3 physically separate zones per region

- **Azure Paired Regions:**
  - 300+ miles separation
  - Priority recovery in outages
  - Sequential updates

- **Azure Policy:**
  - `Virtual machines should be enabled for disaster recovery`
  - `Geo-redundant backup should be enabled for Azure Database services`
  - `Geo-redundant storage should be enabled for Storage Accounts`

- **Business Continuity Documentation:**
  - Store DR plans in Azure Blob (immutable)
  - Version control in Azure DevOps

- **Testing Framework:**
  - ASR test failover (non-disruptive)
  - Azure Chaos Studio for resilience testing
  - Load testing with Azure Load Testing

**Alert Configuration:**
- Site Recovery:
  - Replication health issues
  - Test failover failures
  - RPO threshold breached
  - Failover operations
- Azure Monitor:
  - Replication lag
  - Backup failures
  - Region outage detection
- Policy alerts:
  - DR not configured
  - GRS not enabled

---

## DOMAIN 4: THIRD-PARTY AND CLOUD COMPUTING CYBERSECURITY

### 4-1: Third-Party Cybersecurity
**NCA Requirements:**
- 4-1-1-1: Screening/vetting of outsourcing companies and personnel for critical systems
- 4-1-1-2: Outsourcing must rely on Saudi companies per legislation

**Azure Controls:**
- **Microsoft Entra ID B2B (Business-to-Business):**
  - Guest user access
  - Conditional Access for external users
  - Cross-tenant access settings
  - Terms of use enforcement

- **Azure Lighthouse:**
  - Delegated resource management
  - Audit trail of partner actions
  - Just-in-time access for partners

- **Azure Policy:**
  - `Audit external accounts with owner permissions`
  - `External accounts with write permissions should be removed`
  - `Guest accounts should be reviewed regularly`

- **Privileged Identity Management:**
  - Time-limited external access
  - Approval workflows
  - Access reviews for guests

- **Microsoft Defender for Cloud:**
  - Security posture for multi-tenant scenarios
  - Recommendations for external access

**Alert Configuration:**
- Entra ID:
  - Guest user additions
  - Privileged guest access
  - External user sign-ins
- PIM:
  - External user privilege escalation
- Sentinel:
  - Anomalous external user behavior
  - Lateral movement by external accounts

### 4-2: Cloud Computing and Hosting Cybersecurity
**NCA Requirement:**
- 4-2-1-1: Host critical systems in-organization or Saudi cloud providers compliant with NCA Cloud Cybersecurity Controls (CCC)

**Azure Controls:**
- **Azure Regions in Saudi Arabia:**
  - Saudi Arabia Central (Riyadh)
  - Saudi Arabia North (Jeddah)
  - Data residency compliance

- **Azure Compliance:**
  - ISO 27001, 27017, 27018
  - SOC 1, 2, 3
  - CSA STAR Certification
  - Multiple industry certifications

- **Azure Sovereign Cloud:**
  - Azure Government (US)
  - Azure China (operated by 21Vianet)
  - Azure Germany (Microsoft Cloud Deutschland - retired)

- **Data Residency Controls:**
  - Azure Policy for region restrictions
  - `Allowed locations` policy
  - `Allowed locations for resource groups` policy

- **Azure Dedicated Host:**
  - Physical server isolation
  - No multi-tenancy

- **Azure Policy:**
  - `Require specific regions for resource deployment`
  - `Audit resources deployed outside Saudi regions`
  - `Storage accounts should restrict network access`

- **Microsoft Defender for Cloud:**
  - Multi-cloud support (AWS, GCP)
  - Unified security posture
  - Regulatory compliance dashboard

- **Azure Confidential Computing:**
  - Hardware-based Trusted Execution Environments (TEEs)
  - Encryption of data in use

**Alert Configuration:**
- Azure Policy:
  - Resources deployed outside allowed regions
  - Non-compliant configurations
- Azure Monitor:
  - Data egress to non-Saudi regions
  - Cross-region traffic
- Defender for Cloud:
  - Cloud security posture drift
  - Multi-cloud compliance violations

---

## IMPLEMENTATION FRAMEWORK

### Phase 1: Foundation (Month 1-2)
1. **Enable Core Defender Plans:**
   - Defender for Servers Plan 2
   - Defender CSPM
   - Defender for Storage
   - Defender for SQL
   - Defender for Key Vault
   - Defender for App Service
   - Defender for Containers

2. **Deploy Baseline Policies:**
   - Microsoft Cloud Security Benchmark (auto-enabled)
   - NIST SP 800-53 Rev. 5 initiative
   - Saudi Arabia region restriction policies
   - MFA enforcement policies

3. **Configure Identity Protection:**
   - Entra ID P2 licenses
   - Conditional Access policies (all NCA 2-2 requirements)
   - Privileged Identity Management
   - Identity Protection

4. **Enable Logging:**
   - Create Log Analytics workspace (18+ month retention)
   - Enable diagnostic settings on all resources
   - Configure Activity Log export

### Phase 2: Advanced Security (Month 3-4)
1. **Deploy Microsoft Sentinel:**
   - Enable Sentinel on Log Analytics workspace
   - Connect data sources (Azure, Office 365, Threat Intelligence)
   - Deploy analytics rules
   - Configure UEBA

2. **Network Security:**
   - Implement Network Security Groups (NSGs)
   - Deploy Azure Firewall Premium
   - Configure Private Endpoints
   - Enable DDoS Protection Standard
   - Implement network segmentation

3. **Endpoint Protection:**
   - Onboard devices to Defender for Endpoint
   - Deploy Intune compliance policies
   - Configure application control
   - Enable file integrity monitoring

4. **Backup and DR:**
   - Create Recovery Services Vaults (Saudi regions)
   - Configure backup policies (daily for critical systems)
   - Deploy Azure Site Recovery
   - Document recovery procedures

### Phase 3: Optimization (Month 5-6)
1. **Custom Policies and Standards:**
   - Create custom security standards in Defender CSPM
   - Deploy KQL-based custom recommendations
   - Implement automated remediation

2. **Data Protection:**
   - Deploy Microsoft Purview
   - Configure sensitivity labels
   - Implement DLP policies
   - Enable Always Encrypted for SQL

3. **Vulnerability Management:**
   - Configure Defender Vulnerability Management
   - Integrate with Intune for automated patching
   - Create remediation workflows

4. **Testing and Validation:**
   - Conduct DR test failovers
   - Penetration testing
   - Quarterly access reviews
   - Backup restoration tests

---

## ALERTING AND MONITORING MATRIX

### Critical Alerts (P1 - Immediate Response)
| Control Area | Alert | Service | Action |
|--------------|-------|---------|--------|
| 2-2 Identity | Sign-in from blocked country | Entra ID | Block + Investigate |
| 2-2 Identity | Multiple failed MFA | Entra ID | Account lockdown |
| 2-3 Systems | Critical vulnerability detected | Defender VM | Immediate patch |
| 2-4 Network | Firewall rule violation | Azure Firewall | Block + Review |
| 2-6 Data | DLP policy violation - exfiltration | Purview DLP | Block + Incident |
| 2-11 Logging | Log tampering detected | Sentinel | Incident response |
| 3-1 DR | Replication stopped | Site Recovery | Immediate action |

### High Alerts (P2 - 1 Hour Response)
| Control Area | Alert | Service | Action |
|--------------|-------|---------|--------|
| 2-1 Assets | Untagged critical resource | Azure Policy | Tag + Classify |
| 2-3 Systems | Missing patch > 30 days | Update Manager | Schedule patch |
| 2-8 Backup | Backup failure | Azure Backup | Investigate + Retry |
| 2-9 Vulnerabilities | High severity CVE | Defender VM | Remediate within 48h |
| 2-11 Logs | Log Analytics quota exceeded | Azure Monitor | Increase capacity |

### Medium Alerts (P3 - 24 Hour Response)
| Control Area | Alert | Service | Action |
|--------------|-------|---------|--------|
| 1-2 Risk | Policy non-compliance | Azure Policy | Remediation plan |
| 2-2 Identity | Guest account not reviewed | Entra ID | Quarterly review |
| 2-3 Systems | Configuration drift | Defender for Cloud | Restore baseline |
| 2-10 Pentest | Pentest overdue | Custom alert | Schedule test |

---

## LICENSING REQUIREMENTS

### Minimum Required Licenses
1. **Microsoft 365 / Entra ID:**
   - Entra ID P2 (for Conditional Access, PIM, Identity Protection)
   - Or Microsoft 365 E5

2. **Microsoft Defender for Cloud:**
   - Defender CSPM
   - Defender for Servers Plan 2
   - Defender for Storage
   - Defender for SQL
   - Defender for Key Vault
   - Defender for App Service
   - Defender for Containers
   - Defender for DNS (legacy, now in Servers)

3. **Microsoft Sentinel:**
   - Pay-as-you-go based on data ingestion
   - Or Microsoft 365 E5 includes some capacity

4. **Microsoft Defender for Endpoint:**
   - Plan 2 (or Microsoft 365 E5)

5. **Microsoft Intune:**
   - Intune Plan 2 (device management)

6. **Microsoft Purview:**
   - Purview Compliance (DLP, Information Protection)
   - Or Microsoft 365 E5 Compliance

### Optional Enhancements
- Microsoft Defender Vulnerability Management (standalone or add-on)
- Azure Dedicated Host (physical isolation)
- Azure Confidential Computing VMs
- Microsoft Security Copilot

---

## KEY POLICY INITIATIVES TO DEPLOY

### Regulatory Compliance Initiatives (Built-in)
1. **NIST SP 800-53 Rev. 5** - 698 policies
2. **ISO/IEC 27001:2022** - 59 policies  
3. **PCI DSS v4.0.1** - 213 policies
4. **CIS Microsoft Azure Foundations Benchmark 1.4.0** - Multiple controls

### Security Baseline Initiatives (Custom)
1. **NCA CSCC Critical Systems Initiative** (Custom)
   - Combine all policies mapped to CSCC controls
   - Assign to critical system resource groups
   - Deploy with `deployIfNotExist` and `deny` effects

### Geographic Restrictions
1. **Saudi Arabia Region Enforcement**
   - Allowed locations: Saudi Arabia Central, Saudi Arabia North
   - Apply to all resource types
   - Exception process for global services

---

## CUSTOM POLICY EXAMPLES

### Policy 1: Enforce Critical System Tagging
```json
{
  "mode": "Indexed",
  "policyRule": {
    "if": {
      "allOf": [
        {"field": "type", "equals": "Microsoft.Compute/virtualMachines"},
        {"field": "tags['CriticalSystem']", "exists": "false"}
      ]
    },
    "then": {"effect": "deny"}
  }
}
```

### Policy 2: Enforce Saudi Arabia Regions
```json
{
  "mode": "Indexed",
  "policyRule": {
    "if": {
      "not": {
        "field": "location",
        "in": ["saudiarabia", "saudiarabianorth"]
      }
    },
    "then": {"effect": "deny"}
  }
}
```

### Policy 3: Require MFA for All Users (Audit)
```json
{
  "mode": "All",
  "policyRule": {
    "if": {
      "allOf": [
        {"field": "type", "equals": "Microsoft.Compute/virtualMachines"},
        {"value": "[requestContext().principal.mfaEnabled]", "equals": "false"}
      ]
    },
    "then": {"effect": "audit"}
  }
}
```

---

## DEFENDER FOR CLOUD RECOMMENDATIONS MAPPING

### High Priority Recommendations
1. **MFA should be enabled on accounts with owner permissions** → NCA 2-2-1-3, 2-2-1-4
2. **System updates should be installed** → NCA 2-3-1-3
3. **Endpoint protection should be installed** → NCA 2-3-1-2  
4. **Management ports should be closed** → NCA 2-4-1-3
5. **DDoS Protection should be enabled** → NCA 2-4-1-8
6. **Diagnostic logs should be enabled** → NCA 2-11-1-1
7. **Backup should be enabled** → NCA 2-8-1-1
8. **Vulnerability assessment should be enabled** → NCA 2-9-1-1
9. **Transparent data encryption should be enabled** → NCA 2-7-1-2

---

## MICROSOFT DEFENDER PLANS MAPPING TO NCA CSCC

| Defender Plan | NCA CSCC Controls | Key Capabilities |
|---------------|-------------------|------------------|
| **Defender CSPM** | 1-2, 1-4, 4-2 | Attack paths, Cloud security explorer, Custom recommendations |
| **Defender for Servers Plan 2** | 2-3, 2-9, 2-11 | Vulnerability assessment, File integrity monitoring, Just-in-time access |
| **Defender for Storage** | 2-6, 2-7 | Malware scanning, Sensitive data discovery, Activity logs |
| **Defender for SQL** | 2-2-1-8, 2-6, 2-9 | Vulnerability assessment, Threat detection, Data classification |
| **Defender for Containers** | 2-3, 2-9, 2-13 | Image scanning, Runtime protection, Kubernetes security |
| **Defender for Key Vault** | 2-7 | Unusual access patterns, Threat detection |
| **Defender for App Service** | 2-12, 2-13 | Web app protection, Threat detection |
| **Defender for DNS** | 2-4 | DNS threat detection |

---

## SENTINEL ANALYTICS RULES FOR NCA CSCC

### Identity Protection (NCA 2-2)
- Multiple failed login attempts
- Sign-in from suspicious locations
- Impossible travel
- Privilege escalation
- Service principal anomalies

### Network Security (NCA 2-4)
- Port scanning detected
- Traffic to malicious IPs
- Unusual outbound traffic
- Firewall rule changes
- NSG modifications

### Data Protection (NCA 2-6)
- Mass file deletion
- Large data downloads
- Unusual data access patterns
- Sensitive data exfiltration

### Logging and Monitoring (NCA 2-11)
- Log deletion attempts
- Audit log tampering
- Diagnostic settings disabled
- Security tools disabled

---

## COMPLIANCE MONITORING DASHBOARD

### Key Metrics to Track
1. **Secure Score** - Overall security posture (0-100%)
2. **Policy Compliance** - % resources compliant with NCA policies
3. **Vulnerability Exposure** - Number of high/critical vulnerabilities
4. **Backup Coverage** - % critical systems with backup enabled
5. **Log Retention Compliance** - All resources meeting 18-month retention
6. **MFA Adoption** - % users with MFA enabled
7. **Patching Compliance** - % systems with latest updates
8. **Incident Response Time** - Mean time to detect (MTTD) and respond (MTTR)

### Quarterly Review Checklist
- [ ] Access reviews completed (NCA 2-2-2)
- [ ] Backup restore test performed (NCA 2-8-2)
- [ ] Penetration test conducted (NCA 2-10-2)
- [ ] Configuration reviews completed (NCA 2-3-1-6, 2-4-1-2)
- [ ] DR test failover completed (NCA 3-1-1-3)
- [ ] Risk register updated (NCA 1-2-1-2)
- [ ] Vulnerability assessments current (NCA 2-9-2)
- [ ] Policy compliance reports generated (NCA 1-4-1)

---

## AUTOMATION AND REMEDIATION

### Auto-Remediation Scenarios
1. **Missing MFA** → Conditional Access block + notification
2. **Unencrypted Storage** → Deploy with TLS enforcement
3. **Missing Backup** → Configure backup policy
4. **Open Management Ports** → Apply NSG rule to block
5. **Missing Diagnostic Logs** → Enable diagnostic settings
6. **Outdated TLS** → Update to TLS 1.2
7. **Missing Tags** → Inherit from resource group
8. **Public Endpoint** → Deploy private endpoint

### Logic Apps / Automation Account Workflows
- Automated incident response playbooks
- Backup verification scripts
- Compliance report generation
- Security alert enrichment
- Automated remediation tasks

---

## DOCUMENTATION REQUIREMENTS

### Required Documentation (Store in Azure Blob - Immutable)
1. Cybersecurity Strategy (NCA 1-1)
2. Risk Assessment Reports (NCA 1-2)
3. Risk Register (NCA 1-2)
4. Penetration Test Reports (NCA 2-10)
5. DR Plans and Test Results (NCA 3-1)
6. Compliance Audit Reports (NCA 1-4)
7. Incident Response Procedures
8. Change Management Records (NCA 1-3)
9. Access Review Results (NCA 2-2)
10. Backup and Recovery Procedures (NCA 2-8)

### Azure Services for Documentation
- **Azure Blob Storage** - Immutable storage with WORM
- **Azure DevOps** - Version control for policies/procedures
- **SharePoint Online** - Collaborative editing
- **Microsoft Purview** - Records management

---

## CONTACT AND SUPPORT

### Microsoft Support Channels
- **Azure Support Plans** - Professional Direct, Premier
- **Microsoft Security Response Center (MSRC)** - Security issues
- **FastTrack for Azure** - Deployment assistance
- **Microsoft Partner Network** - Certified partners in Saudi Arabia

### Saudi Arabia Azure Resources
- **Azure Regions:** Saudi Arabia Central (Riyadh), Saudi Arabia North (Jeddah)
- **Local Microsoft Office:** Riyadh, Saudi Arabia
- **Azure Documentation:** https://docs.microsoft.com/en-us/azure/
- **Compliance Documentation:** https://aka.ms/AzureCompliance

---

## CHANGE LOG

**Version:** 1.0  
**Date:** October 2025  
**Created by:** Azure Security Architecture Team  
**Review Cycle:** Quarterly  
**Next Review:** January 2026

---

*This mapping provides comprehensive coverage of NCA CSCC requirements using Azure Policy and Microsoft Defender for Cloud capabilities. All controls can be implemented, monitored, and alerted on through the Azure platform with appropriate licensing.*
