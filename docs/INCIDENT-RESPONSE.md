# Incident response: personal data breaches

Not legal advice; reviewed by no lawyer yet. Deadlines and the form of notices under the DPDP Rules, 2025 must be confirmed
with counsel before an incident, not during one.

A **personal data breach** is any unauthorised processing, disclosure, loss or alteration of personal data, or loss of access to
it. For Mimir the personal data at risk is small by design: encrypted vaults, hashed login secrets, dates, and (for people who
opted in) hashed visitor ids and usage counts. Vault contents cannot be read without a person's recovery key.

## Roles (fill in)
| Role | Person | Contact |
|---|---|---|
| Incident lead | [to be named] | |
| Grievance Officer | [to be named] | |
| Technical lead / plugin maintainer | [to be named] | |
| Legal counsel | [to be named] | |
| Hosting contacts | WordPress.com support (account owner), GitHub | |

## Steps
1. **Detect and report.** Anyone who suspects an incident tells the incident lead at once (security reports arrive at hello@terratalesmedia.world, subject "Security"). Start the log below.
2. **Contain.** Within hours: deactivate the Mimir Vault plugin or block the endpoints if the server is affected; rotate WordPress admin passwords and application keys; revoke exposed tokens; for a site defect, redeploy a fixed build. Preserve evidence (logs, database snapshot) before changing anything.
3. **Assess.** What data, whose, how many people, how it was exposed, whether it was readable (ciphertext and hashes are not), and whether it is ongoing. Decide if it is a reportable breach.
4. **Notify.** If reportable: inform each affected Data Principal without delay and the Data Protection Board of India in the form and within the time the Rules set; tell the host if they must act. Vault holders cannot be contacted individually (no email is held), so publish the notice on the privacy page and in the product, and advise them to change their recovery key.
5. **Fix and recover.** Patch the cause, restore from a clean backup if needed, check the fix with the contract tests (`php wordpress/tests/harness.php`), and watch for recurrence.
6. **Review.** Within 14 days: root cause, what worked, changes to controls and to this plan; update `docs/DPDP.md`.

## Incident log (copy per incident)
| Time (UTC) | Who | What was seen or done |
|---|---|---|

## Templates
**Notice to people (publish on /privacy/ and in the product; add to the Account page if relevant)**
> On [date] we found that [what happened] affecting [which data] for [which people]. [Whether any readable personal data was
> exposed; Mimir vaults are encrypted on your device and the server holds only ciphertext.] We have [what we did]. What you
> should do: [for example make a new recovery key on the Account page]. Contact: [Grievance Officer, email]. You may complain to
> the Data Protection Board of India.

**Intimation to the Data Protection Board of India (check the prescribed form and timeline)**
- Fiduciary: Terratales Media Entertainment Private Limited, [CIN], registered office [address], contact [name, phone, email]
- Nature, extent, timing and location of the breach, and likely impact
- Data and number of people affected
- Measures taken and proposed to limit harm
- Findings on who caused it and why, and remedial steps to prevent recurrence
- Notice given to affected people (how and when)
- Detailed report where required within the prescribed period
