# UCLA Class Tracker

Checks UCLA's Schedule of Classes every ~5 minutes and buzzes your phone when a
class opens up (or a waitlist spot appears). Runs free on GitHub, so it keeps
working with your laptop closed.

Setup takes about 15 minutes. No coding needed.

---

## Step 1 — Set up phone notifications (ntfy)

1. Install the free **ntfy** app (App Store or Google Play).
2. Open it → tap **+** → make up a **topic name** that nobody could guess, like
   `bruin-classes-k7x2q9`. Anyone who knows the name can see your alerts, so
   don't use something like `ucla`.
3. Tap **Subscribe**. Write the topic name down — you'll need it in Step 4.
4. (iPhone) Allow notifications when asked.

## Step 2 — Make a GitHub account

Go to https://github.com and sign up (free).

## Step 3 — Create the repository and add the files

1. Click **+** (top right) → **New repository**.
2. Name: `ucla-class-tracker`. Choose **Public**.
   *Why public?* Public repos get unlimited free runs. Private ones get only
   2,000 minutes a month, which runs out in about a week at one check every 5 minutes.
   Your phone topic stays secret (Step 4); only your class links are visible.
3. Check **Add a README file** → **Create repository**.
4. Click **Add file → Upload files**. Drag in these files from the folder
   you downloaded: `check_classes.py`, `classes.txt`, `state.json`.
   Click **Commit changes**.
5. Now add the schedule file (it's in a hidden folder, so make it by hand):
   **Add file → Create new file**. In the name box type exactly:
   `.github/workflows/check-classes.yml`
   (typing the `/` creates the folders automatically). Open
   `check-classes.yml` from the download in a text editor (TextEdit / Notepad),
   copy everything, paste it in, and click **Commit changes**.

## Step 4 — Give it your ntfy topic (secretly)

1. In your repo: **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret**.
3. Name: `NTFY_TOPIC` Secret: your topic name from Step 1. → **Add secret**.

## Step 5 — Add the classes you want

1. Go to https://sa.ucla.edu/ro/public/soc, search for your class.
2. Expand the course and click the blue **section link** (e.g. `Lec 1`, or
   the discussion like `Dis 1A` if the class has discussions — you enroll
   through the discussion, so track that one).
3. Copy the URL from your browser's address bar.
4. In your repo, click `classes.txt` → the **pencil icon** (edit). Add one line
   per class at the bottom:

   ```
   Psych 10 Lec 1 | https://sa.ucla.edu/ro/Public/SOC/Results/ClassDetail?...
   Stats 13 Dis 2B | https://sa.ucla.edu/ro/Public/SOC/Results/ClassDetail?...
   ```
   Nickname, then `|`, then the URL. → **Commit changes**.

## Step 6 — Turn it on and test it

1. Click the **Actions** tab. If it asks, click
   **"I understand my workflows, go ahead and enable them."**
2. Click **Check UCLA classes** on the left → **Run workflow** (right side).
3. **Test notifications:** tick *"Just send a test notification"* → **Run workflow**.
   Within a minute your phone should show *"Class tracker test"*. ✅
4. **Real check:** click **Run workflow** again with the box *unticked*.
   You should get *"Class tracker is watching"* listing each class and its
   current status. That means it's reading UCLA's pages correctly.

Done! From now on it checks automatically about every 5 minutes.

---

## What alerts you'll get

| Alert | Meaning |
|---|---|
| 🟢 **[class] is OPEN** | Seats available — go enroll on MyUCLA now |
| 🟡 **waitlist spot** | Class is full but you can join the waitlist |
| 🔴 **filled up again** | It was open and now it's full (you missed it) |
| ⚠️ **Can't read [class]** | 3 checks in a row failed — check the URL |
| 👀 **Class tracker is watching** | Sent once when you add new classes |

It does **not** alert on small changes like 175 → 176 enrolled.

## Good to know

- **It's limited by UCLA's own update speed.** The public Schedule of Classes
  isn't live, so a seat can open and fill before the page shows it. When you get an alert,
  check MyUCLA right away.
- **GitHub's timing is approximate.** "Every 5 minutes" can sometimes be
  10–20 minutes when GitHub is busy.
- **It never logs in or enrolls you.** It only reads public pages.
- **To add/remove classes:** edit `classes.txt` any time.
- **To pause/stop:** Actions → Check UCLA classes → **⋯** → **Disable workflow**.
  Turn it back on the same way next quarter.
- **60-day rule:** GitHub pauses schedules in repos with no activity for
  60 days. Re-enable it in the Actions tab if that happens.

## Troubleshooting

- **No test notification:** check the secret is named exactly `NTFY_TOPIC` and
  matches the topic in the app (spelling and capitals count).
- **"Can't read" alert or status UNKNOWN:** open the URL from `classes.txt` in
  your browser and make sure it shows the enrollment status. If it does,
  click the failed run in the Actions tab and look at the log for the error.
- **Red ❌ run that says "classes.txt has no classes":** you still need to do Step 5.
  Make sure your lines don't start with `#`.
