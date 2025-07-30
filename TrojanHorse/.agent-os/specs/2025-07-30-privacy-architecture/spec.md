# Spec Requirements Document

> Spec: Privacy Architecture
> Created: 2025-07-30
> Status: Planning

## Overview

Implement a privacy architecture that filters personally identifiable information (PII) from transcribed text before it is sent to the cloud for analysis.

## User Stories

### PII Filtering

As a user, I want to have PII automatically filtered from my transcribed conversations before they are sent to the cloud, so that I can be sure that my private information is not being shared.

## Spec Scope

1. **PII Detection:** Implement a PII detection service that can identify common PII such as names, email addresses, and phone numbers.
2. **PII Redaction:** Implement a PII redaction service that can replace PII with placeholders.
3. **User Configuration:** Allow users to configure the PII detection and redaction settings.

## Out of Scope

- Filtering PII from audio data.
- Filtering PII from images or other non-text data.

## Expected Deliverable

1. A new `privacy.py` module that contains the PII filtering logic.
2. The ability to run the PII filtering service from the command line.
3. The `cloud_analyze.py` module will be modified to use the `privacy.py` module to filter PII before sending text to the cloud.
