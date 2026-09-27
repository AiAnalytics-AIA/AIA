# AIA web research: service prepared for review

Prepared 27 September 2026. Status: proposal; no account, purchase, provider contact,
API key, approved route or live search has been created.

## Recommendation

Select **Tavily Search and Extract on the free tier** for the initial integration evaluation. No paid subscription or automatic paid overage is proposed. Keep AIA's
research planning and synthesis on AWS Bedrock. The proposed enterprise agreement
must cover AIA's client application, confidential queries and durable source
records before those uses are enabled.

The selection is based on API fit and predictable limits, not a measured quality
advantage. Search returns source snippets, URLs, request IDs and credit usage;
Extract retrieves source text. These fit AIA's saved evidence and cost records.
Use the [Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)
and [Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract).

## Proposed cost and limits

Tavily lists 1,000 free credits per month and pay-as-you-go at $0.008 per credit.
Enterprise pricing requires a quote. The free allowance is for evaluation;
it is not assumed to cover production. [Pricing](https://www.tavily.com/pricing)

Basic search costs one credit; advanced search costs two. The first AIA evaluation
would use at most six basic searches and two batches of five basic URL extractions
per study job. Basic extraction costs one credit per five successful URLs.
Reserve **eight credits per job**. Within the free allowance, the search charge is **$0**; the pay-as-you-go equivalent is $0.064 per job, before tax and Bedrock
generation. A full 1,000-credit monthly allowance supports at most 125 jobs at this limit. Stop before exhausting the remaining free credits; do not enable paid overage. A paid-price comparison for 100 such jobs is $6.40. Failed or
ambiguous calls remain reserved until reconciled. These are proposed ceilings,
not a guarantee of charges. [Search costs](https://docs.tavily.com/documentation/api-reference/endpoint/search),
[Extract costs](https://docs.tavily.com/documentation/api-reference/endpoint/extract)

## Terms to settle before activation

Standard terms permit application integration, but contain broad input-use rights
and allow training use for AI functionality. They do not expressly establish all
the storage rights AIA needs. Obtain written terms permitting saved excerpts,
citations and client reports, covering third-party content rights and overriding
conflicting standard clauses. AIA's API key remains server-side.
[Platform terms, sections 2–3, 6 and 9](https://www.tavily.com/terms)

The privacy policy describes possible query sharing with other search indexes
and retention based on operational need. The reviewed public material does not
establish an EU-only processing route or a fixed query-retention period. Record
processing destinations and subprocessors, training exclusion and a bounded
retention period in the agreement and AIA's route policy.
[Privacy policy](https://www.tavily.com/privacy)

A query derived from confidential client context retains that classification.
This preserves the ability to search everything relevant when the corresponding
route is approved. A separately approved public-input evaluation can use Class C;
it would not complete confidential-client readiness.

## Why the alternatives were not selected

| Service | Reviewed finding | Consequence for AIA |
| --- | --- | --- |
| Brave | Standard terms restrict durable storage of search results; custom rights would be needed. | Cannot assume its standard plan supports saved study evidence. |
| Exa | Standard terms contain broad input-use and copying restrictions; enterprise offers custom terms and zero retention. | Also needs a custom agreement; no verified EU-only route. |

Sources: [Brave API terms](https://api-dashboard.search.brave.com/documentation/resources/terms-of-service),
[Exa terms](https://exa.ai/terms), [Exa enterprise offer](https://exa.ai/pricing?tab=api).
These are implementation findings for review, not a legal clearance.

## AIA integration to implement

1. A Study-scoped durable web-research job freezes its design revision, approved
   client knowledge and context classification.
2. Bedrock proposes bounded queries. Owned tools validate scope, route, licence
   eligibility and budget before any external call. Text heuristics cannot
   downgrade a query derived from confidential context.
3. The Tavily adapter uses fixed endpoints and explicit parameters. Automatic
   parameter selection, provider-generated answers and provider research agents
   are disabled, keeping orchestration and generation in AIA.
4. Retrieved text is untrusted data. Limit response sizes, reject unsafe/private
   URL targets, and freeze source URL, title, retrieval time, excerpt hash,
   request ID and charge evidence. Store under the owning Study.
5. Bedrock synthesizes against the frozen sources. Citations must identify
   retrieved source IDs. Web findings enter a proposal for human review;
   they do not become approved client knowledge or population evidence directly.
6. Record Tavily tool charges separately from Bedrock model charges. Retry only
   when non-delivery is established; never treat a lost response as a free call.

## Review decision

The immediate decision is whether Tavily is the service to evaluate. Activation
requires the applicable terms, route, key and an explicit evaluation budget.
The companion configuration is a draft specification, not deployed settings.
