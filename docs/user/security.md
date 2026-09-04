# Your data and your account

What BeCoMe stores about you, who can see it, and how to take it back. This page is for the person
using the product. The engineering account of the same system, including what it deliberately does
not defend against, stays in the repository rather than here.

## Your password

Your password is never stored. What is stored is a bcrypt hash of it, which cannot be turned back
into the password, and which is computed fresh with a different salt for every account. Two people
who choose the same password get different hashes.

Repeated failed sign-ins to one account are throttled, so someone working through a list of guesses
is slowed to uselessness. An email address that has never registered is treated exactly like one
that has, including the time it takes to answer, so the sign-in form cannot be used to find out who
has an account here.

## Your session

Signing in gives your browser two tokens, held in cookies your own page scripts cannot read. The
short-lived one authorizes requests. The longer-lived one renews it, and it rotates on every
renewal: each use mints a new token and retires the old.

That rotation is the part worth knowing. If a refresh token is ever stolen and used, the theft
shows up the next time your own browser renews, because the token it holds has already been
retired. The whole session is then revoked rather than left running beside the thief's.

## Who can see your opinions

The members of the project, and nobody else. A project is visible to its owner and the experts
invited into it. Your opinion carries your name, so a panel is not anonymous: everyone in the room
can see who said what, which is the point of a panel and worth knowing before you answer.

When an admin removes someone from a project, that person's opinion is deleted in the same
operation and the result is recalculated without it. The opinion does not linger in the project
after the person has gone.

## Taking your data out

**Export.** One request returns everything the system holds about you as a JSON file: your profile,
the projects you own with their results, the projects you joined, every opinion you have given, and
the invitations you received. It does not include invitations you sent, because those are about the
person you sent them to.

**Deletion.** Deleting your account removes it, along with your profile photo. Projects you
administer need a decision first: for each one you either hand it to another member or delete it.
The account goes only after every project you own has an answer.

That extra step is deliberate. Without it, one person leaving would silently take a whole panel's
work with them, including opinions that other people gave.

## Email

Your address is used to sign you in, to confirm the account when you register, to reset a forgotten
password, and to tell you that someone invited you to a project. It is not used for anything else,
and it is visible to the members of projects you join.
