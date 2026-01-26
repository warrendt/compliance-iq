# AI Mapping Agent - Logging Guide

## Overview
Enhanced logging has been implemented to track the interaction between the AI mapping service and the Microsoft Learn MCP server. This enables fine-tuning and debugging of the agent's behavior.

## Logging Levels

- **DEBUG**: Detailed information for diagnostics (query construction, API calls, policy extraction details)
- **INFO**: General information about operation flow (mapping started, policies found, etc.)
- **WARNING**: Issues that don't prevent operation but should be noted
- **ERROR**: Errors that prevent specific operations

## What's Being Logged

### 1. Microsoft Learn API Interactions

#### Query Construction
- Original control name, domain, and description
- Query component lengths and truncation
- Final constructed query string and its length
- Example:
  ```
  INFO: Searching Microsoft Learn for: Establish cybersecurity policy
  DEBUG: Query components - name: 'Establish cybersecurity policy', domain: 'Cybersecurity Governance', desc: 'Define, approve, and annually review...'
  INFO: Built search query (length=145): Azure Policy Establish cybersecurity policy Cybersecurity Governance...
  ```

#### API Request/Response
- API endpoint URL
- Request parameters (search query, facets, limits)
- HTTP response status code
- Number of results returned
- Error response bodies (first 500 chars on failures)
- Example:
  ```
  INFO: Calling Microsoft Learn API: https://learn.microsoft.com/api/search
  DEBUG: Request params: {'search': '...', 'facet': 'category:Azure,products:Azure Policy', 'top': 5}
  INFO: Microsoft Learn API response: 200
  INFO: Microsoft Learn returned 3 results
  ```

### 2. Policy Extraction Process

#### Search Result Processing
- Number of search results to process
- For each result:
  - Title (truncated to 60 chars)
  - URL
  - Whether policy ID was found
  - Whether title contains "policy"
  - Decision to include/skip
- Example:
  ```
  DEBUG: Processing 3 search results for policy extraction
  DEBUG: Result 1: Azure Policy - Security Center recommendations...
  DEBUG:   URL: https://learn.microsoft.com/azure/governance/policy/...
  DEBUG:   ✓ Found policy ID: a1b2c3d4-...
  DEBUG: Result 2: Configure network security...
  DEBUG:   ✗ No policy ID found, title doesn't contain 'policy', skipping
  ```

#### Extracted Policies
- Total number of policies extracted
- For each policy:
  - Policy name (truncated to 80 chars)
  - Policy ID or "See documentation"
  - Learn URL
- Example:
  ```
  INFO: ✓ Found 2 relevant policies
  DEBUG:   Policy 1: Azure Policy - Enable Microsoft Defender for Cloud on subscriptions
  DEBUG:     ID: abc123-def456-...
  DEBUG:     URL: https://learn.microsoft.com/...
  ```

### 3. AI Prompt Generation

#### Policy Context Formatting
- Number of policies being formatted
- Each policy being added to context
- Final policy context length
- Preview of generated context
- Example:
  ```
  INFO: Formatting 2 policies for AI prompt context
  DEBUG:   Added policy 1/2: Azure Policy - Enable Microsoft Defender...
  DEBUG:   Added policy 2/2: Azure Policy - Audit VMs without managed disks
  INFO: ✓ Generated policy context (1234 chars) with 2 policies for SAMA-GOV-01
  DEBUG: Policy context preview: Relevant Azure Policies from Microsoft Learn:\n2 policies found...
  ```

#### Complete Prompt
- Number of MCSB controls being considered
- Total prompt length
- Preview of first 300 characters
- Example:
  ```
  DEBUG: Creating AI mapping prompt with 15 MCSB controls
  INFO: Generated prompt for AI (4567 chars) with 15 MCSB controls and policy context
  DEBUG: Prompt preview: You are an expert in cybersecurity compliance frameworks...
  ```

### 4. Overall Mapping Flow

- Control ID being mapped
- Azure Policy search initiation
- Policy search completion with context length
- Prompt creation with control count
- Final mapping result (control ID → MCSB control, confidence score)

## How to Use the Logs

### Watch logs in real-time:
```bash
tail -f /tmp/backend.log
```

### Filter for specific components:
```bash
# Only Microsoft Learn client logs
grep "microsoft_learn_client" /tmp/backend.log

# Only AI mapping service logs
grep "ai_mapping_service" /tmp/backend.log

# Only DEBUG level
grep "DEBUG" /tmp/backend.log

# Track a specific control
grep "SAMA-GOV-01" /tmp/backend.log
```

### Analyze API call success rate:
```bash
# Count successful API calls
grep "Microsoft Learn API response: 200" /tmp/backend.log | wc -l

# Count failed API calls
grep "Microsoft Learn API response: 4" /tmp/backend.log | wc -l
```

### Find empty result scenarios:
```bash
grep "Microsoft Learn returned 0 results" /tmp/backend.log
```

## Fine-Tuning Opportunities

Based on the logs, you can identify:

1. **Query Quality**: Are queries too generic or too specific?
2. **Result Relevance**: Are the right policies being extracted?
3. **API Efficiency**: How many API calls return useful results?
4. **Context Size**: Is the policy context appropriate for the AI model?
5. **Truncation Issues**: Are important parts being cut off?

## Current Configuration

- Log Level: **DEBUG** (set in `app/main.py`)
- Log Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Output: `/tmp/backend.log`

## To Reduce Log Verbosity

Change in `app/main.py`:
```python
logging.basicConfig(
    level=logging.INFO,  # Change from DEBUG to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

This will hide DEBUG messages while keeping INFO, WARNING, and ERROR messages.
