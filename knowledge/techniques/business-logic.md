# Business logic flaws — playbook

The class with the highest payout-per-bug because scanners can't find them.
Requires reading the app like a user with bad intent.

## when to try
- Always. Especially: cart/checkout, refunds, gift cards/credits, referrals,
  coupons, tier upgrades/downgrades, voting/rating, invitations, tipping,
  marketplaces, "share with N people max" features.

## bug archetypes
- **Negative or zero values**: `quantity=-1` (refunds you), `amount=0`, `discount=200%`.
- **Tampered totals**: client computes price → server trusts it. Edit the JSON.
- **Step-skipping**: 3-step checkout — go directly to step 3.
- **State machine illegal transitions**: `cancelled → paid`, `delivered → cancelled`, `pending → completed` without paying.
- **Re-applying single-use**: re-use coupon by editing user_id/cart_id, or by race (see `race-conditions.md`).
- **Currency**: `currency=USD` → `currency=ZWL` with same number. Or set `currency_rate` if exposed.
- **Quantity overflow**: `quantity=99999999` triggers integer overflow → negative total.
- **Object-confusion**: passing a different entity ID where the app expects e.g. an order ID — sometimes treated as belonging to you (bridges into IDOR).
- **Promo abuse**: stack stackable + non-stackable, apply expired by setting `valid_until` in the body.
- **Referral self-credit**: refer yourself with a second account; pivot through identifiers (email plus-aliasing, gmail dot-trick).

## confirmation flow
1. Walk the happy path with a proxy. List every parameter that could be an "amount", "id", "tier", "state".
2. For each: try negative, zero, very large, missing, duplicated, wrong-type (string vs int).
3. For multi-step flows: skip steps. Send step N's request without doing N-1.
4. Check responses for hidden fields (`is_admin`, `is_paid`, `is_verified`, `tier`) — try mass-assign in the next request (`access-control.md`).

## caveats
- Don't actually charge real cards or transfer real money. Use test mode or sandbox.
- Logic flaws often need a clean exploit demo to be taken seriously — record steps + show financial impact.

## provenance
PortSwigger Business Logic labs. HackerOne logic top-paid lists.
