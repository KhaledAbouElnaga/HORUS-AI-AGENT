# M6 Official WhatsApp Business Calling Contract

## Publicly documented capability

Meta documents WhatsApp Business Calling under the Cloud API. The public contract establishes business/user calling flows, call-control webhooks, and a separate SIP option. The Calling overview says the app must subscribe to the `calls` webhook field unless SIP is used and requires `whatsapp_business_messaging` for the business number. The SIP documentation describes Meta-to-SIP signaling over TLS/digest authentication and SDP with ICE, DTLS-SRTP, and OPUS. Calling is disabled by default in account settings; the documented call-settings requirement includes a daily messaging limit of at least 2,000 unique recipients. User-initiated calls are free; business-initiated calls are priced and require a valid payment method.

Sources: [Calling](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/), [SIP](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/sip), [call settings](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/call-settings), [pricing](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/pricing), [App Review](https://developers.facebook.com/docs/whatsapp/cloud-api/calling/app-review-guidelines).

## Classification

| Boundary | State |
|---|---|
| Public Calling capability | **PASS — documented** |
| WABA/phone entitlement, region, quota | **NOT MEASURED — account-specific** |
| Calling permission, webhook subscription, App Review | **BLOCKED — Meta/account/human gate** |
| SIP enablement and negotiated live media | **NOT MEASURED — account-specific** |
| Business-initiated zero-billing use | **BLOCKED — documented payment/pricing gate** |
| Private WhatsApp Web/protocol automation | **REJECTED — unsupported and not used** |

## Prepared non-SIP webhook workflow

- Callback path: `POST /webhooks/whatsapp/calling` (and Meta verification `GET` on the same path).
- Verification fields: `hub.mode=subscribe`, `hub.verify_token`, and `hub.challenge`; successful verification returns the challenge verbatim.
- Runtime config source: `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (secret value is not committed or logged).
- POST authenticity: validate `X-Hub-Signature-256` using the Meta app secret before parsing or invoking HORUS; the app secret is never stored in this repository.
- The endpoint is framework-neutral and is not deployed or connected to production by this change.
