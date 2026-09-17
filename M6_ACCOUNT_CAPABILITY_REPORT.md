# M6 Meta Account Capability Report

## Safe inspection

The repository and local environment were inspected for Meta/WhatsApp tokens, WABA/phone identifiers, webhook handlers, SIP credentials, media endpoints, and prior adapter configuration. No account configuration or secret-bearing environment variable was available. Existing project material contains research only; no authorized Meta client or account session was used.

| Capability | Result | Evidence / gate |
|---|---|---|
| WABA and phone-number readiness | **NOT MEASURED** | No account surface or identifiers available |
| Calling feature enabled | **NOT MEASURED** | Calling is account-specific and publicly documented as disabled by default |
| Required permissions | **NOT MEASURED** | No Meta app/token inspection performed |
| Calls webhook readiness | **NOT MEASURED** | No authorized callback configuration available |
| SIP/media/WebRTC configuration | **NOT MEASURED** | No SIP endpoint or account negotiation available |
| Production probe | **BLOCKED** | Requires Meta login/account access and human approval; no reversible no-side-effect probe was exposed |

Exact human gate: Meta account access, phone-number/WABA eligibility, Calling enablement, webhook permission/subscription, and—if SIP is selected—SIP endpoint provisioning and credentials. Business-initiated calling additionally crosses Meta pricing/payment terms. No credentials were requested or changed.
