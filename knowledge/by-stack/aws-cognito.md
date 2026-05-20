# AWS Cognito — stack notes

Source: redscan pack (aws_cognito v1.0.0). Use when target uses Cognito User Pools or Identity Pools.

## Fingerprinting

- Response headers: `x-amzn-requestid`, `x-amz-cognito-request-id`
- Token `iss`: `https://cognito-idp.<region>.amazonaws.com/<pool_id>`
- Login URLs: `<domain>.auth.<region>.amazoncognito.com`
- JS source: `amazon-cognito-identity-js`, `aws-amplify`

## Critical invariants to test

### cognito_token_revocation (Critical)
Revoked tokens must be rejected on all endpoints.
```
# 1. Capture a valid access token
# 2. Sign the user out: POST to GlobalSignOut or AdminUserGlobalSignOut
# 3. Replay the captured access token against the app's API
# Expect: 401. If 200 → token revocation not enforced.
```

### cognito_hosted_ui_redirect (Critical)
Hosted UI redirect_uri must be validated against allowed callback URLs.
```
GET https://<domain>.auth.<region>.amazoncognito.com/oauth2/authorize
  ?response_type=code&client_id=<id>&redirect_uri=https://attacker.com
# Expect: error page. If 302 to attacker.com → open redirect → auth code theft.
```

### cognito_srp_downgrade (High)
SRP flow must not be downgradeable to USER_PASSWORD_AUTH when MFA enforced.
```
POST https://cognito-idp.<region>.amazonaws.com/
  X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth
{"AuthFlow":"USER_PASSWORD_AUTH","ClientId":"...","AuthParameters":{"USERNAME":"...","PASSWORD":"..."}}
# If MFA enforced, expect ChallengeName=SMS_MFA. If tokens returned → downgrade succeeded.
```

### cognito_identity_pool_unauthenticated (High)
Unauthenticated identity pool access must not grant sensitive AWS permissions.
```
# Get unauthenticated credentials:
POST https://cognito-identity.<region>.amazonaws.com/
  X-Amz-Target: AWSCognitoIdentityService.GetId → GetCredentialsForIdentity
# Use returned temp creds with AWS CLI:
AWS_ACCESS_KEY_ID=... aws s3 ls  / aws dynamodb list-tables
# Any data access = overpermissioned guest role.
```

### cognito_refresh_token_rotation (High)
Old refresh token must be rejected after rotation.
```
POST /oauth2/token  grant_type=refresh_token&refresh_token=<old_token>
# Use SAME old token twice. Expect: 400 on second call. If 200 → reuse not detected.
```

### cognito_user_pool_self_signup (Medium)
When AllowAdminCreateUserOnly=true, unauthenticated signup must be blocked.
```
POST https://cognito-idp.<region>.amazonaws.com/
  X-Amz-Target: AWSCognitoIdentityProviderService.SignUp
{"ClientId":"...","Username":"attacker@evil.com","Password":"..."}
# Expect: NotAuthorizedException. If UserConfirmationNecessary → self-signup enabled.
```

## Key endpoints (sinks)

| Endpoint | Method | Key params |
|---|---|---|
| `/oauth2/token` | POST | grant_type, code, redirect_uri, client_id, refresh_token |
| `/oauth2/authorize` | GET | response_type, client_id, redirect_uri, state, scope |
| Cognito API (JSON-RPC) | POST | Varies by X-Amz-Target |

## Misconfig patterns

- **Weak password policy** — `DescribeUserPool` (admin) shows `PasswordPolicy`. Min length < 8 or no complexity = finding.
- **MFA optional** — policy shows `MfaConfiguration=OFF` or `OPTIONAL` on sensitive app = medium finding.
- **Token expiry too long** — access token > 24h or refresh token > 30d in pool settings.

## Chaining notes

- Unauthenticated identity pool + overpermissioned IAM role = AWS resource access without login
- Hosted UI open redirect + auth code grant = authorization code interception → ATO
- SRP downgrade + no MFA enforcement = MFA bypass chain
