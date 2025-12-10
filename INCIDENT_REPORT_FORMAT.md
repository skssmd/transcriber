# Incident Report Format

## Overview

When you select **"Incident Report"** as the meeting type, the AI will generate a comprehensive, formal investigation report following a structured format similar to professional incident investigation documentation.

---

## Report Structure

### 1. **Summary**
Comprehensive overview including:
- What happened
- Who was involved (with names)
- When and where it occurred
- Why it's being investigated

### 2. **Incident Report (Detailed Structure)**

#### **Background**
- Context and history
- Parties involved and their relationships
- Relevant prior incidents or patterns
- Organizational/situational context

#### **Key Facts**
Bulleted list of specific facts including:
- Names of all parties
- Specific actions taken
- Concrete details and observations
- Verifiable information

#### **Timeline**
Chronological breakdown by time periods:
```json
{
  "time_period": "Morning Visit - 9:00 AM",
  "events": [
    "Who did what, where, with specific dialogue",
    "Actions, reactions, and outcomes",
    "All relevant details for this period"
  ]
}
```

#### **Concerns Identified**
Categorized by type:
- **Policy Violations**: What policies were violated and how
- **Risk Assessment Failures**: Missed risk assessments
- **Documentation Failures**: What wasn't documented
- **Professional Boundaries**: Boundary violations
- **Other Concerns**: Additional issues

#### **Evidence Collected**
- What evidence exists
- Who collected it
- When it was collected
- Type of evidence (video, photos, documents, statements)

#### **Parties Involved**
For each person:
- Full name or identifier
- Role/title
- Detailed description of their involvement

### 3. **Conclusion**
Comprehensive final assessment:
- Policy violations that occurred
- Implications of the incident
- Outcome of investigation
- Systemic issues identified

### 4. **Action Items**
Specific next steps:
- Corrective actions (who does what)
- Training requirements (what and for whom)
- Follow-up items (monitoring/review)
- Policy changes (if applicable)

---

## Key Features

### ✅ Name Extraction
The AI is specifically instructed to:
- Extract ALL names mentioned
- Include first names, last names, roles, titles
- Identify relationships between parties
- Document who said what and who did what

### ✅ Detailed Timeline
- Chronological order
- Specific time periods
- Comprehensive event documentation
- Direct quotes where relevant

### ✅ Formal Tone
- Professional investigation language
- Objective and factual
- Comprehensive documentation
- No detail too small

### ✅ Structured Categories
- Organized by concern type
- Easy to navigate
- Comprehensive coverage
- Clear categorization

---

## Example Output Structure

```json
{
  "summary": "Investigation into incident involving unauthorized visitor at Dean's residence on Sunday. Care worker Khalipha allowed an unknown person (Jay) to enter the service user's home to retrieve a phone, violating visitor protocols and failing to report the incident to management.",
  
  "incident_report": {
    "background": "Dean is a service user with full mental capacity but mobility issues. He has a history of having friends over when he has money, followed by claims of missing funds. Police previously warned that no visitors except carers should be allowed. Social services case was closed after Dean refused help.",
    
    "key_facts": [
      "Khalipha (care worker) allowed Jay (unknown male) into Dean's house on Sunday afternoon",
      "Jay came to retrieve his phone left from previous night's party",
      "Dean appeared angry but said 'Let him in' when asked",
      "Jay apologized to Dean, retrieved disassembled phone, and left within 5 minutes",
      "Khalipha did not report the incident to management",
      "House showed evidence of party - cigarettes, popcorn, foils scattered",
      "Dean's bank card showed only £11 remaining, down from expected £1000+"
    ],
    
    "timeline": [
      {
        "time_period": "Morning Visit - Lunchtime",
        "events": [
          "Khalipha arrived at Dean's house, door was unlocked",
          "Dean sent Khalipha to shop with his bank card and PIN",
          "Card declined at Tesco ATM - balance showed £11.95",
          "Dean expressed surprise, claimed he should have over £1000",
          "Khalipha gave Dean his medication and went home"
        ]
      },
      {
        "time_period": "Afternoon Visit - 4:30 PM",
        "events": [
          "Khalipha returned for second call (social call)",
          "Found house extremely dirty - evidence of party",
          "Khalipha took video of messy house as evidence",
          "While taking bins outside, encountered tall man at door",
          "Man said: 'I'm looking for Dean, I'm here to take my phone'",
          "Khalipha consulted Dean, who said 'Let him in'",
          "Jay entered, apologized to Dean, retrieved phone from bedroom",
          "Jay left immediately without extended interaction"
        ]
      }
    ],
    
    "concerns_identified": [
      {
        "category": "Policy Violations",
        "details": [
          "Allowed unauthorized person into service user's home without proper verification",
          "Did not ask visitor's name before consulting Dean",
          "Violated previous police warning about no visitors",
          "Accepted service user's PIN (should use contactless only)"
        ]
      },
      {
        "category": "Risk Assessment Failures",
        "details": [
          "No risk assessment conducted before allowing entry",
          "Service user safety not prioritized despite unknown visitor",
          "Relied on Dean's consent without independent judgment"
        ]
      },
      {
        "category": "Documentation Failures",
        "details": [
          "Incident not reported to management",
          "No notes written about visitor",
          "No incident report filed",
          "Rationale: 'Nothing happened, guy just came and left'"
        ]
      },
      {
        "category": "Professional Boundaries",
        "details": [
          "Has Dean's friend's (Shock) phone number",
          "Shared video of messy house with Shock (GDPR violation)",
          "Personal relationship with service user's associates"
        ]
      }
    ],
    
    "evidence_collected": [
      "Video of messy house taken by Khalipha (later deleted after sending to Shock)",
      "Photo of ATM balance showing £11.95",
      "Khalipha's verbal account of events",
      "Pattern of previous incidents reported by Khalipha (blood, beatings, medication theft)"
    ],
    
    "parties_involved": [
      {
        "name": "Khalipha (Care Worker)",
        "involvement": "Primary care worker who allowed unauthorized visitor into service user's home, failed to report incident, and shared confidential video with third party"
      },
      {
        "name": "Dean (Service User)",
        "involvement": "Service user with capacity who authorized visitor entry but has history of exploitation by friends and financial issues"
      },
      {
        "name": "Jay (Visitor)",
        "involvement": "Unauthorized visitor who came to retrieve phone left from previous night's party, apologized to Dean for wanting to smoke drugs in his house"
      },
      {
        "name": "Shock (Dean's Friend)",
        "involvement": "Dean's friend who received confidential video from Khalipha, brings Dean cigarettes and food"
      },
      {
        "name": "Priscilla (Manager)",
        "involvement": "Management conducting investigation, providing guidance on incident reporting procedures"
      },
      {
        "name": "Andrea (Manager)",
        "involvement": "Management providing guidance on risk assessment, documentation, professional boundaries, and GDPR compliance"
      },
      {
        "name": "Camelita (Management)",
        "involvement": "Management team member present during investigation"
      }
    ]
  },
  
  "conclusion": "This incident reveals multiple policy violations including unauthorized visitor access, failure to report, and GDPR breach. While Khalipha's intentions were to respect Dean's autonomy, she failed to follow proper safeguarding procedures. The investigation identified training gaps in risk assessment, incident reporting, and professional boundaries. Khalipha has committed to improved practice going forward. The ongoing concern is Dean's pattern of exploitation by friends despite having capacity, requiring creative safeguarding solutions that respect autonomy while providing protection.",
  
  "action_items": [
    "Khalipha to complete assigned online training modules on incident reporting, risk assessment, and GDPR compliance",
    "Management to provide increased supervision and spot checks of Khalipha's work",
    "Khalipha to call management before making any uncertain decisions at Dean's residence",
    "Implement protocol: Do not open door for anyone at Dean's house except authorized carers/professionals",
    "If Dean insists on visitors, Khalipha to call management and let Dean open door himself",
    "All incidents to be documented and reported immediately going forward",
    "No accepting PINs from service users - use contactless only",
    "No personal contact with service user's friends/family",
    "Management to review Khalipha's notes and provide feedback on documentation quality",
    "Assess need for additional safeguarding measures for Dean given pattern of exploitation"
  ]
}
```

---

## Comparison: Regular Meeting vs Incident Report

### Regular Meeting
- Sections with context-based notes
- Summary of discussions
- Conclusion
- Action items

### Incident Report
- **All of the above PLUS:**
- Detailed background and context
- Comprehensive key facts with names
- Chronological timeline by period
- Categorized concerns (violations, failures, boundaries)
- Evidence documentation
- Parties involved with roles and involvement
- Formal investigation tone
- Systemic issue identification

---

## Tips for Best Results

1. **Speak Clearly**: Mention names clearly and frequently
2. **Be Specific**: Include times, dates, locations
3. **State Roles**: Identify people's roles/titles
4. **Describe Actions**: Who did what, when, where
5. **Include Dialogue**: Direct quotes are valuable
6. **Mention Evidence**: Photos, videos, documents, witnesses
7. **Discuss Concerns**: Policy violations, risks, failures
8. **Identify Outcomes**: What happened as a result

---

## When to Use Incident Report Mode

✅ **Use for:**
- Workplace incidents
- Policy violations
- Safety concerns
- Investigations
- Disciplinary matters
- Compliance issues
- Formal reviews
- Safeguarding concerns

❌ **Don't use for:**
- Regular team meetings
- Planning sessions
- Brainstorming
- Status updates
- Casual discussions

---

## Export Options

Once generated, you can export the incident report as:
- **Markdown (.md)**: Formatted document with headers and structure
- **JSON**: Raw data for further processing

The markdown export will include all sections formatted with proper headers matching the structure shown in `meeting_minutes.md`.
