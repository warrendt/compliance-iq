# NDMO Azure Implementation Checklist

## Pre-Implementation

- [ ] Review NDMO official documentation
- [ ] Obtain necessary licenses (Defender for Cloud, Purview, Entra ID P2)
- [ ] Identify critical data assets and systems
- [ ] Define compliance scope (subscriptions, resource groups)
- [ ] Assemble implementation team
- [ ] Schedule executive briefing

## Phase 1: Foundation (Weeks 1-4)

### Microsoft Defender for Cloud
- [ ] Enable Defender for Servers P2 on all VMs
- [ ] Enable Defender for Storage on all storage accounts
- [ ] Enable Defender for SQL on all SQL servers and databases
- [ ] Enable Defender for Containers on AKS clusters
- [ ] Enable Defender for Key Vault
- [ ] Enable Defender for Resource Manager
- [ ] Enable Defender for DNS
- [ ] Enable Defender for APIs (if applicable)
- [ ] Configure continuous export to Log Analytics
- [ ] Setup email notifications for security team

### Azure Policy
- [ ] Assign Microsoft Cloud Security Benchmark initiative
- [ ] Enable encryption-at-rest policies (Audit mode initially)
- [ ] Enable encryption-in-transit policies (Audit mode initially)
- [ ] Configure RBAC audit policies
- [ ] Enable diagnostic settings policies
- [ ] Review policy compliance dashboard
- [ ] Create exemptions for legacy systems (if needed)
- [ ] Document policy exceptions

### Logging & Monitoring
- [ ] Create Log Analytics workspace(s)
- [ ] Configure 90-day retention minimum
- [ ] Enable Activity Log diagnostics
- [ ] Configure resource diagnostics for all critical resources
- [ ] Setup log archival to storage accounts (for 1+ year retention)
- [ ] Create action groups for security team
- [ ] Create action groups for compliance team
- [ ] Test alert notifications

## Phase 2: Data Governance & Classification (Weeks 5-8)

### Microsoft Purview Setup
- [ ] Create Microsoft Purview account
- [ ] Configure Azure data sources
- [ ] Configure on-premises data sources (if applicable)
- [ ] Enable auto-discovery and scanning
- [ ] Review discovered data assets
- [ ] Configure scan schedules

### Data Classification
- [ ] Deploy Microsoft 365 sensitivity labels to Azure
- [ ] Configure automatic classification rules
- [ ] Train custom classifiers (if needed)
- [ ] Enable SQL Data Discovery & Classification
- [ ] Configure classification policies for storage
- [ ] Review classification results
- [ ] Create classification register
- [ ] Establish classification review schedule

### Data Governance
- [ ] Define governance domains in Purview
- [ ] Create business glossary
- [ ] Map data owners and stewards
- [ ] Configure data lineage tracking
- [ ] Enable data catalog search
- [ ] Create data governance policies
- [ ] Document data lifecycle procedures

### Access Control
- [ ] Enable Microsoft Entra ID P2
- [ ] Configure Conditional Access policies
- [ ] Enable MFA for all admin accounts
- [ ] Enable MFA for all users (recommended)
- [ ] Configure PIM for Azure AD roles
- [ ] Configure PIM for Azure resource roles
- [ ] Enable JIT VM access
- [ ] Configure RBAC policies with least privilege
- [ ] Conduct initial access review
- [ ] Schedule quarterly access reviews

## Phase 3: Monitoring & Alerting (Weeks 9-12)

### Security Monitoring
- [ ] Configure security alert rules in Defender for Cloud
- [ ] Create custom alert rules in Azure Monitor
- [ ] Configure alerting for encryption violations
- [ ] Configure alerting for access control violations
- [ ] Configure alerting for policy violations
- [ ] Configure alerting for backup failures
- [ ] Test all alert rules
- [ ] Fine-tune alert thresholds

### Dashboards & Reporting
- [ ] Create NDMO Compliance Dashboard
- [ ] Create Security Posture Dashboard
- [ ] Create Data Protection Dashboard
- [ ] Create Access Control Dashboard
- [ ] Create Data Classification Dashboard
- [ ] Configure dashboard sharing permissions
- [ ] Setup automated weekly security reports
- [ ] Setup automated monthly compliance reports

### Microsoft Sentinel (Optional)
- [ ] Deploy Sentinel workspace
- [ ] Configure Defender for Cloud connector
- [ ] Configure Azure Activity connector
- [ ] Configure Microsoft Entra ID connector
- [ ] Configure Azure Policy connector
- [ ] Enable built-in analytics rules
- [ ] Create custom analytics rules
- [ ] Configure automation playbooks
- [ ] Test incident response workflows

## Phase 4: Privacy & Compliance (Weeks 13-16)

### Privacy Controls
- [ ] Configure Microsoft Purview DLP policies
- [ ] Enable endpoint DLP (if applicable)
- [ ] Configure data subject rights request automation
- [ ] Setup consent tracking mechanisms
- [ ] Configure retention labels and policies
- [ ] Enable records management
- [ ] Test DSR workflows
- [ ] Document privacy procedures

### Compliance Monitoring
- [ ] Enable Microsoft Purview Compliance Manager
- [ ] Configure NDMO compliance assessment
- [ ] Configure ISO 27001 assessment (if applicable)
- [ ] Map controls to NDMO requirements
- [ ] Assign improvement actions
- [ ] Setup compliance score tracking
- [ ] Configure compliance reporting
- [ ] Schedule compliance reviews

### Backup & DR
- [ ] Configure Azure Backup policies
- [ ] Enable backup for all critical VMs
- [ ] Enable backup for all databases
- [ ] Enable backup for file shares
- [ ] Configure backup retention (align with NDMO)
- [ ] Enable soft delete for backups
- [ ] Test restore procedures
- [ ] Configure Azure Site Recovery (for DR)
- [ ] Conduct DR drill
- [ ] Document backup/restore procedures

### Audit & Compliance
- [ ] Verify all audit logs are enabled
- [ ] Configure audit log retention (minimum 90 days)
- [ ] Setup long-term audit log archival (1+ year)
- [ ] Enable SQL auditing with 90+ day retention
- [ ] Configure audit alerts for critical actions
- [ ] Create audit trail documentation
- [ ] Establish audit log review procedures
- [ ] Schedule quarterly audit reviews

## Phase 5: Validation & Optimization (Weeks 17-20)

### Compliance Validation
- [ ] Conduct internal NDMO compliance audit
- [ ] Review all 15 domains for compliance
- [ ] Verify 77 controls implementation
- [ ] Validate 191 specifications
- [ ] Document compliance gaps
- [ ] Create remediation plan for gaps
- [ ] Generate compliance evidence package
- [ ] Present findings to management

### Security Testing
- [ ] Conduct vulnerability assessment
- [ ] Perform penetration testing (if required)
- [ ] Test incident response procedures
- [ ] Validate backup and restore procedures
- [ ] Test disaster recovery procedures
- [ ] Review security alert effectiveness
- [ ] Optimize alert thresholds
- [ ] Document test results

### Optimization
- [ ] Review and optimize license utilization
- [ ] Optimize log ingestion and retention
- [ ] Fine-tune policy assignments
- [ ] Optimize classification rules
- [ ] Review and optimize RBAC assignments
- [ ] Optimize Defender for Cloud coverage
- [ ] Review cost optimization opportunities
- [ ] Update documentation

### Training & Documentation
- [ ] Conduct security team training
- [ ] Conduct compliance team training
- [ ] Conduct IT admin training
- [ ] Conduct user awareness training
- [ ] Document all procedures and runbooks
- [ ] Create incident response playbooks
- [ ] Document escalation procedures
- [ ] Create user guides

## Ongoing Operations

### Daily Tasks
- [ ] Review security alerts
- [ ] Triage incidents
- [ ] Monitor backup job status
- [ ] Review critical system logs

### Weekly Tasks
- [ ] Review security dashboard
- [ ] Analyze alert trends
- [ ] Update incident status
- [ ] Review access logs
- [ ] Generate weekly security report

### Monthly Tasks
- [ ] Comprehensive security review
- [ ] Policy compliance review
- [ ] Classification accuracy review
- [ ] Access rights review
- [ ] Backup validation
- [ ] Update security documentation
- [ ] Generate monthly compliance report
- [ ] Present to security committee

### Quarterly Tasks
- [ ] Full NDMO compliance assessment
- [ ] Vulnerability management review
- [ ] Incident response plan review
- [ ] Disaster recovery drill
- [ ] Access certification
- [ ] Review and update policies
- [ ] Security awareness training
- [ ] Generate quarterly risk report

### Annual Tasks
- [ ] Full NDMO compliance audit
- [ ] External security assessment
- [ ] Penetration testing
- [ ] Business continuity plan review
- [ ] Update security architecture
- [ ] Review and update compliance frameworks
- [ ] License optimization review
- [ ] Strategic security planning

## Key Metrics to Track

### Security Metrics
- [ ] Secure Score (Target: >80%)
- [ ] Mean Time to Detect (Target: <15 min)
- [ ] Mean Time to Respond (Target: <1 hour critical)
- [ ] Critical Vulnerabilities (Target: 0)
- [ ] High Vulnerabilities (Target: <10)
- [ ] Open Security Alerts (Target: <5)

### Compliance Metrics
- [ ] NDMO Compliance Score (Target: >95%)
- [ ] Policy Compliance Rate (Target: >98%)
- [ ] Failed Controls (Target: <5)
- [ ] Data Classification Coverage (Target: >95%)
- [ ] Backup Compliance (Target: 100%)
- [ ] Audit Log Retention Compliance (Target: 100%)

### Operational Metrics
- [ ] Incident Response Time (Target: <4 hours avg)
- [ ] False Positive Rate (Target: <10%)
- [ ] Automated Remediation Rate (Target: >50%)
- [ ] Backup Success Rate (Target: >99%)
- [ ] Encryption Coverage (Target: 100%)

## Approval & Sign-off

- [ ] Security Team Lead: _________________ Date: _______
- [ ] Compliance Officer: _________________ Date: _______
- [ ] IT Manager: _________________ Date: _______
- [ ] CISO/Security Director: _________________ Date: _______
- [ ] CIO/CTO: _________________ Date: _______

## Notes & Comments

_______________________________________________________________________________
_______________________________________________________________________________
_______________________________________________________________________________
_______________________________________________________________________________

## Document Version Control

**Version:** 1.0
**Last Updated:** October 29, 2025
**Next Review:** January 2026
