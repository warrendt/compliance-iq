# 🎉 NEW: Oman CDC Cloud Security Controls Framework

## What's New - January 2026

The Cloud Compliance Toolkit now includes the **Oman Cyber Defense Centre (CDC)** cloud security controls framework!

## 📦 What's Included

### Complete Azure Policy Initiative
Located in [`/framework/Oman CDC/`](framework/Oman%20CDC/):

- ✅ **37 Azure Policy Definitions** mapped to CDC controls
- ✅ **28 Controls** automated via Azure Policy (60% coverage)
- ✅ **PowerShell Deployment Script** for easy initiative creation
- ✅ **Comprehensive Documentation** (README + Quick Reference)
- ✅ **Implementation Roadmap** (14-week deployment plan)

### Control Catalog
Located in [`/catalogues/OmanCDC_Framework_Azure_Mappings.csv`](catalogues/OmanCDC_Framework_Azure_Mappings.csv):

- 📊 **47 Total Controls** across 3 categories
- 🔧 **Technical Requirements (CDC-TR-*)**: 16 controls
- 📋 **Policy Requirements (CDC-POL-*)**: 14 controls
- 📝 **Contractual Requirements (CDC-CON-*)**: 17 controls

## 🎯 Key Features

### Government-Specific Controls
- **Geographic Hosting Restrictions** - CDC approval required for data residency
- **CDC Approval Management** - 2-year validity with renewal tracking
- **Semi-Annual Reporting** - Structured audit reports to CDC
- **Secret Data Prohibition** - Enforcement of classified data restrictions

### Technical Security
- **Network Security**: Azure Firewall, DDoS Protection, NSG enforcement
- **Identity & Access**: MFA, RBAC, JIT access, geo-blocking
- **Data Protection**: Encryption at rest/transit, CMK, DLP
- **Logging & Monitoring**: 6-month minimum retention, SIEM integration
- **Endpoint Protection**: Antimalware, vulnerability assessment
- **Backup & DR**: Immutable backups, geo-redundant storage

### AI Governance
- **AI Application Usage** - Compliance with MTCIT policies
- **Training Data Restrictions** - Prohibition on customer data usage
- **Private Endpoints** - Secure AI service deployment

## 🚀 Quick Start

### 1. Deploy the Initiative

```powershell
cd "/path/to/cctoolkit_v1/framework/Oman CDC"
./CreateCDCInitiative.ps1 -AssignAfterCreation
```

### 2. Review Control Mappings

```bash
# View the comprehensive catalog
open catalogues/OmanCDC_Framework_Azure_Mappings.csv

# Or review the quick reference
open "framework/Oman CDC/CDC_Quick_Reference.md"
```

### 3. Configure Prerequisites

Before deploying to production:
- ✅ Complete data classification per Oman regulations (CDC-POL-01)
- ✅ Conduct risk assessment and documentation (CDC-POL-05)
- ✅ Obtain CDC geographic approval (CDC-POL-03)
- ✅ Enable Microsoft Defender for Cloud

### 4. Monitor Compliance

```powershell
# Check compliance status
Get-AzPolicyStateSummary -PolicySetDefinitionName "OmanCDC_Cloud_Compliance"

# Export compliance report
Get-AzPolicyState -PolicySetDefinitionName "OmanCDC_Cloud_Compliance" | 
  Export-Csv "CDC_Compliance_Report.csv"
```

## 📚 Documentation

### Main Files
- 📖 **[README.md](framework/Oman%20CDC/README.md)** - Complete implementation guide (300+ lines)
- 📋 **[Quick Reference](framework/Oman%20CDC/CDC_Quick_Reference.md)** - Fast lookup and deployment checklist
- 📊 **[Creation Summary](framework/Oman%20CDC/CREATION_SUMMARY.md)** - Detailed statistics and mappings

### Technical Files
- 🔧 **[CreateCDCInitiative.ps1](framework/Oman%20CDC/CreateCDCInitiative.ps1)** - Deployment script
- 📝 **[cdc_policies.json](framework/Oman%20CDC/cdc_policies.json)** - 37 Azure Policy definitions
- 🏷️ **[cdc_groups.json](framework/Oman%20CDC/cdc_groups.json)** - 28 control groups
- ⚙️ **[CDC_Initiative.json](framework/Oman%20CDC/CDC_Initiative.json)** - Complete initiative definition

## 🎨 Integration with Existing Frameworks

The Oman CDC framework complements other toolkit frameworks:

| Framework | Overlap Area | Oman CDC Controls |
|-----------|--------------|-------------------|
| **SAMA** (Saudi Arabia) | Financial sector, MFA, encryption | Similar identity & data protection |
| **ADHICS** (UAE Healthcare) | Data classification, encryption | Aligned data protection approach |
| **SITA** (South Africa Gov) | Sovereign cloud, data residency | Similar government requirements |
| **ISO 27001** | Security controls baseline | CDC requires ISO 27001 certification |

## 📊 Updated Toolkit Statistics

| Metric | Previous | New | Change |
|--------|----------|-----|--------|
| **Total Frameworks** | 7 | 8 | +1 |
| **Total Controls** | 181 | 228 | +47 |
| **Azure Policies** | 50+ | 60+ | +10 |
| **Geographic Coverage** | MENA + Africa | MENA + Africa | Expanded Oman |

## 🌍 Geographic Coverage

The toolkit now covers:

### Middle East
- 🇸🇦 **Saudi Arabia** - SAMA (Financial)
- 🇦🇪 **UAE** - CCC (Cloud), ADHICS (Healthcare)
- 🇴🇲 **Oman** - CDC (Government Cloud) ⭐ NEW

### Africa
- 🇿🇦 **South Africa** - SITA (Government), POPIA (Privacy), eGov, IGR

## ⚠️ Important Notes

### Manual Controls
**19 controls** require manual attestation:
- Most **CDC-POL-*** controls (governance, approvals)
- Most **CDC-CON-*** controls (contractual with provider)
- Operational controls (pen testing, incident response planning)

### Prerequisites
Before requesting CDC approval:
1. **Data Classification** - Complete and documented
2. **Risk Assessment** - Documented and approved
3. **Geographic Selection** - Approved regions identified
4. **Provider Verification** - ISO/SOC certifications confirmed

### Ongoing Requirements
- **Semi-Annual Reports** to CDC (CDC-POL-06)
- **CDC Approval Renewal** every 2 years (CDC-POL-11)
- **Quarterly Access Reviews** (best practice)
- **Annual Penetration Testing** (CDC-TR-05)

## 🔄 Next Steps

### For Organizations in Oman
1. Review the [CDC Quick Reference](framework/Oman%20CDC/CDC_Quick_Reference.md)
2. Complete data classification (CDC-POL-01)
3. Deploy the Azure Policy initiative
4. Configure Microsoft Defender for Cloud
5. Submit CDC approval request
6. Schedule semi-annual audit reports

### For Other Organizations
The Oman CDC framework provides excellent reference for:
- Government cloud security controls
- Data sovereignty requirements
- AI governance in government sector
- Cloud provider certification requirements

## 📞 Support

### Questions?
- Review the comprehensive [README.md](framework/Oman%20CDC/README.md)
- Check the [Quick Reference Guide](framework/Oman%20CDC/CDC_Quick_Reference.md)
- Open an issue in the repository

### Resources
- **Oman CDC**: https://cdc.om/
- **Azure Policy**: https://aka.ms/azurepolicy
- **Defender for Cloud**: https://aka.ms/defendercloud
- **Microsoft Trust Center**: https://servicetrust.microsoft.com/

---

## 🙏 Acknowledgments

Special thanks to:
- **Cyber Defense Centre (CDC) of Oman** for their comprehensive cloud security framework
- **Ministry of Transport, Communications and Information Technology (MTCIT)** of Oman
- Organizations in Oman adopting secure cloud practices

---

**Release Date**: January 26, 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✅

**Built with ❤️ for Secure Cloud Deployments in the Middle East**
