# Prompt for Antigravity — Sakura Shop "Konkurs" (Referral Contest)

Paste this into Antigravity in the **same project** as the Sakura shop bot. It adds a feature; it doesn't create a new bot.

---

Add a **referral contest ("Konkurs")** feature to the existing Sakura shop bot (aiogram 3 + FastAPI + SQLAlchemy + React Mini App). Reuse the existing owner/admin system, the linked channel, the i18n file (Uzbek default), and the pink sakura design. Scores must be **exactly correct**: no double counting, no fake points, no lost points, even if the bot restarts.

## 1. How it works (the rules)

1. The owner starts a contest with **one button** and enters prizes for 🥇 1st, 🥈 2nd and 🥉 3rd place.
2. The bot posts a contest announcement in her channel with a "🎁 Qatnashish" (participate) button.
3. Every participant gets a **personal invite link**: `https://t.me/<bot>?start=r_<contest_id>_<referrer_user_id>`.
4. A friend opens the link and starts the bot. The bot shows: "Konkursda qatnashish uchun kanalga obuna bo'ling 🌸" with two buttons: **📢 Kanalga o'tish** (opens the channel) and **✅ Tasdiqlash** (confirm).
5. When the friend presses **✅ Tasdiqlash**, the bot checks the subscription with `getChatMember(channel_id, user_id)`:
   - **Subscribed:** the referrer gets **+1** and the friend sees "Rahmat! 🌸 Siz konkursda ham qatnashishingiz mumkin". The friend also gets their own invite link, so they can compete too.
   - **Not subscribed:** show "Siz hali obuna bo'lmagansiz 🙈" and keep the buttons. Nothing is counted.
6. Whoever has the most points at the end wins 1st place, then 2nd and 3rd.

## 2. Exact counting rules (no mistakes)

A referral counts **+1 only when ALL of these are true**:
- A contest is **active**, and the link's `contest_id` is that active contest.
- The invitee is a **new bot user**: their first `/start` ever happened through this link. A person who already used the bot before can't be "invited".
- The invitee isn't the referrer (no self-invites) and isn't a bot (`is_bot`).
- The invitee pressed **✅ Tasdiqlash**, and `getChatMember` returned `member`, `administrator`, `creator`, or `restricted` with `is_member=true`.
- **"Only new subscribers" setting (default ON):** if the invitee was **already** a channel member when they first opened the link, it doesn't count. Check membership at first `/start` and store it as `was_member_before`. Tell them kindly that they can still join the contest themselves.
- The invitee hasn't already been counted for anyone in this contest. **The first referrer wins forever.** The referrer is locked at the invitee's first `/start` and can't be changed by opening other links later.

**Database guarantees:**
- Table `contest_referrals`: `contest_id`, `invitee_id`, `referrer_id`, `status` (`pending` / `confirmed` / `revoked`), `was_member_before`, `started_at`, `confirmed_at`, `revoked_at`.
- `UNIQUE(contest_id, invitee_id)` and `CHECK(invitee_id != referrer_id)`.
- Confirming is **idempotent and atomic**: one transaction with a conditional update `pending → confirmed`. Double taps, two devices, or Telegram retries can never give +2.
- **Scores are never a stored counter.** The leaderboard is always computed as `COUNT(*) WHERE status='confirmed' GROUP BY referrer_id`, so it can't drift. Add indexes for speed.

**Leaving the channel = point removed:**
- The bot is a channel admin, so subscribe to `chat_member` updates (`allowed_updates` must include `chat_member`). If a confirmed invitee leaves the channel during the contest, set their referral to `revoked` and notify the referrer: "Do'stingiz kanaldan chiqdi, 1 ball olib tashlandi". If they rejoin and press Tasdiqlash again, it becomes `confirmed` again (still the same referrer).
- **Final recheck at the end:** before picking winners, re-verify every confirmed invitee with `getChatMember`. Respect rate limits with a ~20 req/s throttle and `TelegramRetryAfter` handling. Revoke anyone who left. This catches leaves the bot missed while it was offline.

**Tie-break:** with equal points, the person who reached that score **first** ranks higher (compare the `confirmed_at` of their last counted referral).

## 3. Owner: create a contest with one button

- In `/admin` (and in the Mini App 👑 Admin tab), add a big button: **🎁 Yangi konkurs**.
- Wizard (FSM, every step has ⬅️ Orqaga and ❌ Bekor):
  1. 🥇 1-o'rin sovg'asi (prize text, required)
  2. 🥈 2-o'rin sovg'asi (required)
  3. 🥉 3-o'rin sovg'asi (required)
  4. ⏳ Duration buttons: **1 hafta**, **2 hafta**, or custom end date/time
  5. 🖼 Optional photo for the announcement (or skip)
  6. **Preview** of the channel post → ✅ Boshlash (start) / ✏️ Tahrirlash / ❌ Bekor
- **Only one active contest at a time.** If one is running, show it with buttons instead of starting a new one.
- All times are in **Asia/Tashkent**. Show the end time clearly, e.g. "26-oktabr, 20:00 gacha".

**Channel announcement (cute, channel style):**
```
🌸 SAKURA KONKURS 🌸

🥇 1-o'rin: <prize 1>
🥈 2-o'rin: <prize 2>
🥉 3-o'rin: <prize 3>

📌 Shartlar:
1. Botga kiring va shaxsiy havolangizni oling
2. Do'stlaringizni taklif qiling
3. Ular kanalga obuna bo'lib, ✅ Tasdiqlash tugmasini bossin

Eng ko'p do'st taklif qilgan g'olib bo'ladi! 💗
⏳ Tugash: <date time>
```
Add a URL button "🎁 Qatnashish" → `https://t.me/<bot>?start=konkurs`.

**Owner controls while it's running:**
- 📊 Live leaderboard (top 20 with names/@usernames and scores, plus total participants and confirmed invites).
- ⏹ End now, ⏳ Extend, ✏️ Edit prizes (also edits the channel post), and ❌ Cancel (with confirmation; nobody wins).
- 🔎 Check a user: who they invited and the status of each invite. This is useful for disputes.
- Show suspicious activity: e.g. many invitees who confirmed and then quickly left, so she can judge fairness.

## 4. Participants

- `/start konkurs`, the "🎁 Konkurs" button in the bot menu, and a **Konkurs tab in the Mini App** all show:
  - The prizes and a countdown timer ⏳
  - **My link**, with buttons 📋 Nusxa olish (copy) and 📤 Do'stlarga ulashish (share via `https://t.me/share/url?url=<link>&text=<cute text>`)
  - **My score** and **my place** ("Siz 4-o'rindasiz, 3-o'ringa 2 ball qoldi! 🌸")
  - Top 10 leaderboard with 🥇🥈🥉 badges and sakura petal animation
  - A list of my invites, each with status ✅ / ⏳ (pending, not confirmed yet) / ❌ (left the channel)
- The referrer gets a DM on each confirmed invite: "🎉 +1! <name> qo'shildi. Jami: 7 ball".
- Pending invitees get one reminder after ~1 hour if they haven't confirmed yet: "✅ Tasdiqlash tugmasini bosishni unutmang 🌸".
- If someone opens an invite link when **no contest is active**, they still become a normal shop user. Nothing is counted, and they see "Hozircha faol konkurs yo'q 🌸".

## 5. Ending the contest (automatic and safe)

- Store `ends_at` in the DB. Use a scheduler that **survives restarts**: on startup, check for contests that should already have ended and finish them.
- At the end: lock the contest (no more confirmations) → run the final recheck (section 2) → compute the top 3 → send the owner the **results for approval** ("✅ E'lon qilish" to announce / "🔁 Qayta tekshirish" to recheck). She can also disqualify someone before announcing, with a reason.
- After she approves:
  - Post the winners in the channel: "🏆 Konkurs g'oliblari! 🥇 @user — 12 ta do'st …" with congratulations and petals.
  - DM each winner: "Tabriklaymiz! 🎉 Siz <place>-o'rinni egalladingiz. Sovg'ani olish uchun @fkhrdnvvvva ga yozing 💌".
  - Store the results in history.
- **History:** a list of past contests with winners, scores, and total new subscribers gained. That's her "growth" stat.
- Fewer than 3 people with points: award only the places that have someone. A score of 0 never wins.

## 6. Security & edge cases

- Validate the `start` payload strictly (regex `^r_\d+_\d+$`). Ignore unknown or tampered payloads, a non-existent referrer, or a mismatched or ended contest.
- Don't count users who blocked the bot. Handle `TelegramForbiddenError` without crashing.
- If the bot loses channel admin rights, stop counting, alert the owner right away, and pause the contest until it's fixed.
- Throttle Tasdiqlash to max 1 check per 3 seconds per user.
- All admin actions require server-side owner/admin checks, both in the bot and in the Mini App API (initData HMAC).
- Log every referral state change in an audit table: who, what, when.

## 7. Tests (pytest) — must all pass

- Self-invite is rejected.
- An existing bot user opening an invite link doesn't count.
- An already-subscribed user doesn't count when "only new subscribers" is ON.
- Not subscribed + Tasdiqlash → no point; subscribe + Tasdiqlash → +1.
- Double Tasdiqlash (including concurrent calls) → exactly +1.
- The second referrer link for the same invitee is ignored.
- Leaving the channel → revoked (−1); rejoining + Tasdiqlash → confirmed again for the same referrer.
- The final recheck revokes users who left while the bot was offline.
- Tie-break orders by who reached the score first.
- Fewer than 3 scorers → only those places are awarded; 0 points never wins.
- Contest ending after a restart works (`ends_at` already in the past).
- Malformed `start` payloads are ignored safely.
- Non-admins can't create, end, or edit contests (bot and API).

Mock `getChatMember` in tests. Run the tests and show me the output, plus screenshots of the owner wizard, the channel post, the participant Konkurs tab, and the results message before finishing.
