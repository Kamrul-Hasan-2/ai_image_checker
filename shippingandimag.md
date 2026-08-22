# BDStall Integration Guide — id-only `image_checker` + `weight_checker`

**Audience:** the BDStall web developer (PHP / CodeIgniter) who owns
`Productlistingmodel::check_image_api()`.

**Status:** the AI side is **implemented and live-tested**. Nothing more is needed from
the AI service to start — the PHP side can switch over whenever it's ready. The old
payload still works during the transition (see [§8 Migration](#8-migration-checklist)).

---

## 1. What changed

| | Before | Now |
|---|---|---|
| Request | Full payload — `category`, `title`, `description`, `images[]`, `shipping_weight` | `{"id": 141462}` |
| Who fetches listing data | PHP builds and pushes it | AI service fetches it from `product_details` |
| Which images get checked | Whatever PHP sends | Only `ai_verified` 0 or 1 (AI filters) |
| Response | One object per image, every flag present | Only the errors actually found |
| Error naming | Flag names (`blur_image`) → PHP maps to ids | BDStall `error_id` numbers directly |
| Weight mismatch | Bundled into every image result | Separate `weight_checker` endpoint |

The `blur_image → 5`, `watermark → 4` … mapping that `check_image_api()` hardcodes today
(`Productlistingmodel.php:7453-7476`) can be **deleted** — the AI service returns those
numbers now.

---

## 2. Endpoints

Both take the same body and are `POST` with `Content-Type: application/json`.

| Endpoint | Purpose |
|---|---|
| `POST https://ai.bdstall.com/api/moderation_ai/image_checker/` | Image quality/content errors |
| `POST https://ai.bdstall.com/api/moderation_ai/weight_checker/` | Shipping-weight mismatch |
| `GET  https://ai.bdstall.com/image_checker/health` | Liveness check |

```json
{ "id": 141462 }
```

Notes:

- The un-prefixed paths (`/image_checker/`, `/weight_checker/`) work too — use whichever
  matches your existing config.
- Both endpoints hit `product_details` for the same listing, but the response is cached
  for 60 seconds, so calling them back to back costs **one** `product_details` fetch.
- The two calls are independent. Call them in any order, or in parallel.
- Set a **curl timeout of 120s**. A 5-image listing takes roughly 5–20s depending on how
  many images need checking; nginx allows up to 300s.

---

## 3. `image_checker`

### Response

```json
{
  "results": [
    { "image_id": 374187, "position_id": 0, "error_id": 5 },
    { "image_id": 374167, "position_id": 0, "error_id": 4 },
    { "image_id": 374169, "position_id": 0, "error_id": 4 }
  ],
  "checked": [374187, 374167, 374168, 374169, 374170]
}
```

(That is a real response for listing 141462.)

| Field | Always present | Meaning |
|---|---|---|
| `results` | yes | One entry **per error found**. An image with two errors appears twice. An image with no errors does not appear at all. |
| `checked` | yes | Every `image_id` that was actually evaluated. **Set `ai_verification_avator = 2` on exactly these** — see §5. |
| `skipped` | only when non-empty | Images that could not be downloaded or processed. Leave these at 0/1 so the next run retries them. |
| `error` | only on total failure | The whole batch failed; `results` and `checked` are empty. Treat as a failed call. |

`skipped` looks like this:

```json
{
  "results": [],
  "checked": [374187],
  "skipped": [
    { "image_id": 374167, "position_id": 0, "reason": "Failed to download image" }
  ]
}
```

### `error_id` values

These are BDStall's own `error_list` ids — no mapping needed on the PHP side.

| `error_id` | Check |
|---|---|
| 2 | Wrong category image |
| 3 | Promotional text found |
| 4 | Contains watermark or banner |
| 5 | Blurry image |
| 6 | Invalid background |
| 8 | Screenshot not allowed |
| 9 | Prohibited image |
| 10 | Stock image detected |

> `error_id 6` (background) is part of the contract but the current pipeline never emits
> it. It will start appearing if that check is enabled later — handle it now so nothing
> breaks then.

### HTTP status codes

| Status | Meaning | What PHP should do |
|---|---|---|
| `200` | Success | Process `results` / `checked` / `skipped` |
| `404` | Listing not found in `product_details` | Log it. Don't retry — the id is wrong or the listing is deleted |
| `422` | Bad request body | Bug on the PHP side — the body must be `{"id": <int>}` |
| `502` | `product_details` unreachable or returned garbage | Retry later. **Do not** mark anything verified |
| `503` | AI models still loading (server just restarted) | Retry in ~60s |

**Important:** a failed call never returns an empty "all clean" result. `{"results": []}`
with HTTP 200 genuinely means every checked image was clean.

---

## 4. `weight_checker`

### Response

```json
{ "weight_mismatch": false }
```

When the declared weight is implausible for the product, the numbers behind the verdict
come back with it:

```json
{
  "weight_mismatch": true,
  "error_id": 24,
  "declared_weight_kg": 200,
  "estimated_weight_kg": 4.2,
  "narration": "Declared shipping weight (200 kg) is well above the estimated actual weight (4.2 kg) for this product."
}
```

`error_id 24` = *"Weight differs from recorded product weight"*. It is a **listing-level**
error — there is no `image_id`.

| Field | When present | Meaning |
|---|---|---|
| `weight_mismatch` | always | The verdict |
| `error_id` | on mismatch | Always `24` |
| `declared_weight_kg` | on mismatch | The `shipping_weight_kg` value read from `product_details` and actually compared against — echoed back, not re-fetched, so your message always matches what was judged |
| `estimated_weight_kg` | on mismatch, when derivable | What the AI believes the listing really weighs, packaged |
| `narration` | on mismatch, when derivable | One English sentence. **Fallback only** — build the Bangla message from the two numbers |

When `weight_mismatch` is `false`, none of the extra fields appear.

`estimated_weight_kg` is an **advisory** number for a human to act on — it never decides
the verdict (see below). Treat it as missing-able: a listing can be flagged by the
category ceiling with no product-level estimate available, in which case only
`narration` explains the flag. Build your seller message defensively:

```php
if (isset($response['estimated_weight_kg'])) {
    // "ঘোষিত ওজন X কেজি, আনুমানিক প্রকৃত ওজন Y কেজি"
    $msg = $this->weight_message_bn($response['declared_weight_kg'], $response['estimated_weight_kg']);
} elseif (!empty($response['narration'])) {
    $msg = $response['narration'];
} else {
    $msg = $this->default_error_text(24);
}
```

### How the verdict is reached

So you know what a flag means when a seller disputes one:

1. **Model-specific (Gemini).** The AI looks up the product's published *net* weight and
   its typical *packaged* weight (device + box + accessories). The allowance is the higher
   of the two, plus 10%. Because sellers declare a **shipping** weight, the packaged figure
   is the fair comparison — a 0.23 kg phone genuinely ships in a ~0.38 kg box.
   This layer only fires when the AI recognises the exact model. Generic titles
   ("X-922 Bluetooth RGB Speaker") are deliberately not guessed at.
   → `estimated_weight_kg` is the packaged weight of that model.
2. **Category ceiling.** When the model isn't recognised, the weight is compared against a
   generous per-category plausibility ceiling, so unit mistakes (350 kg for a speaker) are
   still caught.
   → `estimated_weight_kg` is a *type-level* estimate ("what a Bluetooth speaker typically
   weighs"), which is why it's advisory only. It did not trigger the flag — the ceiling
   did. It may be absent.
3. **Fail open.** Unknown model *and* unrecognised category means no reference point
   exists — nothing is flagged. A pass is never a claim that the weight is correct, only
   that nothing contradicted it.

Only **over**-declared weights are flagged today: the check fires when the declared weight
exceeds the ceiling, not when it falls below the estimate. Under-declaration (a seller
shaving the shipping weight down) is not currently detected — say the word if you want
that added.

### Repeatability

The published net weight is a fact the model returns identically every time; the packaged
figure is an estimate and does drift between calls. Lookups are therefore cached per
product for 24 hours, so a seller who saves the same listing twice sees the same
`estimated_weight_kg` twice rather than a number that wanders. Editing the title starts a
fresh lookup, since that is a different product as far as the check is concerned.

### Listings with no declared weight

`product_details` now returns a numeric `shipping_weight_kg` — confirmed live on listing
169830. Listings that don't carry one yet fail open:

```json
{ "weight_mismatch": false, "reason": "no_declared_shipping_weight" }
```

That is a successful call with nothing to compare against, not an error — treat it exactly
like a clean pass. The free-text `specification` entry (`"Package Weight: Approximately
0.70 kg"`) is deliberately **not** parsed as a substitute: it isn't guaranteed to be
present, numeric, or in kg, and a misread string would flag a real seller.

---

## 5. Which images to mark `ai_verification_avator = 2`

This is the one part that is easy to get wrong.

An image is absent from `results` for **two different reasons** — it was clean, or it was
never looked at. Only the first may be marked done. That's what `checked` is for:

```
ai_verification_avator = 2   →   exactly the ids in `checked`
leave at 0 / 1               →   ids in `skipped`, and anything not in either list
```

Do **not** write `UPDATE ... WHERE ai_verification_avator IN (0,1)` after a successful
call. If a seller adds a photo between the AI fetching `product_details` and PHP running
the update, that blanket update would mark a never-checked photo as verified.

Only update when the HTTP status was `200`. On `502` / `503` / curl failure, change
nothing — the images stay at 0/1 and the next save retries them.

### 5.1 Clearing stale errors

Since only unchecked images are re-evaluated, **don't** delete every AI image error for
the listing before writing new ones — that would wipe errors belonging to images already
at `ai_verified = 2`, which weren't re-checked and so won't be re-reported.

Delete only the error rows whose image is in `checked`, then insert the new `results`:

```php
if (!empty($checked)) {
    $this->db->where('listing_id', $listing_id)
             ->where_in('avator_id', $checked)
             ->where_in('error_id', [2, 3, 4, 5, 6, 8, 9, 10])
             ->delete('listing_error');
}
```

For `weight_checker`, clear `error_id = 24` for the listing on every successful call, then
re-insert it only if `weight_mismatch` is `true`.

---

## 6. PHP implementation

> Table/column names below (`listing_avator`, `avator_id`, `listing_error`) and the
> `set_listing_error()` signature are illustrative — keep your own. The logic is the part
> that matters.

### 6.1 Shared HTTP helper

```php
/**
 * POST {"id": N} to an AI moderation endpoint.
 * Returns the decoded array on HTTP 200, or null on any failure.
 */
private function call_ai_moderation($endpoint, $listing_id)
{
    $url = 'https://ai.bdstall.com/api/moderation_ai/' . $endpoint . '/';

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode(['id' => (int) $listing_id]),
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT        => 120,
    ]);

    $body     = curl_exec($ch);
    $status   = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curl_err = curl_error($ch);
    curl_close($ch);

    if ($body === false) {
        log_message('error', "AI {$endpoint} curl failed (listing {$listing_id}): {$curl_err}");
        return null;
    }

    if ($status !== 200) {
        log_message('error', "AI {$endpoint} HTTP {$status} (listing {$listing_id}): {$body}");
        return null;
    }

    $data = json_decode($body, true);
    if (!is_array($data)) {
        log_message('error', "AI {$endpoint} bad JSON (listing {$listing_id}): {$body}");
        return null;
    }

    // Total-failure marker — treat exactly like a transport failure.
    if (isset($data['error'])) {
        log_message('error', "AI {$endpoint} reported failure (listing {$listing_id}): {$data['error']}");
        return null;
    }

    return $data;
}
```

### 6.2 `check_image_api()`

```php
/**
 * Run the AI image checks for one listing.
 * Returns true if the call succeeded and results were applied, false otherwise.
 */
public function check_image_api($listing_id)
{
    $response = $this->call_ai_moderation('image_checker', $listing_id);
    if ($response === null) {
        // Nothing is marked verified — the next save retries this listing.
        return false;
    }

    $results = isset($response['results']) ? $response['results'] : [];
    $checked = isset($response['checked']) ? array_map('intval', $response['checked']) : [];
    $skipped = isset($response['skipped']) ? $response['skipped'] : [];

    if (empty($checked) && empty($skipped)) {
        // Every image was already at ai_verified = 2 — nothing to do.
        return true;
    }

    $this->db->trans_start();

    // 1. Clear previous AI errors, but ONLY for the images that were re-checked (§5.1).
    if (!empty($checked)) {
        $this->db->where('listing_id', $listing_id)
                 ->where_in('avator_id', $checked)
                 ->where_in('error_id', [2, 3, 4, 5, 6, 8, 9, 10])
                 ->delete('listing_error');
    }

    // 2. Write one row per error found. error_id comes straight from the AI —
    //    the old flag-name-to-id mapping is gone.
    foreach ($results as $row) {
        $this->set_listing_error(
            $listing_id,
            (int) $row['error_id'],
            (int) $row['image_id'],
            (int) $row['position_id']
        );
    }

    // 3. Mark ONLY the evaluated images as done. Never a blanket
    //    "WHERE ai_verification_avator IN (0,1)" — see §5.
    if (!empty($checked)) {
        $this->db->where('listing_id', $listing_id)
                 ->where_in('avator_id', $checked)
                 ->update('listing_avator', ['ai_verification_avator' => 2]);
    }

    $this->db->trans_complete();

    // 4. Images the AI could not fetch stay at 0/1 and retry on the next save.
    foreach ($skipped as $s) {
        log_message('error', sprintf(
            'AI image_checker skipped image %d on listing %d: %s',
            $s['image_id'], $listing_id, $s['reason']
        ));
    }

    return true;
}
```

### 6.3 `check_weight_api()`

```php
/**
 * Run the AI shipping-weight check for one listing.
 */
public function check_weight_api($listing_id)
{
    $response = $this->call_ai_moderation('weight_checker', $listing_id);
    if ($response === null) {
        return false;
    }

    // Always clear the previous verdict before writing the new one.
    $this->db->where('listing_id', $listing_id)
             ->where('error_id', 24)
             ->delete('listing_error');

    if (!empty($response['weight_mismatch'])) {
        $error_id = isset($response['error_id']) ? (int) $response['error_id'] : 24;
        $this->set_listing_error($listing_id, $error_id);   // listing-level, no image_id
    }

    // Informational: the AI had no declared weight to compare against (§4).
    if (isset($response['reason']) && $response['reason'] === 'no_declared_shipping_weight') {
        log_message('debug', "weight_checker: listing {$listing_id} has no shipping_weight_kg in product_details");
    }

    return true;
}
```

### 6.4 Calling both on listing save

```php
$this->check_image_api($listing_id);
$this->check_weight_api($listing_id);
```

---

## 7. Testing

Health check first:

```bash
curl https://ai.bdstall.com/image_checker/health
# {"status":"healthy","service":"AI Image Checker","version":"1.0.0","ready":true}
```

Real listing:

```bash
curl -X POST https://ai.bdstall.com/api/moderation_ai/image_checker/ \
     -H 'Content-Type: application/json' \
     -d '{"id": 141462}'
```

```bash
curl -X POST https://ai.bdstall.com/api/moderation_ai/weight_checker/ \
     -H 'Content-Type: application/json' \
     -d '{"id": 141462}'
```

Unknown listing — should be HTTP 404, **not** an empty clean result:

```bash
curl -i -X POST https://ai.bdstall.com/api/moderation_ai/image_checker/ \
     -H 'Content-Type: application/json' \
     -d '{"id": 999999999}'
```

Interactive docs: <https://ai.bdstall.com/docs>

### Cases worth testing before rollout

| Case | Expected |
|---|---|
| Listing where all images are `ai_verified = 2` | `{"results": [], "checked": []}` — nothing updated |
| Listing with a mix of 0/1 and 2 | Only the 0/1 ids appear in `checked` |
| One image with two errors | Two entries in `results`, same `image_id` |
| Broken/deleted image URL | Appears in `skipped`, **stays** at 0/1 in the DB |
| AI service down | `check_image_api()` returns false, **no** `ai_verified` change |
| Re-running the same listing twice | Second run is a no-op (`checked` is empty) |

---

## 8. Migration checklist

The AI service accepts **both** contracts right now, so the switch can be done in one
deploy without downtime.

- [ ] Add the `call_ai_moderation()` helper
- [ ] Rewrite `check_image_api()` to POST `{"id": ...}` and read `results` / `checked` / `skipped`
- [ ] **Delete** the hardcoded flag-name → `error_id` mapping (`Productlistingmodel.php:7453-7476`)
- [ ] **Delete** the payload builder (title / description / category / image-URL collection)
- [ ] Add `check_weight_api()` and call it alongside `check_image_api()`
- [ ] Stop reading `weight_mismatch` out of the `image_checker` response
- [ ] Replace the `ai_verification_avator` update with the `checked`-based one (§5)
- [ ] Scope the stale-error delete to `checked` image ids (§5.1)
- [ ] Add `shipping_weight_kg` to the `product_details` response (§4) — can ship separately
- [ ] Verify against listing 141462 in staging

Once the PHP side is live, the legacy payload path can be removed from the AI service.

---

## 9. Reference — what the AI service does with the id

1. `GET https://www.bdstall.com/api/item_ai/product_details/?key=123_456&id=<id>`
2. Reads `title`, `category`, `description` and the `images` array from `data`
3. Keeps only images where `ai_verified` is `0` or `1` (`2` = already checked, skipped)
4. Runs the pipeline — blur, watermark, promotional text, screenshot, CLIP category match
5. Returns `results` + `checked` + optional `skipped`

Configurable on the AI side via env vars if the API ever moves:

| Env var | Default |
|---|---|
| `BDSTALL_PRODUCT_DETAILS_URL` | `https://www.bdstall.com/api/item_ai/product_details/` |
| `BDSTALL_API_KEY` | `123_456` |
| `BDSTALL_PRODUCT_DETAILS_TIMEOUT` | `15` seconds |
| `BDSTALL_PRODUCT_DETAILS_TTL_SECONDS` | `60` (response cache) |
