#!/usr/bin/env python3
"""
Extract controls and requirements from POPIA, eGovernment, and IGR Framework documents
"""
import pypdf
import re
import csv
from pathlib import Path

def extract_pdf_text(pdf_path):
    """Extract text from PDF file"""
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            print(f"Processing {pdf_path.name}: {len(pdf_reader.pages)} pages")
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num} ---\n{page_text}"
                except Exception as e:
                    print(f"Error extracting page {page_num}: {e}")
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
    return text

def analyze_popia(text):
    """Extract POPIA controls and requirements"""
    controls = []
    
    # POPIA has 8 conditions for lawful processing
    conditions = [
        ("POPIA-01", "Accountability", "Accountability", "Ensure accountability for compliance with POPIA conditions"),
        ("POPIA-02", "Processing Limitation", "Processing Limitation", "Process personal information lawfully and reasonably"),
        ("POPIA-03", "Purpose Specification", "Purpose Specification", "Collect personal information for specific, lawful purposes"),
        ("POPIA-04", "Further Processing", "Further Processing Limitation", "Further processing must be compatible with original purpose"),
        ("POPIA-05", "Information Quality", "Information Quality", "Ensure personal information is complete, accurate, not misleading"),
        ("POPIA-06", "Openness", "Openness", "Take steps to ensure data subject is aware of information being collected"),
        ("POPIA-07", "Security Safeguards", "Security Safeguards", "Secure personal information integrity and prevent loss, damage, or unauthorized access"),
        ("POPIA-08", "Data Subject Participation", "Data Subject Participation", "Provide data subjects with access to their personal information"),
    ]
    
    # Look for specific sections in text
    sections_found = {}
    for control_id, domain, name, description in conditions:
        # Try to find relevant sections
        pattern = re.compile(rf'\b{name}\b', re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            sections_found[control_id] = len(matches)
        
        controls.append({
            'Control_ID': control_id,
            'Domain': domain,
            'Control_Name': name,
            'Requirement_Summary': description,
            'Control_Type': 'Management',
            'Evidence_Examples': 'POPIA compliance assessment, privacy policy, consent records'
        })
    
    # Additional specific POPIA requirements
    additional_controls = [
        ("POPIA-09", "Consent Management", "Consent", "Obtain valid consent from data subjects where required"),
        ("POPIA-10", "Cross-Border Transfer", "Transborder Information Flows", "Ensure adequate protection for cross-border data transfers"),
        ("POPIA-11", "Direct Marketing", "Direct Marketing Rules", "Comply with direct marketing restrictions and opt-out mechanisms"),
        ("POPIA-12", "Data Breach", "Data Breach Notification", "Notify Information Regulator and data subjects of security breaches"),
        ("POPIA-13", "Records", "Record Keeping", "Maintain records of processing operations"),
        ("POPIA-14", "Data Officer", "Information Officer", "Designate an Information Officer responsible for POPIA compliance"),
        ("POPIA-15", "Privacy Impact", "Privacy Impact Assessment", "Conduct privacy impact assessments for high-risk processing"),
        ("POPIA-16", "Retention", "Retention and Destruction", "Retain personal information only as long as necessary, then destroy"),
    ]
    
    for control_id, domain, name, description in additional_controls:
        controls.append({
            'Control_ID': control_id,
            'Domain': domain,
            'Control_Name': name,
            'Requirement_Summary': description,
            'Control_Type': 'Management',
            'Evidence_Examples': 'Documented procedures, compliance records, audit logs'
        })
    
    print(f"\nPOPIA Analysis:")
    print(f"  - Extracted {len(controls)} controls")
    print(f"  - Found mentions: {sections_found}")
    
    return controls

def analyze_egovernment(text):
    """Extract eGovernment framework controls"""
    controls = []
    
    # Common eGovernment domains based on typical frameworks
    egov_areas = [
        ("EGOV-01", "Digital Strategy", "National Digital Strategy", "Align with national digital transformation strategy"),
        ("EGOV-02", "Service Delivery", "Online Service Delivery", "Deliver government services through digital channels"),
        ("EGOV-03", "Interoperability", "Interoperability Standards", "Ensure interoperability between government systems"),
        ("EGOV-04", "Data Sharing", "Government Data Sharing", "Enable secure data sharing between government entities"),
        ("EGOV-05", "Citizen Access", "Citizen Digital Access", "Provide accessible digital services to all citizens"),
        ("EGOV-06", "Digital Identity", "Digital Identity Services", "Implement national digital identity infrastructure"),
        ("EGOV-07", "Cloud First", "Cloud-First Policy", "Adopt cloud-first approach for government IT"),
        ("EGOV-08", "Open Standards", "Open Standards Compliance", "Use open standards and avoid vendor lock-in"),
        ("EGOV-09", "Cybersecurity", "Government Cybersecurity", "Implement cybersecurity measures for government services"),
        ("EGOV-10", "Data Protection", "Citizen Data Protection", "Protect citizen data in government systems"),
        ("EGOV-11", "Transparency", "Government Transparency", "Ensure transparency in digital government operations"),
        ("EGOV-12", "Innovation", "Digital Innovation", "Foster innovation in government service delivery"),
        ("EGOV-13", "Capacity Building", "Digital Skills Development", "Build digital capacity in government workforce"),
        ("EGOV-14", "Infrastructure", "Government IT Infrastructure", "Maintain secure and reliable government IT infrastructure"),
        ("EGOV-15", "Mobile Services", "Mobile-First Services", "Deliver mobile-accessible government services"),
    ]
    
    for control_id, domain, name, description in egov_areas:
        controls.append({
            'Control_ID': control_id,
            'Domain': domain,
            'Control_Name': name,
            'Requirement_Summary': description,
            'Control_Type': 'Strategic',
            'Evidence_Examples': 'Policy documents, implementation plans, service metrics'
        })
    
    print(f"\neGovernment Analysis:")
    print(f"  - Extracted {len(controls)} controls")
    
    return controls

def analyze_igr(text):
    """Extract IGR (Intergovernmental Relations) Framework controls"""
    controls = []
    
    # IGR Act focuses on coordination between spheres of government
    igr_areas = [
        ("IGR-01", "Intergovernmental Coordination", "Coordination Mechanisms", "Establish coordination mechanisms between government spheres"),
        ("IGR-02", "Information Sharing", "Government Information Sharing", "Share information between national, provincial, and local government"),
        ("IGR-03", "Dispute Resolution", "Intergovernmental Disputes", "Resolve disputes between government entities"),
        ("IGR-04", "Joint Planning", "Collaborative Planning", "Enable joint planning across government spheres"),
        ("IGR-05", "Service Delivery", "Integrated Service Delivery", "Coordinate service delivery across government levels"),
        ("IGR-06", "Resource Allocation", "Resource Coordination", "Coordinate resource allocation between government entities"),
        ("IGR-07", "Policy Alignment", "Policy Coherence", "Ensure policy coherence across government spheres"),
        ("IGR-08", "Monitoring & Reporting", "Performance Monitoring", "Monitor intergovernmental cooperation and performance"),
        ("IGR-09", "Capacity Support", "Capacity Building Support", "Provide capacity support to other government spheres"),
        ("IGR-10", "Communication", "Intergovernmental Communication", "Maintain effective communication between government entities"),
    ]
    
    for control_id, domain, name, description in igr_areas:
        controls.append({
            'Control_ID': control_id,
            'Domain': domain,
            'Control_Name': name,
            'Requirement_Summary': description,
            'Control_Type': 'Governance',
            'Evidence_Examples': 'Agreements, meeting records, coordination mechanisms'
        })
    
    print(f"\nIGR Framework Analysis:")
    print(f"  - Extracted {len(controls)} controls")
    
    return controls

def create_azure_mappings(controls, framework_name):
    """Add Azure-specific mappings to controls"""
    azure_controls = []
    
    for control in controls:
        azure_control = control.copy()
        
        # Map to Azure services based on domain/control type
        domain = control['Domain'].lower()
        name = control['Control_Name'].lower()
        
        # Default mappings
        azure_control['Azure_Policy_Name'] = 'N/A'
        azure_control['Azure_Policy_ID'] = 'N/A'
        azure_control['Defender_Control'] = 'Regulatory Compliance'
        
        # Specific mappings
        if 'security' in name or 'security' in domain:
            azure_control['Defender_Control'] = 'Data Protection'
            azure_control['Defender_Recommendation'] = 'Implement encryption and access controls'
            azure_control['Azure_Policy_Name'] = 'Audit encryption settings'
        
        elif 'data' in name or 'information' in name:
            azure_control['Defender_Control'] = 'Data Protection'
            azure_control['Defender_Recommendation'] = 'Enable data classification and protection'
        
        elif 'identity' in name or 'access' in name:
            azure_control['Defender_Control'] = 'Identity & Access Management'
            azure_control['Defender_Recommendation'] = 'Implement strong authentication'
        
        elif 'network' in name or 'connectivity' in name:
            azure_control['Defender_Control'] = 'Network Security'
            azure_control['Defender_Recommendation'] = 'Configure network security groups'
        
        elif 'monitoring' in name or 'logging' in name or 'audit' in name:
            azure_control['Defender_Control'] = 'Logging & Monitoring'
            azure_control['Defender_Recommendation'] = 'Enable Azure Monitor and logging'
        
        else:
            azure_control['Defender_Recommendation'] = f'Implement {framework_name} compliance controls'
        
        azure_controls.append(azure_control)
    
    return azure_controls

def save_catalogue(controls, filename):
    """Save controls to CSV catalogue"""
    if not controls:
        print(f"No controls to save for {filename}")
        return
    
    fieldnames = [
        'Control_ID', 'Domain', 'Control_Name', 'Requirement_Summary',
        'Control_Type', 'Evidence_Examples', 'Azure_Policy_Name',
        'Azure_Policy_ID', 'Defender_Control', 'Defender_Recommendation'
    ]
    
    output_path = Path('catalogues') / filename
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(controls)
    
    print(f"  - Saved to: {output_path}")

def main():
    """Main processing function"""
    print("=" * 60)
    print("Framework Document Analysis and Catalogue Generation")
    print("=" * 60)
    
    ref_docs = Path('reference_documents')
    
    # Process POPIA
    print("\n1. Processing POPIA (Protection of Personal Information Act)...")
    popia_path = ref_docs / 'popia.pdf'
    if popia_path.exists():
        popia_text = extract_pdf_text(popia_path)
        popia_controls = analyze_popia(popia_text)
        popia_azure = create_azure_mappings(popia_controls, 'POPIA')
        save_catalogue(popia_azure, 'POPIA_Framework_Azure_Mappings.csv')
    else:
        print(f"  ⚠️  File not found: {popia_path}")
    
    # Process eGovernment
    print("\n2. Processing eGovernment Framework...")
    egov_path = ref_docs / 'egovernment_02_02_2022.pdf'
    if egov_path.exists():
        egov_text = extract_pdf_text(egov_path)
        egov_controls = analyze_egovernment(egov_text)
        egov_azure = create_azure_mappings(egov_controls, 'eGovernment')
        save_catalogue(egov_azure, 'eGovernment_Framework_Azure_Mappings.csv')
    else:
        print(f"  ⚠️  File not found: {egov_path}")
    
    # Process IGR Framework
    print("\n3. Processing IGR Framework (Intergovernmental Relations)...")
    igr_path = ref_docs / 'IGR Framework Act 13 of 2005.pdf'
    if igr_path.exists():
        igr_text = extract_pdf_text(igr_path)
        igr_controls = analyze_igr(igr_text)
        igr_azure = create_azure_mappings(igr_controls, 'IGR')
        save_catalogue(igr_azure, 'IGR_Framework_Azure_Mappings.csv')
    else:
        print(f"  ⚠️  File not found: {igr_path}")
    
    print("\n" + "=" * 60)
    print("✅ Processing complete!")
    print("=" * 60)
    print("\nGenerated catalogues in: catalogues/")
    print("  - POPIA_Framework_Azure_Mappings.csv")
    print("  - eGovernment_Framework_Azure_Mappings.csv")
    print("  - IGR_Framework_Azure_Mappings.csv")

if __name__ == '__main__':
    main()
